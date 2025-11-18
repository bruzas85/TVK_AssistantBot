import os
import logging
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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
        if self.database_url:
            self.engine = create_engine(self.database_url)
            self.Session = sessionmaker(bind=self.engine)
        else:
            self.engine = None
            self.Session = None

    def add_running_task(self, user_id, task_text, priority="medium", days_of_week=None):
        if not self.engine:
            return RunningTask(id=1, user_id=user_id, task_text=task_text, priority=priority)

        try:
            session = self.Session()
            days_json = json.dumps(days_of_week or [False] * 7)

            result = session.execute(text("""
                INSERT INTO running_tasks (user_id, task_text, priority, days_of_week, status_history)
                VALUES (:user_id, :task_text, :priority, :days_of_week, :status_history)
                RETURNING id
            """), {
                'user_id': user_id,
                'task_text': task_text,
                'priority': priority,
                'days_of_week': days_json,
                'status_history': json.dumps([])
            })

            task_id = result.scalar()
            session.commit()

            return RunningTask(
                id=task_id,
                user_id=user_id,
                task_text=task_text,
                priority=priority,
                days_of_week=days_of_week,
                status_history=[]
            )
        except Exception as e:
            logger.error(f"Ошибка при добавлении задачи: {e}")
            return None

    def get_running_tasks(self, user_id):
        if not self.engine:
            return []

        try:
            session = self.Session()
            result = session.execute(text("""
                SELECT id, user_id, task_text, priority, days_of_week, status_history, created_at
                FROM running_tasks 
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """), {'user_id': user_id})

            tasks = []
            for row in result:
                tasks.append(RunningTask(
                    id=row[0],
                    user_id=row[1],
                    task_text=row[2],
                    priority=row[3],
                    days_of_week=json.loads(row[4]) if row[4] else [False] * 7,
                    status_history=json.loads(row[5]) if row[5] else [],
                    created_at=row[6]
                ))
            return tasks
        except Exception as e:
            logger.error(f"Ошибка при получении задач: {e}")
            return []


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
        tasks = self.storage.get_running_tasks(user_id)

        if not tasks:
            # Если задач нет, предлагаем создать первую
            keyboard = [
                [InlineKeyboardButton("➕ Создать первую задачу", callback_data="add_first_task")]
            ]
            await update.message.reply_text(
                "📋 **Ваш Running List пуст**\n\n"
                "Создайте свою первую задачу для отслеживания!",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return

        # Показываем список задач
        message = "📋 **Ваш Running List:**\n\n"
        for i, task in enumerate(tasks):
            task_display = self.format_task_display(task)
            message += f"{i + 1}. {task_display}\n"

        # Клавиатура для управления
        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
            [InlineKeyboardButton("🔄 Обновить", callback_data="refresh_list")]
        ]

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
            await query.edit_message_text("Введите текст новой задачи:")
        else:
            await update.message.reply_text("Введите текст новой задачи:")

        # Сохраняем состояние в context
        context.user_data['adding_task'] = True

    async def handle_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текст задачи и запрашивает приоритет"""
        if not context.user_data.get('adding_task'):
            return

        task_text = update.message.text
        context.user_data['new_task'] = {'text': task_text}
        context.user_data['adding_task'] = False

        # Клавиатура для выбора приоритета
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
            f"Задача: *{task_text}*\n\nВыберите приоритет:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def handle_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор приоритета"""
        query = update.callback_query
        await query.answer()

        priority = query.data.replace("priority_", "")
        context.user_data['new_task']['priority'] = priority

        # Создаем клавиатуру для выбора дней недели
        keyboard = []
        row = []
        for i, day in enumerate(self.day_names):
            row.append(InlineKeyboardButton(day, callback_data=f"day_{i}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("✅ Сохранить задачу", callback_data="save_task")])

        priority_emoji = self.priority_emojis.get(priority, "🟨")
        await query.edit_message_text(
            f"Задача: *{context.user_data['new_task']['text']}*\n"
            f"Приоритет: {priority_emoji}\n\n"
            "Выберите дни недели для выполнения (нажмите на день чтобы выбрать/отменить):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def toggle_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает выбор дня недели"""
        query = update.callback_query
        await query.answer()

        day_index = int(query.data.replace("day_", ""))

        # Инициализируем дни если нужно
        if 'days' not in context.user_data['new_task']:
            context.user_data['new_task']['days'] = [False] * 7

        # Переключаем состояние дня
        context.user_data['new_task']['days'][day_index] = not context.user_data['new_task']['days'][day_index]

        # Обновляем сообщение с текущим состоянием
        days_status = ""
        for i, day_name in enumerate(self.day_names):
            if context.user_data['new_task']['days'][i]:
                days_status += f"✅ {day_name}\n"
            else:
                days_status += f"⬜ {day_name}\n"

        priority_emoji = self.priority_emojis.get(context.user_data['new_task']['priority'], "🟨")

        keyboard = []
        row = []
        for i, day in enumerate(self.day_names):
            # Показываем выбранные дни с галочкой
            button_text = f"✅ {day}" if context.user_data['new_task']['days'][i] else day
            row.append(InlineKeyboardButton(button_text, callback_data=f"day_{i}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("💾 Сохранить задачу", callback_data="save_task")])

        await query.edit_message_text(
            f"Задача: *{context.user_data['new_task']['text']}*\n"
            f"Приоритет: {priority_emoji}\n\n"
            f"Выбранные дни:\n{days_status}\n"
            "Нажмите на день чтобы выбрать/отменить:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def save_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет задачу"""
        query = update.callback_query
        await query.answer()

        task_data = context.user_data['new_task']
        user_id = update.effective_user.id

        # Сохраняем задачу
        task = self.storage.add_running_task(
            user_id=user_id,
            task_text=task_data['text'],
            priority=task_data['priority'],
            days_of_week=task_data.get('days', [False] * 7)
        )

        if task:
            # Очищаем временные данные
            context.user_data.pop('new_task', None)
            context.user_data.pop('adding_task', None)

            await query.edit_message_text(
                "✅ Задача успешно добавлена в Running List!\n\n"
                "Используйте /running_list для просмотра всех задач."
            )
        else:
            await query.edit_message_text(
                "❌ Ошибка при сохранении задачи. Попробуйте еще раз."
            )

    async def refresh_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет список задач"""
        query = update.callback_query
        await query.answer()
        await self.show_running_list(update, context)


# Создаем экземпляр обработчиков
running_handlers = RunningListHandlers(storage_service)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я TVK Assistant Bot - твой помощник в организации задач.\n\n"
        "📋 **Running List система АКТИВНА!**\n"
        "Создавайте задачи, назначайте приоритеты и дни выполнения.\n\n"
        "✨ **Новый функционал из ветки development!**"
    )

    keyboard = [
        [KeyboardButton("📋 Running List"), KeyboardButton("ℹ️ Помощь")],
        [KeyboardButton("➕ Добавить задачу")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🆘 **Помощь по TVK Assistant Bot**\n\n"
        "📋 **Running List система:**\n"
        "• Создавайте повторяющиеся задачи\n"
        "• Приоритеты: 🟦 Низкий, 🟨 Средний, 🟥 Высокий, ⚡ Срочный\n"
        "• Назначайте дни выполнения\n"
        "• Отслеживайте прогресс\n\n"
        "🎯 **Как использовать:**\n"
        "1. Нажмите '📋 Running List' для просмотра\n"
        "2. Нажмите '➕ Добавить задачу' для создания\n"
        "3. Выберите приоритет и дни недели\n"
        "4. Отслеживайте выполнение\n\n"
        "🔧 **Команды:**\n"
        "/start - Перезапустить бота\n"
        "/help - Показать справку\n"
        "/running_list - Показать список задач"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def running_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /running_list"""
    await running_handlers.show_running_list(update, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text

    if text == "📋 Running List":
        await running_handlers.show_running_list(update, context)
    elif text == "➕ Добавить задачу":
        await running_handlers.add_task_start(update, context)
    elif text == "ℹ️ Помощь":
        await help_command(update, context)
    elif context.user_data.get('adding_task'):
        # Если пользователь в процессе добавления задачи
        await running_handlers.handle_task_text(update, context)
    else:
        await update.message.reply_text(
            "🤔 Не понял ваше сообщение.\n"
            "Используйте кнопки или команды:\n"
            "/start - Перезапуск\n"
            "/help - Помощь\n"
            "/running_list - Список задач"
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback запросов от inline кнопок"""
    query = update.callback_query
    data = query.data

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


def check_and_run_migrations():
    """Проверяет и применяет необходимые миграции"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("DATABASE_URL не установлен, пропускаем миграции")
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
                logger.info("Создаем таблицу running_tasks...")
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

    except Exception as e:
        logger.error(f"Ошибка при применении миграций: {e}")


def main():
    """Основная функция запуска бота"""
    try:
        logger.info("Запуск TVK Assistant Bot...")

        # Проверяем переменные окружения
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN не установлен!")
            return

        # Проверяем миграции
        check_and_run_migrations()

        # Создаем приложение
        application = Application.builder().token(token).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("running_list", running_list_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback_query))

        # Запускаем бота
        logger.info("✅ Бот запущен и готов к работе")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")


if __name__ == '__main__':
    main()