from telebot import types
from .base_handler import BaseHandler
from ..models.running_list import RunningTask, TaskPriority, TaskStatus


class RunningListHandler(BaseHandler):
    def __init__(self, bot, users_data):
        super().__init__(bot, users_data)

    def handle_running_list_main(self, message):
        self.set_user_state(message.chat.id, 'running_list_main')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_add_task = types.KeyboardButton('➕ Добавить задачу')
        btn_view_grid = types.KeyboardButton('📋 Grid задач')
        btn_view_by_status = types.KeyboardButton('📊 По статусам')
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_add_task, btn_view_grid, btn_view_by_status, btn_back)

        user_data = self.get_user_data(message.chat.id)
        task_count = len(user_data.running_list.tasks)

        response = f"""
📋 Раздел: RUNNING LIST

Всего задач: {task_count}

Статусы задач:
⏳ Ожидает
✅ Выполнено  
🟡 Частично выполнено
❌ Отменено
📅 Перенесено

Выберите действие:
"""
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_add_task(self, message):
        self.set_user_state(message.chat.id, 'waiting_task_description')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_back)

        response = "➕ ДОБАВЛЕНИЕ ЗАДАЧИ\n\nВведите полное описание задачи:"
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_task_description_input(self, message):
        chat_id = message.chat.id
        description = message.text.strip()

        if not description:
            self.bot.send_message(chat_id, "❌ Описание задачи не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)
        user_data.temp_task_description = description
        self.set_user_state(chat_id, 'waiting_task_short_name')

        response = f"📝 Полное описание: {description}\n\nТеперь введите короткое название для кнопки (максимум 20 символов):"
        self.bot.send_message(chat_id, response)

    def handle_task_short_name_input(self, message):
        chat_id = message.chat.id
        short_name = message.text.strip()

        if not short_name:
            self.bot.send_message(chat_id, "❌ Короткое название не может быть пустым.")
            return

        if len(short_name) > 20:
            short_name = short_name[:20] + "..."

        user_data = self.get_user_data(chat_id)
        description = getattr(user_data, 'temp_task_description', '')

        if not description:
            self.bot.send_message(chat_id, "❌ Ошибка: описание задачи не найдено.")
            self.handle_running_list_main(message)
            return

        user_data.temp_task_short_name = short_name
        self.set_user_state(chat_id, 'waiting_task_priority')

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔵 Низкий", callback_data="priority:LOW"),
            types.InlineKeyboardButton("🟡 Средний", callback_data="priority:MEDIUM"),
            types.InlineKeyboardButton("🔴 Высокий", callback_data="priority:HIGH"),
            types.InlineKeyboardButton("⚡ Срочный", callback_data="priority:URGENT")
        )

        response = f"📝 Задача: {description}\n🏷️ Короткое название: {short_name}\n\nВыберите приоритет:"
        self.bot.send_message(chat_id, response, reply_markup=markup)

    def handle_view_grid(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        if not running_list.tasks:
            response = "📋 GRID ЗАДАЧ\n\n❌ Нет задач"
            self.bot.send_message(chat_id, response)
            return

        # Создаем grid 2x2 из кнопок
        markup = types.InlineKeyboardMarkup(row_width=2)

        for task in running_list.tasks:
            # Создаем кнопку с эмодзи статуса и коротким названием
            button_text = f"{self._get_status_emoji(task.status)} {task.short_name}"
            callback_data = f"view_task:{task.id}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

        markup.add(types.InlineKeyboardButton("➕ Добавить задачу", callback_data="add_new_task"))

        response = "📋 GRID ЗАДАЧ\n\nНажмите на задачу для просмотра деталей и изменения статуса:"
        self.bot.send_message(chat_id, response, reply_markup=markup)

    def handle_view_by_status(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        running_list = user_data.running_list

        response = "📊 ЗАДАЧИ ПО СТАТУСАМ\n\n"

        for status in TaskStatus:
            tasks = running_list.get_tasks_by_status(status)
            if tasks:
                response += f"\n{status.value}:\n"
                for task in tasks:
                    response += f"• {task.short_name} ({task.priority.value})\n"

        if not running_list.tasks:
            response += "❌ Нет задач"

        self.bot.send_message(chat_id, response)

    def handle_view_task_details(self, call, task_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        task = user_data.running_list.get_task(task_id)

        if not task:
            self.bot.answer_callback_query(call.id, "❌ Задача не найдена")
            return

        # Формируем детальную информацию о задаче
        response = f"""
📋 ДЕТАЛИ ЗАДАЧИ

🏷️ Короткое название: {task.short_name}
📝 Полное описание: {task.description}
🎯 Приоритет: {task.priority.value}
📊 Статус: {task.status.value}
📅 Создана: {task.created_date.strftime('%d.%m.%Y %H:%M')}
🔄 Обновлена: {task.updated_date.strftime('%d.%m.%Y %H:%M')}
"""

        if task.comments:
            response += f"\n💬 Комментарии:\n"
            for comment in task.comments[-3:]:  # Показываем последние 3 комментария
                response += f"• {comment}\n"

        # Кнопки для изменения статуса
        markup = types.InlineKeyboardMarkup(row_width=2)

        status_buttons = [
            ("✅ Выполнено", f"set_status:{task.id}:COMPLETED"),
            ("🟡 Частично", f"set_status:{task.id}:PARTIAL"),
            ("❌ Отменить", f"set_status:{task.id}:CANCELLED"),
            ("📅 Перенести", f"set_status:{task.id}:POSTPONED"),
            ("⏳ В ожидание", f"set_status:{task.id}:PENDING")
        ]

        for btn_text, callback_data in status_buttons:
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))

        markup.add(
            types.InlineKeyboardButton("💬 Добавить комментарий", callback_data=f"add_comment:{task.id}"),
            types.InlineKeyboardButton("🗑️ Удалить задачу", callback_data=f"delete_task:{task.id}")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Назад к grid", callback_data="back_to_grid"))

        self.bot.edit_message_text(
            response,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    def handle_change_status(self, call, task_id: str, new_status: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        task = user_data.running_list.get_task(task_id)

        if not task:
            self.bot.answer_callback_query(call.id, "❌ Задача не найдена")
            return

        try:
            status = TaskStatus[new_status]
            old_status = task.status
            task.change_status(status)

            # АВТОСОХРАНЕНИЕ
            self._auto_save_user_data(chat_id)

            self.bot.answer_callback_query(
                call.id,
                f"✅ Статус изменен: {old_status.value} → {status.value}"
            )

            # Обновляем детали задачи
            self.handle_view_task_details(call, task_id)

        except KeyError:
            self.bot.answer_callback_query(call.id, "❌ Ошибка изменения статуса")

    def start_add_comment(self, call, task_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)

        user_data.temp_task_id = task_id
        self.set_user_state(chat_id, 'waiting_task_comment')

        self.bot.send_message(chat_id, "💬 Введите комментарий к задаче:")

    def handle_comment_input(self, message):
        chat_id = message.chat.id
        comment = message.text.strip()

        if not comment:
            self.bot.send_message(chat_id, "❌ Комментарий не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)
        task_id = getattr(user_data, 'temp_task_id', '')

        if not task_id:
            self.bot.send_message(chat_id, "❌ Ошибка: задача не найдена.")
            self.handle_running_list_main(message)
            return

        task = user_data.running_list.get_task(task_id)
        if task:
            task.add_comment(comment)

            # АВТОСОХРАНЕНИЕ
            self._auto_save_user_data(chat_id)

            # Очищаем временные данные
            if hasattr(user_data, 'temp_task_id'):
                delattr(user_data, 'temp_task_id')

            self.bot.send_message(chat_id, f"✅ Комментарий добавлен к задаче: {task.short_name}")
            self.handle_running_list_main(message)
        else:
            self.bot.send_message(chat_id, "❌ Задача не найдена.")
            self.handle_running_list_main(message)

    def handle_delete_task(self, call, task_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)

        task = user_data.running_list.get_task(task_id)
        if task and user_data.running_list.delete_task(task_id):
            # АВТОСОХРАНЕНИЕ
            self._auto_save_user_data(chat_id)

            self.bot.answer_callback_query(call.id, f"✅ Задача удалена: {task.short_name}")
            self.handle_view_grid(call.message)
        else:
            self.bot.answer_callback_query(call.id, "❌ Ошибка удаления задачи")

    def _get_status_emoji(self, status: TaskStatus) -> str:
        """Возвращает эмодзи для статуса"""
        emoji_map = {
            TaskStatus.PENDING: "⏳",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.PARTIAL: "🟡",
            TaskStatus.CANCELLED: "❌",
            TaskStatus.POSTPONED: "📅"
        }
        return emoji_map.get(status, "📝")

    def _auto_save_user_data(self, chat_id: int):
        """Автосохранение данных пользователя"""
        try:
            user_data = self.get_user_data(chat_id)
            self.bot.storage_service.save_user_data(user_data)
        except Exception as e:
            print(f"Ошибка автосохранения: {e}")

    def handle_running_list_callback(self, call):
        chat_id = call.message.chat.id
        data = call.data

        print(f"DEBUG: Running list callback: {data}")

        if data.startswith("priority:"):
            self.handle_priority_selection(call, data.split(":")[1])
        elif data.startswith("view_task:"):
            self.handle_view_task_details(call, data.split(":")[1])
        elif data.startswith("set_status:"):
            _, task_id, status = data.split(":")
            self.handle_change_status(call, task_id, status)
        elif data.startswith("add_comment:"):
            self.start_add_comment(call, data.split(":")[1])
        elif data.startswith("delete_task:"):
            self.handle_delete_task(call, data.split(":")[1])
        elif data == "back_to_grid":
            self.bot.delete_message(chat_id, call.message.message_id)
            self.handle_view_grid(call.message)
        elif data == "add_new_task":
            self.bot.delete_message(chat_id, call.message.message_id)
            self.handle_add_task(call.message)

    def handle_priority_selection(self, call, priority_name: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)

        try:
            priority = TaskPriority[priority_name]
            description = getattr(user_data, 'temp_task_description', '')
            short_name = getattr(user_data, 'temp_task_short_name', '')

            if not description:
                self.bot.send_message(chat_id, "❌ Ошибка: описание задачи не найдено.")
                self.handle_running_list_main(call.message)
                return

            # Добавляем задачу
            task = user_data.running_list.add_task(description, priority, short_name)

            # АВТОСОХРАНЕНИЕ
            self._auto_save_user_data(chat_id)

            # Очищаем временные данные
            for attr in ['temp_task_description', 'temp_task_short_name']:
                if hasattr(user_data, attr):
                    delattr(user_data, attr)

            # Удаляем сообщение с кнопками приоритета
            try:
                self.bot.delete_message(chat_id, call.message.message_id)
            except:
                pass

            self.bot.send_message(
                chat_id,
                f"✅ Задача добавлена!\n"
                f"🏷️ {task.short_name}\n"
                f"📝 {task.description}\n"
                f"🎯 Приоритет: {task.priority.value}"
            )
            self.handle_running_list_main(call.message)

        except KeyError:
            self.bot.send_message(chat_id, "❌ Ошибка: неверный приоритет.")
            self.handle_running_list_main(call.message)