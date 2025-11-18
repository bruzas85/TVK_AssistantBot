import os
import logging
import json
import traceback
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class RunningTask:
    def __init__(self, id=None, user_id=None, task_text="", priority="medium",
                 days_of_week=None, status_history=None, created_at=None):
        self.id = id
        self.user_id = user_id
        self.task_text = task_text
        self.priority = priority
        self.days_of_week = days_of_week or [False] * 7
        self.status_history = status_history or []
        self.created_at = created_at


class StorageService:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.memory_storage = {}  # Временное хранилище в памяти
        self.next_id = 1

        logger.info(f"🔧 Инициализация StorageService")
        logger.info(f"📊 DATABASE_URL: {'✅ Установлен' if self.database_url else '❌ Отсутствует'}")

        if self.database_url:
            try:
                self.engine = create_engine(self.database_url)
                self.Session = sessionmaker(bind=self.engine)
                logger.info("✅ Двигатель SQLAlchemy создан успешно")
                self.use_database = True
            except Exception as e:
                logger.error(f"❌ Ошибка создания двигателя SQLAlchemy: {e}")
                self.engine = None
                self.Session = None
                self.use_database = False
        else:
            self.engine = None
            self.Session = None
            self.use_database = False
            logger.warning("🔄 Используется временное хранилище в памяти")

    def add_running_task(self, user_id, task_text, priority="medium", days_of_week=None):
        if not self.use_database:
            # Используем временное хранилище в памяти
            task_id = self.next_id
            self.next_id += 1

            task = RunningTask(
                id=task_id,
                user_id=user_id,
                task_text=task_text,
                priority=priority,
                days_of_week=days_of_week,
                status_history=[],
                created_at=None
            )

            if user_id not in self.memory_storage:
                self.memory_storage[user_id] = []

            self.memory_storage[user_id].append(task)
            logger.info(f"💾 Задача сохранена в памяти, ID: {task_id}")
            return task

        # Используем базу данных
        session = None
        try:
            session = self.Session()
            days_json = json.dumps(days_of_week or [False] * 7)
            status_history_json = json.dumps([])

            logger.info(f"💾 Попытка сохранения задачи в БД: user_id={user_id}, text='{task_text}'")

            result = session.execute(text("""
                INSERT INTO running_tasks (user_id, task_text, priority, days_of_week, status_history)
                VALUES (:user_id, :task_text, :priority, :days_of_week, :status_history)
                RETURNING id
            """), {
                'user_id': user_id,
                'task_text': task_text,
                'priority': priority,
                'days_of_week': days_json,
                'status_history': status_history_json
            })

            task_id = result.scalar()
            session.commit()
            logger.info(f"✅ Задача успешно сохранена в БД, ID: {task_id}")

            return RunningTask(
                id=task_id,
                user_id=user_id,
                task_text=task_text,
                priority=priority,
                days_of_week=days_of_week,
                status_history=[],
                created_at=None
            )

        except SQLAlchemyError as e:
            logger.error(f"❌ Ошибка SQLAlchemy при добавлении задачи: {e}")
            if session:
                session.rollback()
            return None
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при добавлении задачи: {e}")
            if session:
                session.rollback()
            return None
        finally:
            if session:
                session.close()

    def get_running_tasks(self, user_id):
        if not self.use_database:
            # Используем временное хранилище в памяти
            tasks = self.memory_storage.get(user_id, [])
            logger.info(f"📊 Загружено {len(tasks)} задач из памяти для пользователя {user_id}")
            return tasks

        # Используем базу данных
        session = None
        try:
            session = self.Session()
            logger.info(f"🔍 Поиск задач в БД для пользователя {user_id}")

            result = session.execute(text("""
                SELECT id, user_id, task_text, priority, days_of_week, status_history, created_at
                FROM running_tasks 
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """), {'user_id': user_id})

            tasks = []
            for row in result:
                try:
                    days_of_week = json.loads(row[4]) if row[4] else [False] * 7
                    status_history = json.loads(row[5]) if row[5] else []

                    tasks.append(RunningTask(
                        id=row[0],
                        user_id=row[1],
                        task_text=row[2],
                        priority=row[3],
                        days_of_week=days_of_week,
                        status_history=status_history,
                        created_at=row[6]
                    ))
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON для задачи {row[0]}: {e}")
                    continue

            logger.info(f"✅ Успешно загружено {len(tasks)} задач из БД для пользователя {user_id}")
            return tasks

        except SQLAlchemyError as e:
            logger.error(f"❌ Ошибка SQLAlchemy при загрузке задач: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при загрузке задач: {e}")
            return []
        finally:
            if session:
                session.close()


