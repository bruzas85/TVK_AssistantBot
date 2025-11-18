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
                VALUES (:user_id, :task_text, :description, :priority, :days_of_week, :status_history, :created_at)
                RETURNING id
            """), {
                'user_id': user_id,
                'task_text': task_text,
                'description': description,
                'priority': priority,
                'days_of_week': days_json,
                'status_history': status_history_json,
                'created_at': datetime.now()
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
            # Обновляем в памяти
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
        for status in reversed(task.status_history):
            status_date = datetime.fromisoformat(status['timestamp']).date()
            if status_date == today:
                return status
        return None

    def format_task_display(self, task):
        """Форматирует отображение задачи с днями недели и статусом"""
        day_emojis = ""
        current_status = self.get_current_day_status(task)
        current_day_index = datetime.now().weekday()

        for i in range(7):
            if task.days_of_week[i]:
                # Если это сегодня и есть статус
                if i == current_day_index and current_status:
                    day_emojis += self.status_emojis.get(current_status['status'], "🟨")
                else:
                    day_emojis += self.priority_emojis.get(task.priority, "🟨")
            else:
                day_emojis += "⬜"

        priority_emoji = self.priority_emojis.get(task.priority, "🟨")

        # Добавляем индикатор описания если оно есть
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
                    "📋 **Ваш Running List пуст**\n\nСоздайте свою первую задачу для отслеживания!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "📋 **Ваш Running List пуст**\n\nСоздайте свою первую задачу для отслеживания!",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            return

        message = "📋 **Ваш Running List:**\n\n"
        for i, task in enumerate(tasks):
            task_display = self.format_task_display(task)
            message += f"{i + 1}. {task_display}\n"

        message += f"\n*Всего задач: {len(tasks)}*"

        if not self.storage.use_database:
            message += f"\n💡 *Задачи хранятся в памяти (перезагрузка очистит их)*"

        keyboard = [
            [InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")],
            [InlineKeyboardButton("📝 Управление задачами", callback_data="manage_tasks")],
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
            await query.edit_message_text(
                "📋 **Нет задач для управления**\n\nСоздайте сначала задачу!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("➕ Создать задачу", callback_data="add_task")]])
            )
            return

        keyboard = []
        for task in tasks:
            keyboard.append([InlineKeyboardButton(
                f"📝 {task.task_text}",
                callback_data=f"task_detail_{task.id}"
            )])

        keyboard.append([InlineKeyboardButton("📋 Назад к списку", callback_data="back_to_list")])

        await query.edit_message_text(
            "🛠️ **Управление задачами**\n\nВыберите задачу для редактирования:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def show_task_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает детали задачи и управление"""
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

        # Форматируем информацию о задаче
        days_info = ""
        for i, day_name in enumerate(self.day_names):
            if task.days_of_week[i]:
                days_info += f"✅ {day_name}\n"
            else:
                days_info += f"⬜ {day_name}\n"

        current_status = self.get_current_day_status(task)
        status_info = f"✅ Сегодня: {current_status['status'] if current_status else 'Не начато'}"

        message = (
            f"📝 **Детали задачи**\n\n"
            f"**Задача:** {task.task_text}\n"
            f"**Приоритет:** {self.priority_emojis.get(task.priority)}\n"
            f"**Статус:** {status_info}\n"
        )

        if task.description:
            message += f"**Описание:** {task.description}\n"

        message += f"\n**Дни выполнения:**\n{days_info}"

        keyboard = [
            [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_task_{task.id}")],
            [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_confirm_{task.id}")],
            [
                InlineKeyboardButton("✅ Выполнено", callback_data=f"status_completed_{task.id}"),
                InlineKeyboardButton("🔳 Частично", callback_data=f"status_partial_{task.id}")
            ],
            [
                InlineKeyboardButton("❌ Отменить", callback_data=f"status_cancelled_{task.id}"),
                InlineKeyboardButton("▶️ Перенести", callback_data=f"status_postponed_{task.id}")
            ],
            [InlineKeyboardButton("📋 Назад к управлению", callback_data="manage_tasks")]
        ]

        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def update_task_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет статус задачи"""
        query = update.callback_query
        await query.answer()

        data_parts = query.data.split("_")
        status_type = data_parts[1]  # completed, partial, cancelled, postponed
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

        # Если задача переносится, перемещаем на следующий день
        if status_type == "postponed":
            next_day = (datetime.now().weekday() + 1) % 7
            task.days_of_week[next_day] = True

        # Сохраняем изменения
        if self.storage.update_running_task(task):
            status_emoji = self.status_emojis.get(status_type, "✅")
            await query.edit_message_text(
                f"{status_emoji} *Статус задачи обновлен!*\n\n"
                f"Задача: {task.task_text}\n"
                f"Новый статус: {status_emoji} {status_type}",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("❌ Ошибка при обновлении статуса")

    async def delete_task_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Подтверждение удаления задачи"""
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.replace("delete_confirm_", ""))
        user_id = update.effective_user.id

        # Находим задачу для показа названия
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
            f"Вы уверены, что хотите удалить задачу?\n"
            f"*{task.task_text}*\n\n"
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
            await query.edit_message_text("✅ *Задача успешно удалена!*", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Ошибка при удалении задачи")

    async def edit_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает редактирование задачи"""
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.replace("edit_task_", ""))
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

        # Сохраняем задачу в context для редактирования
        context.user_data['editing_task'] = task
        context.user_data['edit_step'] = 'text'

        keyboard = [
            [InlineKeyboardButton("📝 Изменить текст", callback_data="edit_text")],
            [InlineKeyboardButton("📋 Изменить описание", callback_data="edit_description")],
            [InlineKeyboardButton("🎯 Изменить приоритет", callback_data="edit_priority")],
            [InlineKeyboardButton("📅 Изменить дни", callback_data="edit_days")],
            [InlineKeyboardButton("📋 Назад", callback_data=f"task_detail_{task.id}")]
        ]

        await query.edit_message_text(
            f"✏️ **Редактирование задачи**\n\n"
            f"*{task.task_text}*\n\n"
            f"Что вы хотите изменить?",
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
        context.user_data['new_task'] = {'days': [False] * 7, 'description': ''}

    async def handle_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает текст задачи"""
        if context.user_data.get('adding_task'):
            task_text = update.message.text
            context.user_data['new_task']['text'] = task_text
            context.user_data['adding_task'] = False

            await update.message.reply_text(
                f"📝 Задача: *{task_text}*\n\n"
                "Хотите добавить описание к задаче?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Да, добавить описание", callback_data="add_description")],
                    [InlineKeyboardButton("⏩ Пропустить", callback_data="skip_description")]
                ]),
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

        if hasattr(update, 'message'):
            await update.message.reply_text(
                "🎯 Выберите приоритет задачи:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.callback_query.edit_message_text(
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
        description_text = f"\n📝 Описание: {context.user_data['new_task']['description']}" if \
        context.user_data['new_task']['description'] else ""

        message = (
            f"📝 Задача: *{context.user_data['new_task']['text']}*{description_text}\n"
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
            context.user_data.pop('adding_task', None)

            storage_info = ""
            if not self.storage.use_database:
                storage_info = "\n\n💡 *Задачи хранятся в памяти*"

            await query.edit_message_text(
                f"✅ *Задача успешно добавлена в Running List!*{storage_info}\n\n"
                "Используйте кнопку '📋 Running List' для просмотра всех задач.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ *Ошибка при сохранении задачи.*\n\n"
                "Попробуйте еще раз.",
                parse_mode='Markdown'
            )

    async def refresh_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет список задач"""
        query = update.callback_query
        await query.answer()
        await self.show_running_list(update, context)


# Создаем экземпляр обработчиков
running_handlers = RunningListHandlers(storage_service)


# ОСНОВНЫЕ ФУНКЦИИ БОТА
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    help_text = (
        "🆘 **Помощь по TVK Assistant Bot**\n\n"
        "📋 **Running List (ОБНОВЛЕН!):**\n"
        "• Создавайте задачи с описанием\n"
        "• Приоритеты: 🟦 Низкий, 🟨 Средний, 🟥 Высокий, ⚡ Срочный\n"
        "• Назначайте дни выполнения\n"
        "• Управляйте статусами: ✅ Выполнено, 🔳 Частично, ❌ Отменено, ▶️ Перенесено\n\n"
        "🎯 **Как использовать:**\n"
        "1. '📋 Running List' - просмотр задач\n"
        "2. '📝 Управление задачами' - редактирование\n"
        "3. Выбирайте задачи для изменения статуса\n\n"
        "🔧 **Статус функций:**\n"
        "• 📋 Running List - ✅ ОБНОВЛЕН\n"
        "• 📊 Табель - ⏳ В РАЗРАБОТКЕ\n"
        "• 🏗️ Объекты - ⏳ В РАЗРАБОТКЕ\n"
        "• 📝 Задачи - ⏳ В РАЗРАБОТКЕ\n"
        "• ⚙️ Настройки - ⏳ В РАЗРАБОТКЕ"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def running_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await running_handlers.show_running_list(update, context)


async def timesheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 **Табель учета рабочего времени**\n\n⏳ В разработке...")


async def objects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏗️ **Строительные объекты**\n\n⏳ В разработке...")


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 **Общие задачи**\n\n⏳ В разработке...")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ **Настройки**\n\n⏳ В разработке...")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text("🤔 Не понял ваше сообщение. Используйте кнопки меню.")


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    try:
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
        elif data.startswith("edit_task_"):
            await running_handlers.edit_task_start(update, context)
        else:
            await query.answer("Неизвестная команда")
    except Exception as e:
        logger.error(f"❌ Ошибка в callback {data}: {e}")