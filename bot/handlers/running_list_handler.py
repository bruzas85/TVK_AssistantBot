from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RunningListHandlers:
    def __init__(self, storage_service):
        self.storage = storage_service
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

    def get_day_emoji(self, task, day_index, current_weekday=None):
        """Возвращает эмодзи для дня недели"""
        if not task.days_of_week[day_index]:
            return "⬜"

        # Если это текущий день и есть статус
        if current_weekday == day_index and task.status_history:
            latest_status = task.status_history[-1]
            status_day = latest_status.get('day')
            status_type = latest_status.get('status')

            if status_day == day_index and status_type in self.status_emojis:
                return self.status_emojis[status_type]

        return self.priority_emojis.get(task.priority, "🟨")

    def format_task_display(self, task, current_weekday=None):
        """Форматирует отображение задачи"""
        day_emojis = "".join([self.get_day_emoji(task, i, current_weekday) for i in range(7)])
        priority_emoji = self.priority_emojis.get(task.priority, "🟨")

        return f"{day_emojis} - {task.task_text} {priority_emoji}"

    async def show_running_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает running list пользователя"""
        user_id = update.effective_user.id
        tasks = self.storage.get_running_tasks(user_id)

        if not tasks:
            await update.message.reply_text("Ваш running list пуст. Добавьте первую задачу!")
            return

        current_weekday = datetime.now().weekday()  # 0 = Monday, 6 = Sunday

        message = "📋 **Ваш Running List:**\n\n"
        keyboard = []

        for i, task in enumerate(tasks):
            task_display = self.format_task_display(task, current_weekday)
            message += f"{i + 1}. {task_display}\n"
            keyboard.append([InlineKeyboardButton(
                f"{i + 1}. {task.task_text}",
                callback_data=f"task_detail_{task.id}"
            )])

        keyboard.append([InlineKeyboardButton("➕ Добавить задачу", callback_data="add_task")])

        await update.message.reply_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    async def add_task_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начинает процесс добавления задачи"""
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            "Введите текст новой задачи:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]])
        )

    async def add_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получает текст задачи и запрашивает приоритет"""
        task_text = update.message.text
        context.user_data['new_task'] = {'text': task_text}

        keyboard = [
            [
                InlineKeyboardButton("🟦 Низкий", callback_data="priority_low"),
                InlineKeyboardButton("🟨 Средний", callback_data="priority_medium")
            ],
            [
                InlineKeyboardButton("🟥 Высокий", callback_data="priority_high"),
                InlineKeyboardButton("⚡ Срочный", callback_data="priority_urgent")
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]
        ]

        await update.message.reply_text(
            f"Задача: {task_text}\nВыберите приоритет:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def set_task_priority(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Устанавливает приоритет и запрашивает дни недели"""
        query = update.callback_query
        await query.answer()

        priority = query.data.replace("priority_", "")
        context.user_data['new_task']['priority'] = priority

        # Показываем выбор дней недели
        keyboard = []
        days_row = []

        for i, day in enumerate(self.day_names):
            days_row.append(InlineKeyboardButton(
                f"{day} ✅" if context.user_data['new_task'].get('days', {}).get(str(i)) else day,
                callback_data=f"toggle_day_{i}"
            ))
            if len(days_row) == 3:  # 3 дня в строке
                keyboard.append(days_row)
                days_row = []

        if days_row:  # Добавляем оставшиеся дни
            keyboard.append(days_row)

        keyboard.extend([
            [InlineKeyboardButton("✅ Сохранить задачу", callback_data="save_task")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_add")]
        ])

        priority_emoji = self.priority_emojis.get(priority, "🟨")
        await query.edit_message_text(
            f"Задача: {context.user_data['new_task']['text']}\n"
            f"Приоритет: {priority_emoji}\n\n"
            f"Выберите дни недели для задачи:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def toggle_day(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Переключает выбор дня недели"""
        query = update.callback_query
        await query.answer()

        day_index = int(query.data.replace("toggle_day_", ""))

        if 'days' not in context.user_data['new_task']:
            context.user_data['new_task']['days'] = {}

        # Переключаем состояние дня
        current_state = context.user_data['new_task']['days'].get(str(day_index), False)
        context.user_data['new_task']['days'][str(day_index)] = not current_state

        # Обновляем клавиатуру
        await self.set_task_priority(update, context)

    async def save_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохраняет новую задачу"""
        query = update.callback_query
        await query.answer()

        task_data = context.user_data['new_task']
        days_of_week = [task_data.get('days', {}).get(str(i), False) for i in range(7)]

        # Создаем задачу
        task = self.storage.add_running_task(
            user_id=update.effective_user.id,
            task_text=task_data['text'],
            priority=task_data['priority']
        )

        # Устанавливаем дни недели
        task.days_of_week = days_of_week
        self.storage.update_running_task(task)

        # Очищаем временные данные
        context.user_data.pop('new_task', None)

        await query.edit_message_text(
            "✅ Задача успешно добавлена в running list!"
        )

        # Показываем обновленный список
        await self.show_running_list_after_save(update, context)

    async def show_running_list_after_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает running list после сохранения"""
        # Здесь можно отправить сообщение с обновленным списком
        pass

    async def task_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает детали задачи"""
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.replace("task_detail_", ""))
        task = self.storage.get_running_task(task_id)

        if not task:
            await query.edit_message_text("Задача не найдена")
            return

        current_weekday = datetime.now().weekday()
        task_display = self.format_task_display(task, current_weekday)

        # Формируем информацию о днях
        days_info = ""
        for i, day_name in enumerate(self.day_names):
            emoji = self.get_day_emoji(task, i, current_weekday)
            days_info += f"{day_name}: {emoji}\n"

        message = (
            f"📝 **Детали задачи:**\n\n"
            f"**Задача:** {task.task_text}\n"
            f"**Приоритет:** {self.priority_emojis.get(task.priority)}\n\n"
            f"**Дни недели:**\n{days_info}"
        )

        keyboard = [
            [InlineKeyboardButton("✅ Выполнено", callback_data=f"complete_task_{task.id}")],
            [InlineKeyboardButton("🔳 Частично", callback_data=f"partial_task_{task.id}")],
            [InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_task_{task.id}")],
            [InlineKeyboardButton("▶️ Перенести", callback_data=f"postpone_task_{task.id}")],
            [InlineKeyboardButton("📋 Назад к списку", callback_data="back_to_list")]
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
        status_type = data_parts[0]  # complete, partial, cancel, postpone
        task_id = int(data_parts[2])

        task = self.storage.get_running_task(task_id)
        current_weekday = datetime.now().weekday()

        # Добавляем запись в историю статусов
        status_record = {
            'day': current_weekday,
            'status': status_type,
            'timestamp': datetime.now().isoformat()
        }
        task.status_history.append(status_record)

        # Если задача переносится, перемещаем на следующий день
        if status_type == "postpone":
            next_day = (current_weekday + 1) % 7
            task.days_of_week[next_day] = True

        self.storage.update_running_task(task)

        await query.edit_message_text(
            f"{self.status_emojis.get(status_type, '✅')} Статус задачи обновлен!"
        )

        # Возвращаем к списку задач
        await self.show_running_list_after_save(update, context)


def setup_handlers(application, storage_service):
    handlers = RunningListHandlers(storage_service)

    # Добавляем обработчики
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handlers.add_task_text
    ))

    application.add_handler(CallbackQueryHandler(
        handlers.show_running_list,
        pattern="^back_to_list$"
    ))
    application.add_handler(CallbackQueryHandler(
        handlers.add_task_start,
        pattern="^add_task$"
    ))
    application.add_handler(CallbackQueryHandler(
        handlers.set_task_priority,
        pattern="^priority_"
    ))
    application.add_handler(CallbackQueryHandler(
        handlers.toggle_day,
        pattern="^toggle_day_"
    ))
    application.add_handler(CallbackQueryHandler(
        handlers.save_task,
        pattern="^save_task$"
    ))
    application.add_handler(CallbackQueryHandler(
        handlers.task_detail,
        pattern="^task_detail_"
    ))
    application.add_handler(CallbackQueryHandler(
        handlers.update_task_status,
        pattern="^(complete|partial|cancel|postpone)_task_"
    ))

    return handlers