# Глобальный экземпляр storage
storage_service = StorageService()


class RunningListHandlers:
    def __init__(self, storage):
        self.storage = storage
        self.priority_emojis = {
            "low": "🟦",
            "medium": "🟨",
            "high": "🟥",
            "urgent": "⚡"
        }
        self.day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def format_task_display(self, task):
        """Форматирует отображение задачи с днями недели"""
        day_emojis = ""
        for i in range(7):
            if task.days_of_week[i]:
                day_emojis += self.priority_emojis.get(task.priority, "🟨")
            else:
                day_emojis += "⬜"

        priority_emoji = self.priority_emojis.get(task.priority, "🟨")
        return f"{day_emojis} - {task.task_text} {priority_emoji}"

    async def show_running_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает running list пользователя"""
        user_id = update.effective_user.id
        logger.info(f"🔍 Запрос Running List от пользователя {user_id}")

        tasks = self.storage.get_running_tasks(user_id)

        logger.info(f"📊 Найдено задач: {len(tasks)}")

        if not tasks:
            keyboard = [
                [InlineKeyboardButton("➕ Создать первую задачу", callback_data="add_first_task")]
            ]
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "📋 **Ваш Running List пуст**\n\n"
                    "Создайте свою первую задачу для отслеживания!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "📋 **Ваш Running List пуст**\n\n"
                    "Создайте свою первую задачу для отслеживания!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            return

        message = "📋 **Ваш Running List:**\n\n"
        for i, task in enumerate(tasks):
            task_display = self.format_task_display(task)
            message += f"{i + 1}. {task_display}\n"

        # Добавляем информацию о хранилище
        if not self.storage.use_database:
            message += f"\n💡 *Задачи хранятся в памяти (перезагрузка очистит их)*"

        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_list")]
        ]

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс добавления задачи"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text("✏️ Введите текст новой задачи:")
        else:
            await update.message.reply_text("✏️ Введите текст новой задачи:")

        context.user_data['adding_task'] = True

    async def handle_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текст задачи и запрашивает приоритет"""
        if not context.user_data.get('adding_task'):
            return

        task_text = update.message.text
        context.user_data['new_task'] = {'text': task_text, 'days': [False] * 7}
        context.user_data['adding_task'] = False

        logger.info(f"📝 Пользователь ввел текст задачи: {task_text}")

        keyboard = [
            [
                InlineKeyboardButton("🟦 Низкий", callback_data="priority_low"),
                InlineKeyboardButton("🟨 Средний", callback_data="priority_medium")
            ],
            [
                InlineKeyboardButton("🟥 Высокий", callback_data="priority_high"),
                InlineKeyboardButton("⚡ Срочный", callback_data="priority_urgent")
            ]
        ]

        await update.message.reply_text(
            f"📝 Задача: *{task_text}*\n\n🎯 Выберите приоритет:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор приоритета"""
        query = update.callback_query
        await query.answer()

        priority = query.data.replace("priority_", "")
        context.user_data['new_task']['priority'] = priority

        logger.info(f"🎯 Выбран приоритет: {priority}")
        await self.show_days_selection(update, context)

    async def show_days_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор дней недели"""
        query = update.callback_query

        keyboard = []
        row = []
        for i, day in enumerate(self.day_names):
            is_selected = context.user_data['new_task']['days'][i]
            button_text = f"✅ {day}" if is_selected else day
            row.append(InlineKeyboardButton(button_text, callback_data=f"day_{i}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("💾 Сохранить задачу", callback_data="save_task")])

        days_status = ""
        selected_days = []
        for i, day_name in enumerate(self.day_names):
            if context.user_data['new_task']['days'][i]:
                days_status += f"✅ {day_name}\n"
                selected_days.append(day_name)
            else:
                days_status += f"⬜ {day_name}\n"

        priority_emoji = self.priority_emojis.get(context.user_data['new_task']['priority'], "🟨")

        message = (
            f"📝 Задача: *{context.user_data['new_task']['text']}*\n"
            f"🎯 Приоритет: {priority_emoji}\n\n"
        )

        if selected_days:
            message += f"📅 Выбранные дни:\n{days_status}\n"
        else:
            message += f"📅 Выберите дни выполнения:\n{days_status}\n"

        message += "Нажмите на день чтобы выбрать/отменить:"

        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def toggle_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает выбор дня недели"""
        query = update.callback_query
        await query.answer()

        day_index = int(query.data.replace("day_", ""))
        context.user_data['new_task']['days'][day_index] = not context.user_data['new_task']['days'][day_index]

        logger.info(f"📅 Изменен день {self.day_names[day_index]}")
        await self.show_days_selection(update, context)

    async def save_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет задачу"""
        query = update.callback_query
        await query.answer()

        task_data = context.user_data['new_task']
        user_id = update.effective_user.id

        logger.info(f"💾 Попытка сохранения задачи для пользователя {user_id}")

        await query.edit_message_text("⏳ Сохраняем задачу...")

        task = self.storage.add_running_task(
            user_id=user_id,
            task_text=task_data['text'],
            priority=task_data['priority'],
            days_of_week=task_data.get('days', [False] * 7)
        )

        if task:
            context.user_data.pop('new_task', None)
            context.user_data.pop('adding_task', None)

            logger.info(f"✅ Задача успешно сохранена с ID: {task.id}")

            storage_info = ""
            if not self.storage.use_database:
                storage_info = "\n\n💡 *Задачи хранятся в памяти*"

            await query.edit_message_text(
                f"✅ *Задача успешно добавлена в Running List!*{storage_info}\n\n"
                "Используйте кнопку '📋 Running List' для просмотра всех задач.",
                parse_mode='Markdown'
            )
        else:
            logger.error("❌ Не удалось сохранить задачу")
            await query.edit_message_text(
                "❌ *Ошибка при сохранении задачи.*\n\n"
                "Попробуйте еще раз. Если ошибка повторяется, обратитесь к администратору.",
                parse_mode='Markdown'
            )

    async def refresh_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет список задач"""
        query = update.callback_query
        await query.answer()
        await self.show_running_list(update, context)


# Создаем экземпляр обработчиков
running_handlers = RunningListHandlers(storage_service)


# ОСНОВНЫЕ ФУНКЦИИ БОТА - должны быть определены ДО их использования в обработчиках

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я TVK Assistant Bot - твой помощник в организации задач.\n\n"
        "📋 **Доступные функции:**\n"
        "• Running List - система повторяющихся задач ✅\n"
        "• Табель учета рабочего времени ⏳\n"
        "• Управление строительными объектами ⏳\n"
        "• И многое другое!\n\n"
        "✨ **Running List полностью готов к использованию!**"
    )

    keyboard = [
        [KeyboardButton("📋 Running List"), KeyboardButton("📊 Табель")],
        [KeyboardButton("🏗️ Объекты"), KeyboardButton("📝 Задачи")],
        [KeyboardButton("ℹ️ Помощь"), KeyboardButton("⚙️ Настройки")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🆘 **Помощь по TVK Assistant Bot**\n\n"
        "📋 **Running List (ГОТОВО!):**\n"
        "• Создавайте повторяющиеся задачи\n"
        "• Приоритеты: 🟦 Низкий, 🟨 Средний, 🟥 Высокий, ⚡ Срочный\n"
        "• Назначайте дни выполнения\n\n"
        "🎯 **Как использовать Running List:**\n"
        "1. Нажмите '📋 Running List'\n"
        "2. '➕ Добавить задачу' для создания\n"
        "3. Выберите приоритет и дни недели\n"
        "4. Отслеживайте выполнение\n\n"
        "🔧 **Статус функций:**\n"
        "• 📋 Running List - ✅ РАБОТАЕТ\n"
        "• 📊 Табель - ⏳ В РАЗРАБОТКЕ\n"
        "• 🏗️ Объекты - ⏳ В РАЗРАБОТКЕ\n"
        "• 📝 Задачи - ⏳ В РАЗРАБОТКЕ\n"
        "• ⚙️ Настройки - ⏳ В РАЗРАБОТКЕ"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def running_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /running_list"""
    await running_handlers.show_running_list(update, context)


async def timesheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик табеля"""
    await update.message.reply_text(
        "📊 **Табель учета рабочего времени**\n\n"
        "⏳ Эта функция находится в разработке.\n"
        "Скоро здесь будет учет рабочего времени!\n\n"
        "📋 А пока попробуйте новую систему **Running List** - она уже работает! 🚀"
    )


async def objects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик строительных объектов"""
    await update.message.reply_text(
        "🏗️ **Строительные объекты**\n\n"
        "⏳ Эта функция находится в разработке.\n"
        "Скоро здесь будет управление строительными объектами!\n\n"
        "📋 А пока попробуйте новую систему **Running List** - она уже работает! 🚀"
    )


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик общих задач"""
    await update.message.reply_text(
        "📝 **Общие задачи**\n\n"
        "⏳ Эта функция находится в разработке.\n"
        "Скоро здесь будет управление общими задачами!\n\n"
        "📋 А пока попробуйте новую систему **Running List** - она уже работает! 🚀"
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик настроек"""
    await update.message.reply_text(
        "⚙️ **Настройки**\n\n"
        "⏳ Эта функция находится в разработке.\n"
        "Скоро здесь будут настройки бота!\n\n"
        "📋 А пока попробуйте новую систему **Running List** - она уже работает! 🚀"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text

    if text == "📋 Running List":
        await running_handlers.show_running_list(update, context)
    elif text == "📊 Табель":
        await timesheet_command(update, context)
    elif text == "🏗️ Объекты":
        await objects_command(update, context)
    elif text == "📝 Задачи":
        await tasks_command(update, context)
    elif text == "ℹ️ Помощь":
        await help_command(update, context)
    elif text == "⚙️ Настройки":
        await settings_command(update, context)
    elif context.user_data.get('adding_task'):
        await running_handlers.handle_task_text(update, context)
    else:
        await update.message.reply_text(
            "🤔 Не понял ваше сообщение.\n\n"
            "Используйте кнопки меню или команды:\n"
            "/start - Основное меню\n"
            "/help - Помощь\n"
            "/running_list - Running List"
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов от inline кнопок"""
    query = update.callback_query
    data = query.data

    try:
        if data == "add_task" or data == "add_first_task":
            await running_handlers.add_task_start(update, context)
        elif data.startswith("priority_"):
            await running_handlers.handle_priority(update, context)
        elif data.startswith("day_"):
            await running_handlers.toggle_day(update, context)
        elif data == "save_task":
            await running_handlers.save_task(update, context)
        elif data == "refresh_list":
            await running_handlers.refresh_list(update, context)
        else:
            await query.answer("Неизвестная команда")
    except Exception as e:
        logger.error(f"❌ Ошибка в callback {data}: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        await query.answer("Произошла ошибка, попробуйте еще раз")


# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

def debug_database():
    """Проверяет подключение к базе и существующие таблицы"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("❌ DATABASE_URL не установлен - используем память")
            return

        logger.info(f"🔧 Проверка подключения к БД: {database_url}")

        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result]
            logger.info(f"📊 Существующие таблицы в БД ({len(tables)}): {tables}")

            if 'running_tasks' in tables:
                result = conn.execute(text("SELECT COUNT(*) as count FROM running_tasks"))
                count = result.scalar()
                logger.info(f"✅ running_tasks: {count} записей")
            else:
                logger.error("❌ Таблица running_tasks не найдена!")

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке БД: {e}")


def check_and_run_migrations():
    """Проверяет и применяет необходимые миграции"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("❌ DATABASE_URL не установлен, пропускаем миграции")
            return

        engine = create_engine(database_url)

        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'running_tasks'
                );
            """))
            table_exists = result.scalar()

            if not table_exists:
                logger.info("🔄 Создаем таблицу running_tasks...")
                conn.execute(text("""
                    CREATE TABLE running_tasks (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        task_text TEXT NOT NULL,
                        priority VARCHAR(20) DEFAULT 'medium',
                        days_of_week TEXT,
                        status_history TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.commit()
                logger.info("✅ Таблица running_tasks создана")
            else:
                logger.info("✅ Таблица running_tasks уже существует")

    except Exception as e:
        logger.error(f"❌ Ошибка при применении миграций: {e}")


# ОСНОВНАЯ ФУНКЦИЯ
def main():
    """Основная функция запуска бота"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК TVK ASSISTANT BOT - DEVELOPMENT")
        logger.info("=" * 60)

        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не установлен!")
            return

        logger.info("✅ TELEGRAM_BOT_TOKEN получен")

        # Отладочная информация о БД
        debug_database()

        # Проверяем миграции
        check_and_run_migrations()

        # Создаем приложение
        application = Application.builder().token(token).build()

        # Добавляем обработчики - теперь все функции определены
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("running_list", running_list_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback_query))

        # Запускаем бота
        logger.info("✅ Бот запущен и готов к работе")
        if storage_service.use_database:
            logger.info("💾 Используется база данных PostgreSQL")
        else:
            logger.info("🧠 Используется временное хранилище в памяти")

        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"💥 Критическая ошибка при запуске бота: {e}")


if __name__ == '__main__':
    main()