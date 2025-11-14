from telebot import types
from .base_handler import BaseHandler
from ..models.running_list import RunningTask, TaskPriority


class RunningListHandler(BaseHandler):
    def __init__(self, bot, users_data):
        super().__init__(bot, users_data)

    def handle_running_list_main(self, message):
        self.set_user_state(message.chat.id, 'running_list_main')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_add_task = types.KeyboardButton('➕ Добавить задачу')
        btn_view_tasks = types.KeyboardButton('📋 Список задач')
        btn_completed_tasks = types.KeyboardButton('✅ Выполненные')
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_add_task, btn_view_tasks, btn_completed_tasks, btn_back)

        user_data = self.get_user_data(message.chat.id)
        active_count = len(user_data.running_list.get_active_tasks())
        completed_count = len(user_data.running_list.get_completed_tasks())

        response = f"""
📋 Раздел: RUNNING LIST

Статистика:
• Активных задач: {active_count}
• Выполненных задач: {completed_count}

Приоритеты:
🔵 Низкий - не срочно
🟡 Средний - обычная важность  
🔴 Высокий - важно
⚡ Срочный - очень срочно

Выберите действие:
"""
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_add_task(self, message):
        self.set_user_state(message.chat.id, 'waiting_task_description')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_back)

        response = "➕ ДОБАВЛЕНИЕ ЗАДАЧИ\n\nВведите описание задачи:"
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_task_description_input(self, message):
        chat_id = message.chat.id
        description = message.text.strip()

        if not description:
            self.bot.send_message(chat_id, "❌ Описание задачи не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)
        user_data.temp_task_description = description
        self.set_user_state(chat_id, 'waiting_task_priority')

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔵 Низкий", callback_data="priority:LOW"),
            types.InlineKeyboardButton("🟡 Средний", callback_data="priority:MEDIUM"),
            types.InlineKeyboardButton("🔴 Высокий", callback_data="priority:HIGH"),
            types.InlineKeyboardButton("⚡ Срочный", callback_data="priority:URGENT")
        )

        response = f"📝 Задача: {description}\n\nВыберите приоритет:"
        self.bot.send_message(chat_id, response, reply_markup=markup)

    def handle_priority_selection(self, call, priority_name: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)

        try:
            priority = TaskPriority[priority_name]
            description = getattr(user_data, 'temp_task_description', '')

            if not description:
                self.bot.send_message(chat_id, "❌ Ошибка: описание задачи не найдено.")
                self.handle_running_list_main(call.message)
                return

            # Добавляем задачу
            task = user_data.running_list.add_task(description, priority)

            # Очищаем временные данные
            if hasattr(user_data, 'temp_task_description'):
                delattr(user_data, 'temp_task_description')

            self.bot.send_message(
                chat_id,
                f"✅ Задача добавлена!\n"
                f"📝 {task.description}\n"
                f"🎯 Приоритет: {task.priority.value}"
            )
            self.handle_running_list_main(call.message)

        except KeyError:
            self.bot.send_message(chat_id, "❌ Ошибка: неверный приоритет.")
            self.handle_running_list_main(call.message)

    def handle_view_tasks(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        active_tasks = running_list.get_active_tasks()

        if not active_tasks:
            response = "📋 АКТИВНЫЕ ЗАДАЧИ\n\n❌ Нет активных задач"
            self.bot.send_message(chat_id, response)
            return

        response = "📋 АКТИВНЫЕ ЗАДАЧИ\n\n"

        # Группируем по приоритетам
        for priority in TaskPriority:
            tasks_by_priority = [t for t in active_tasks if t.priority == priority]
            if tasks_by_priority:
                response += f"\n{priority.value}:\n"
                for i, task in enumerate(tasks_by_priority, 1):
                    response += f"{i}. {task.description}\n"

        response += f"\n✅ Для завершения задачи введите: /done <номер задачи>"
        response += f"\n🗑️ Для удаления задачи введите: /delete <номер задачи>"

        # Показываем нумерованный список для команд
        response += f"\n\nНумерация для команд:"
        for i, task in enumerate(active_tasks, 1):
            response += f"\n{i}. {task.description}"

        self.bot.send_message(chat_id, response)

    def handle_completed_tasks(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        completed_tasks = running_list.get_completed_tasks()

        if not completed_tasks:
            response = "✅ ВЫПОЛНЕННЫЕ ЗАДАЧИ\n\n❌ Нет выполненных задач"
            self.bot.send_message(chat_id, response)
            return

        response = "✅ ВЫПОЛНЕННЫЕ ЗАДАЧИ\n\n"

        for i, task in enumerate(completed_tasks, 1):
            completed_date = task.completed_date.strftime('%d.%m.%Y %H:%M') if task.completed_date else "неизвестно"
            response += f"{i}. {task.description}\n"
            response += f"   🎯 {task.priority.value} | ✅ {completed_date}\n\n"

        response += f"🔄 Для reopening задачи введите: /reopen <номер задачи>"

        self.bot.send_message(chat_id, response)

    def handle_complete_task(self, message, task_number: str):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        try:
            task_index = int(task_number) - 1
            active_tasks = running_list.get_active_tasks()

            if 0 <= task_index < len(active_tasks):
                task = active_tasks[task_index]
                task.complete()

                self.bot.send_message(
                    chat_id,
                    f"✅ Задача выполнена!\n"
                    f"📝 {task.description}"
                )
                self.handle_view_tasks(message)
            else:
                self.bot.send_message(chat_id, "❌ Неверный номер задачи")

        except ValueError:
            self.bot.send_message(chat_id, "❌ Используйте: /done <номер задачи>")

    def handle_delete_task(self, message, task_number: str):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        try:
            task_index = int(task_number) - 1
            active_tasks = running_list.get_active_tasks()

            if 0 <= task_index < len(active_tasks):
                task = active_tasks[task_index]
                running_list.delete_task(task.id)

                self.bot.send_message(
                    chat_id,
                    f"🗑️ Задача удалена!\n"
                    f"📝 {task.description}"
                )
                self.handle_view_tasks(message)
            else:
                self.bot.send_message(chat_id, "❌ Неверный номер задачи")

        except ValueError:
            self.bot.send_message(chat_id, "❌ Используйте: /delete <номер задачи>")

    def handle_reopen_task(self, message, task_number: str):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        try:
            task_index = int(task_number) - 1
            completed_tasks = running_list.get_completed_tasks()

            if 0 <= task_index < len(completed_tasks):
                task = completed_tasks[task_index]
                task.reopen()

                self.bot.send_message(
                    chat_id,
                    f"🔄 Задача reopened!\n"
                    f"📝 {task.description}"
                )
                self.handle_completed_tasks(message)
            else:
                self.bot.send_message(chat_id, "❌ Неверный номер задачи")

        except ValueError:
            self.bot.send_message(chat_id, "❌ Используйте: /reopen <номер задачи>")