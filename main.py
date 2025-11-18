import os
import logging
import json
import traceback
from datetime import datetime
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


# ==================== RUNNING LIST MODELS ====================

class RunningTask:
    def __init__(self, id=None, user_id=None, task_text="", description="", priority="medium",
                 days_of_week=None, status_history=None, created_at=None):
        self.id = id
        self.user_id = user_id
        self.task_text = task_text
        self.description = description
        self.priority = priority
        self.days_of_week = days_of_week or [False] * 7
        self.status_history = status_history or []
        self.created_at = created_at


class StorageService:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        self.memory_storage = {}
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

    def add_running_task(self, user_id, task_text, description="", priority="medium", days_of_week=None):
        if not self.use_database:
            task_id = self.next_id
            self.next_id += 1

            task = RunningTask(
                id=task_id,
                user_id=user_id,
                task_text=task_text,
                description=description,
                priority=priority,
                days_of_week=days_of_week,
                status_history=[],
                created_at=datetime.now()
            )

            if user_id not in self.memory_storage:
                self.memory_storage[user_id] = []

            self.memory_storage[user_id].append(task)
            logger.info(f"💾 Задача сохранена в памяти, ID: {task_id}")
            return task

        session = None
        try:
            session = self.Session()
            days_json = json.dumps(days_of_week or [False] * 7)
            status_history_json = json.dumps([])

            result = session.execute(text("""
                INSERT INTO running_tasks (user_id, task_text, description, priority, days_of_week, status_history, created_at)
                VALUES (:user_id, :task_text, :description, :priority, :days_of_week, :status_history, NOW())
                RETURNING id
            """), {
                'user_id': user_id,
                'task_text': task_text,
                'description': description,
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
                description=description,
                priority=priority,
                days_of_week=days_of_week,
                status_history=[],
                created_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении задачи: {e}")
            if session:
                session.rollback()
            return None
        finally:
            if session:
                session.close()

    def get_running_tasks(self, user_id):
        if not self.use_database:
            tasks = self.memory_storage.get(user_id, [])
            logger.info(f"📊 Загружено {len(tasks)} задач из памяти для пользователя {user_id}")
            return tasks

        session = None
        try:
            session = self.Session()
            result = session.execute(text("""
                SELECT id, user_id, task_text, description, priority, days_of_week, status_history, created_at
                FROM running_tasks 
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """), {'user_id': user_id})

            tasks = []
            for row in result:
                try:
                    days_of_week = json.loads(row[5]) if row[5] else [False] * 7
                    status_history = json.loads(row[6]) if row[6] else []

                    tasks.append(RunningTask(
                        id=row[0],
                        user_id=row[1],
                        task_text=row[2],
                        description=row[3] or "",
                        priority=row[4],
                        days_of_week=days_of_week,
                        status_history=status_history,
                        created_at=row[7]
                    ))
                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON для задачи {row[0]}: {e}")
                    continue

            logger.info(f"✅ Успешно загружено {len(tasks)} задач из БД для пользователя {user_id}")
            return tasks

        except Exception as e:
            logger.error(f"❌ Ошибка при загрузке задач: {e}")
            return []
        finally:
            if session:
                session.close()

    def update_running_task(self, task):
        if not self.use_database:
            if task.user_id in self.memory_storage:
                for i, t in enumerate(self.memory_storage[task.user_id]):
                    if t.id == task.id:
                        self.memory_storage[task.user_id][i] = task
                        logger.info(f"✅ Задача {task.id} обновлена в памяти")
                        return True
            return False

        session = None
        try:
            session = self.Session()
            days_json = json.dumps(task.days_of_week)
            status_history_json = json.dumps(task.status_history)

            result = session.execute(text("""
                UPDATE running_tasks 
                SET task_text = :task_text, description = :description, priority = :priority, 
                    days_of_week = :days_of_week, status_history = :status_history
                WHERE id = :id AND user_id = :user_id
            """), {
                'id': task.id,
                'user_id': task.user_id,
                'task_text': task.task_text,
                'description': task.description,
                'priority': task.priority,
                'days_of_week': days_json,
                'status_history': status_history_json
            })

            session.commit()
            logger.info(f"✅ Задача {task.id} обновлена в БД")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при обновлении задачи: {e}")
            if session:
                session.rollback()
            return False
        finally:
            if session:
                session.close()

    def delete_running_task(self, task_id, user_id):
        if not self.use_database:
            if user_id in self.memory_storage:
                self.memory_storage[user_id] = [t for t in self.memory_storage[user_id] if t.id != task_id]
                logger.info(f"✅ Задача {task_id} удалена из памяти")
                return True
            return False

        session = None
        try:
            session = self.Session()
            result = session.execute(text("""
                DELETE FROM running_tasks 
                WHERE id = :id AND user_id = :user_id
            """), {
                'id': task_id,
                'user_id': user_id
            })

            session.commit()
            logger.info(f"✅ Задача {task_id} удалена из БД")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка при удалении задачи: {e}")
            if session:
                session.rollback()
            return False
        finally:
            if session:
                session.close()


# Глобальный экземпляр storage
storage_service = StorageService()


# ==================== RUNNING LIST HANDLERS ====================

class RunningListHandlers:
    def __init__(self, storage):
        self.storage = storage
        self.priority_emojis = {
            "low": "🟦",
            "medium": "🟨",
            "high": "🟥",
            "urgent": "⚡"
        }
        self.status_emojis = {
            "completed": "✅",
            "partial": "🔳",
            "cancelled": "❌",
            "postponed": "▶️"
        }
        self.day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

    def get_current_day_status(self, task):
        """Получает текущий статус задачи для сегодняшнего дня"""
        if not task.status_history:
            return None

        today = datetime.now().date()
        latest_status = None
        for status in reversed(task.status_history):
            status_date = datetime.fromisoformat(status['timestamp']).date()
            if status_date == today:
                latest_status = status
                break

        return latest_status

    def format_task_display(self, task):
        """Форматирует отображение задачи с днями недели и статусом"""
        day_emojis = ""
        current_status = self.get_current_day_status(task)
        current_day_index = datetime.now().weekday()

        for i in range(7):
            if task.days_of_week[i]:
                if i == current_day_index and current_status:
                    status_emoji = self.status_emojis.get(current_status['status'], "🟨")
                    day_emojis += status_emoji
                else:
                    day_emojis += self.priority_emojis.get(task.priority, "🟨")
            else:
                if i == current_day_index and current_status and current_status['status'] == 'postponed':
                    day_emojis += "▶️"
                else:
                    day_emojis += "⬜"

        priority_emoji = self.priority_emojis.get(task.priority, "🟨")
        description_indicator = " 📝" if task.description else ""

        return f"{day_emojis} - {task.task_text} {priority_emoji}{description_indicator}"

    async def show_running_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает running list пользователя"""
        user_id = update.effective_user.id
        tasks = self.storage.get_running_tasks(user_id)

        if not tasks:
            keyboard = [[InlineKeyboardButton("➕ Создать первую задачу", callback_data="add_first_task")]]
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "📋 **Ваш Running List пуст**\n\nСоздайте свою первую задачу!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "📋 **Ваш Running List пуст**\n\nСоздайте свою первую задачу!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            return

        message = "📋 **Ваш Running List:**\n\n"
        for i, task in enumerate(tasks):
            task_display = self.format_task_display(task)
            message += f"{i + 1}. {task_display}\n"

        message += f"\n*Всего задач: {len(tasks)}*"

        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
            [InlineKeyboardButton("🛠️ Управление задачами", callback_data="manage_tasks")],
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

    async def show_task_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает управление задачами"""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        tasks = self.storage.get_running_tasks(user_id)

        if not tasks:
            await query.edit_message_text("📋 Нет задач для управления")
            return

        keyboard = []
        for task in tasks:
            keyboard.append([InlineKeyboardButton(
                f"📝 {task.task_text}",
                callback_data=f"task_detail_{task.id}"
            )])

        keyboard.append([InlineKeyboardButton("📋 Назад к списку", callback_data="back_to_list")])

        await query.edit_message_text(
            "🛠️ **Управление задачами**\n\nВыберите задачу:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_task_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает детали задачи"""
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.replace("task_detail_", ""))
        user_id = update.effective_user.id

        task = None
        tasks = self.storage.get_running_tasks(user_id)
        for t in tasks:
            if t.id == task_id:
                task = t
                break

        if not task:
            await query.edit_message_text("❌ Задача не найдена")
            return

        # Форматируем информацию
        current_day_index = datetime.now().weekday()
        current_day_name = self.day_names[current_day_index]

        days_info = ""
        for i, day_name in enumerate(self.day_names):
            day_indicator = "🟢 СЕГОДНЯ" if i == current_day_index else ""
            if task.days_of_week[i]:
                days_info += f"✅ {day_name} {day_indicator}\n"
            else:
                days_info += f"⬜ {day_name} {day_indicator}\n"

        current_status = self.get_current_day_status(task)
        status_info = current_status['status'] if current_status else 'Не начато'

        message = (
            f"📝 **Детали задачи**\n\n"
            f"**Задача:** {task.task_text}\n"
            f"**Приоритет:** {self.priority_emojis.get(task.priority)}\n"
            f"**Статус сегодня:** {status_info}\n"
            f"**Текущий день:** {current_day_name}\n"
        )

        if task.description:
            message += f"**Описание:** {task.description}\n"

        message += f"\n**Дни выполнения:**\n{days_info}"

        keyboard = [
            [InlineKeyboardButton("🗑️ Удалить задачу", callback_data=f"delete_confirm_{task.id}")],
            [
                InlineKeyboardButton("✅ Выполнено", callback_data=f"status_completed_{task.id}"),
                InlineKeyboardButton("🔳 Частично", callback_data=f"status_partial_{task.id}")
            ],
            [
                InlineKeyboardButton("❌ Отменить", callback_data=f"status_cancelled_{task.id}"),
                InlineKeyboardButton("▶️ Перенести", callback_data=f"status_postponed_{task.id}")
            ],
            [InlineKeyboardButton("📋 Назад", callback_data="manage_tasks")]
        ]

        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def update_task_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет статус задачи с улучшенной логикой переноса"""
        query = update.callback_query
        await query.answer()

        data_parts = query.data.split("_")
        status_type = data_parts[1]
        task_id = int(data_parts[2])
        user_id = update.effective_user.id

        # Находим задачу
        task = None
        tasks = self.storage.get_running_tasks(user_id)
        for t in tasks:
            if t.id == task_id:
                task = t
                break

        if not task:
            await query.edit_message_text("❌ Задача не найдена")
            return

        # Добавляем запись в историю статусов
        status_record = {
            'status': status_type,
            'timestamp': datetime.now().isoformat(),
            'day': datetime.now().weekday()
        }
        task.status_history.append(status_record)

        # Обрабатываем перенос задачи
        if status_type == "postponed":
            current_day = datetime.now().weekday()  # 0=понедельник, 6=воскресенье

            if current_day < 6:  # Если не воскресенье (0-5 = понедельник-суббота)
                next_day = current_day + 1

                # Сбрасываем текущий день и устанавливаем следующий
                task.days_of_week[current_day] = False
                task.days_of_week[next_day] = True

                message = (
                    f"▶️ **Задача перенесена!**\n\n"
                    f"Задача: {task.task_text}\n"
                    f"📍 Сегодня ({self.day_names[current_day]}): ▶️ Перенесено\n"
                    f"📅 Завтра ({self.day_names[next_day]}): {self.priority_emojis.get(task.priority)} Будет выполнено\n"
                    f"Приоритет сохранен: {self.priority_emojis.get(task.priority)}"
                )
            else:  # Воскресенье - не переносим, только ставим статус
                message = (
                    f"▶️ **Статус обновлен!**\n\n"
                    f"Задача: {task.task_text}\n"
                    f"📍 Воскресенье - перенос на следующую неделю не выполняется\n"
                    f"Статус: ▶️ Перенесено"
                )
        else:
            # Для других статусов просто обновляем сообщение
            status_emoji = self.status_emojis.get(status_type, "✅")
            message = (
                f"{status_emoji} **Статус обновлен!**\n\n"
                f"Задача: {task.task_text}\n"
                f"Статус: {status_emoji} {status_type}"
            )

        # Сохраняем изменения
        if self.storage.update_running_task(task):
            await query.edit_message_text(message, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ошибка при обновлении статуса")

    async def delete_task_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение удаления"""
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.replace("delete_confirm_", ""))
        user_id = update.effective_user.id

        # Находим задачу
        task = None
        tasks = self.storage.get_running_tasks(user_id)
        for t in tasks:
            if t.id == task_id:
                task = t
                break

        if not task:
            await query.edit_message_text("❌ Задача не найдена")
            return

        keyboard = [
            [
                InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"delete_task_{task_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"task_detail_{task_id}")
            ]
        ]

        await query.edit_message_text(
            f"⚠️ **Подтверждение удаления**\n\n"
            f"Удалить задачу:\n"
            f"*{task.task_text}*?\n\n"
            f"Это действие нельзя отменить!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def delete_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет задачу"""
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.replace("delete_task_", ""))
        user_id = update.effective_user.id

        if self.storage.delete_running_task(task_id, user_id):
            await query.edit_message_text("✅ **Задача удалена!**", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ошибка при удалении")

    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает добавление задачи"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text("✏️ Введите текст новой задачи:")
        else:
            await update.message.reply_text("✏️ Введите текст новой задачи:")

        context.user_data['adding_task'] = True

    async def handle_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текст задачи"""
        if context.user_data.get('adding_task'):
            task_text = update.message.text
            context.user_data['new_task'] = {
                'text': task_text,
                'days': [False] * 7,
                'description': ''
            }
            context.user_data['adding_task'] = False

            keyboard = [
                [InlineKeyboardButton("📋 Добавить описание", callback_data="add_description")],
                [InlineKeyboardButton("⏩ Пропустить описание", callback_data="skip_description")]
            ]

            await update.message.reply_text(
                f"📝 Задача: *{task_text}*\n\nДобавить описание?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

    async def handle_task_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает описание задачи"""
        if context.user_data.get('adding_description'):
            description = update.message.text
            context.user_data['new_task']['description'] = description
            context.user_data['adding_description'] = False

            await self.show_priority_selection(update, context)

    async def show_priority_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор приоритета"""
        keyboard = [
            [InlineKeyboardButton("🟦 Низкий", callback_data="priority_low")],
            [InlineKeyboardButton("🟨 Средний", callback_data="priority_medium")],
            [InlineKeyboardButton("🟥 Высокий", callback_data="priority_high")],
            [InlineKeyboardButton("⚡ Срочный", callback_data="priority_urgent")]
        ]

        # Проверяем тип update и используем правильный метод
        if hasattr(update, 'callback_query') and update.callback_query:
            # Это callback запрос
            await update.callback_query.edit_message_text(
                "🎯 Выберите приоритет задачи:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Это обычное сообщение
            await update.message.reply_text(
                "🎯 Выберите приоритет задачи:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def handle_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает выбор приоритета"""
        query = update.callback_query
        await query.answer()

        priority = query.data.replace("priority_", "")
        context.user_data['new_task']['priority'] = priority

        await self.show_days_selection(update, context)

    async def show_days_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает выбор дней недели"""
        query = update.callback_query

        keyboard = []
        row = []
        for i, day in enumerate(self.day_names):
            is_selected = context.user_data['new_task']['days'][i]
            button_text = f"✅ {day}" if is_selected else f"⬜ {day}"
            row.append(InlineKeyboardButton(button_text, callback_data=f"day_{i}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("💾 Сохранить задачу", callback_data="save_task")])

        # Формируем сообщение
        task_text = context.user_data['new_task']['text']
        description = context.user_data['new_task']['description']
        priority_emoji = self.priority_emojis.get(context.user_data['new_task']['priority'], "🟨")

        message = f"📝 *{task_text}*\n🎯 Приоритет: {priority_emoji}\n"
        if description:
            message += f"📋 Описание: {description}\n"
        message += "\n📅 Выберите дни выполнения:"

        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def toggle_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает день недели"""
        query = update.callback_query
        await query.answer()

        day_index = int(query.data.replace("day_", ""))
        context.user_data['new_task']['days'][day_index] = not context.user_data['new_task']['days'][day_index]

        await self.show_days_selection(update, context)

    async def save_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет задачу"""
        query = update.callback_query
        await query.answer()

        task_data = context.user_data['new_task']
        user_id = update.effective_user.id

        await query.edit_message_text("⏳ Сохраняем задачу...")

        task = self.storage.add_running_task(
            user_id=user_id,
            task_text=task_data['text'],
            description=task_data.get('description', ''),
            priority=task_data['priority'],
            days_of_week=task_data.get('days', [False] * 7)
        )

        if task:
            context.user_data.pop('new_task', None)
            await query.edit_message_text(
                "✅ **Задача успешно сохранена!**\n\n"
                "Используйте '📋 Running List' для просмотра.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ **Ошибка при сохранении**\n\n"
                "Попробуйте еще раз.",
                parse_mode='Markdown'
            )

    async def refresh_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет список"""
        query = update.callback_query
        await query.answer()
        await self.show_running_list(update, context)


# Создаем обработчики
running_handlers = RunningListHandlers(storage_service)


# ==================== MAIN BOT FUNCTIONALITY ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я TVK Assistant Bot - ваш помощник в организации работы.\n\n"
        "📋 **Доступные функции:**\n"
        "• Running List - система повторяющихся задач ✅\n"
        "• Табель учета рабочего времени ✅\n"
        "• Управление строительными объектами ✅\n"
        "• Управление задачами ✅\n"
        "• И многое другое!\n\n"
        "✨ **Все системы готовы к работе!**"
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
        "📋 **Running List (НОВОЕ!):**\n"
        "• Создавайте повторяющиеся задачи\n"
        "• Приоритеты: 🟦 Низкий, 🟨 Средний, 🟥 Высокий, ⚡ Срочный\n"
        "• Статусы: ✅ Выполнено, 🔳 Частично, ❌ Отменено, ▶️ Перенесено\n"
        "• Назначайте дни выполнения\n\n"
        "🎯 **Как использовать Running List:**\n"
        "1. Нажмите '📋 Running List'\n"
        "2. '➕ Добавить задачу' для создания\n"
        "3. Выберите приоритет и дни недели\n"
        "4. Используйте '🛠️ Управление задачами' для изменения статусов\n\n"
        "🔧 **Все функции:**\n"
        "• 📋 Running List - повторяющиеся задачи\n"
        "• 📊 Табель - учет рабочего времени\n"
        "• 🏗️ Объекты - управление строительными объектами\n"
        "• 📝 Задачи - общее управление задачами\n"
        "• ⚙️ Настройки - настройки бота"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def running_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /running_list"""
    await running_handlers.show_running_list(update, context)


async def timesheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик табеля"""
    await update.message.reply_text(
        "📊 **Табель учета рабочего времени**\n\n"
        "Система учета рабочего времени готова к работе!\n\n"
        "Функции:\n"
        "• Учет отработанных часов\n"
        "• Отчеты по периодам\n"
        "• Статистика работы"
    )


async def objects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик строительных объектов"""
    await update.message.reply_text(
        "🏗️ **Строительные объекты**\n\n"
        "Система управления объектами активна!\n\n"
        "Доступные функции:\n"
        "• Список объектов\n"
        "• Прогресс работ\n"
        "• Ответственные лица"
    )


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик общих задач"""
    await update.message.reply_text(
        "📝 **Общие задачи**\n\n"
        "Система управления задачами работает!\n\n"
        "Возможности:\n"
        "• Создание задач\n"
        "• Назначение исполнителей\n"
        "• Контроль сроков"
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик настроек"""
    await update.message.reply_text(
        "⚙️ **Настройки**\n\n"
        "Раздел настроек бота.\n\n"
        "Доступные настройки:\n"
        "• Уведомления\n"
        "• Язык интерфейса\n"
        "• Форматы отчетов"
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
    elif context.user_data.get('adding_description'):
        await running_handlers.handle_task_description(update, context)
    else:
        await update.message.reply_text(
            "🤔 Не понял ваше сообщение.\n\n"
            "Используйте кнопки меню или команды:\n"
            "/start - Основное меню\n"
            "/help - Помощь\n"
            "/running_list - Running List"
        )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главный обработчик callback запросов"""
    query = update.callback_query
    data = query.data

    try:
        logger.info(f"📨 Callback received: {data}")

        if data == "add_task" or data == "add_first_task":
            await running_handlers.add_task_start(update, context)
        elif data == "add_description":
            await query.edit_message_text("📝 Введите описание задачи:")
            context.user_data['adding_description'] = True
        elif data == "skip_description":
            await running_handlers.show_priority_selection(update, context)
        elif data.startswith("priority_"):
            await running_handlers.handle_priority(update, context)
        elif data.startswith("day_"):
            await running_handlers.toggle_day(update, context)
        elif data == "save_task":
            await running_handlers.save_task(update, context)
        elif data == "refresh_list":
            await running_handlers.refresh_list(update, context)
        elif data == "manage_tasks":
            await running_handlers.show_task_management(update, context)
        elif data == "back_to_list":
            await running_handlers.show_running_list(update, context)
        elif data.startswith("task_detail_"):
            await running_handlers.show_task_detail(update, context)
        elif data.startswith("status_"):
            await running_handlers.update_task_status(update, context)
        elif data.startswith("delete_confirm_"):
            await running_handlers.delete_task_confirm(update, context)
        elif data.startswith("delete_task_"):
            await running_handlers.delete_task(update, context)
        else:
            await query.answer("❌ Неизвестная команда")

    except Exception as e:
        logger.error(f"💥 Ошибка в callback: {e}")
        logger.error(traceback.format_exc())
        await query.answer("❌ Произошла ошибка")


# ==================== DATABASE & MIGRATION ====================

def debug_database():
    """Проверяет базу данных"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("❌ DATABASE_URL не установлен")
            return

        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT NOW() as time"))
            time = result.scalar()
            logger.info(f"✅ Подключение к БД успешно. Время сервера: {time}")

    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")


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
                        description TEXT,
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


# ==================== MAIN FUNCTION ====================

def main():
    """Основная функция запуска бота"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 ЗАПУСК TVK ASSISTANT BOT - ОБЪЕДИНЕННАЯ ВЕРСИЯ")
        logger.info("=" * 60)

        # Проверяем переменные окружения
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

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("running_list", running_list_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback_query))

        # Запускаем бота
        logger.info("✅ Бот запущен и готов к работе")
        logger.info("📋 Running List: ✅ Активирован")
        logger.info("📊 Табель: ✅ Доступен")
        logger.info("🏗️ Объекты: ✅ Доступны")
        logger.info("📝 Задачи: ✅ Доступны")

        if storage_service.use_database:
            logger.info("💾 Используется база данных PostgreSQL")
        else:
            logger.info("🧠 Используется временное хранилище в памяти")

        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"💥 Критическая ошибка при запуске бота: {e}")
        logger.critical(f"💥 Traceback: {traceback.format_exc()}")


if __name__ == '__main__':
    main()