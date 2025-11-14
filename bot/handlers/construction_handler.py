from telebot import types
from .base_handler import BaseHandler
from ..models.construction import ConstructionStage, ResponsiblePerson, ConstructionObject


class ConstructionHandler(BaseHandler):
    def __init__(self, bot, users_data):
        super().__init__(bot, users_data)

    def handle_construction_main(self, message):
        self.set_user_state(message.chat.id, 'construction_main')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_add_object = types.KeyboardButton('🏗 Добавить объект')
        btn_view_objects = types.KeyboardButton('📋 Список объектов')
        btn_manage_object = types.KeyboardButton('⚙️ Управление объектом')
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_add_object, btn_view_objects, btn_manage_object, btn_back)

        user_data = self.get_user_data(message.chat.id)
        active_count = len(user_data.construction_manager.get_active_objects())
        completed_count = len(user_data.construction_manager.get_completed_objects())

        response = f"""
🏗️ Раздел: СТРОИТЕЛЬНЫЕ ОБЪЕКТЫ

Статистика:
• Активных объектов: {active_count}
• Завершенных объектов: {completed_count}

Этапы работ:
1. {ConstructionStage.ACCEPTANCE.value}
2. {ConstructionStage.INSTALLATION.value}  
3. {ConstructionStage.COMPLETION.value}

Выберите действие:
"""
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_add_object(self, message):
        self.set_user_state(message.chat.id, 'waiting_object_name')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_back)

        response = "🏗️ ДОБАВЛЕНИЕ ОБЪЕКТА\n\nВведите название объекта:"
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_object_name_input(self, message):
        chat_id = message.chat.id
        object_name = message.text.strip()

        if not object_name:
            self.bot.send_message(chat_id, "❌ Название объекта не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)
        user_data.temp_object_name = object_name
        self.set_user_state(chat_id, 'waiting_object_address')

        response = f"🏗️ Объект: {object_name}\n\nВведите адрес объекта:"
        self.bot.send_message(chat_id, response)

    def handle_object_address_input(self, message):
        chat_id = message.chat.id
        address = message.text.strip()

        if not address:
            self.bot.send_message(chat_id, "❌ Адрес объекта не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)
        object_name = getattr(user_data, 'temp_object_name', '')

        if not object_name:
            self.bot.send_message(chat_id, "❌ Ошибка: данные объекта не найдены.")
            self.handle_construction_main(message)
            return

        # Добавляем объект
        obj = user_data.construction_manager.add_object(object_name, address)

        # Очищаем временные данные
        if hasattr(user_data, 'temp_object_name'):
            delattr(user_data, 'temp_object_name')

        self.bot.send_message(chat_id,
                              f"✅ Объект добавлен!\nНазвание: {obj.name}\nАдрес: {obj.address}\nТекущий этап: {obj.current_stage.value}")
        self.handle_construction_main(message)

    def handle_view_objects(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        manager = user_data.construction_manager

        if not manager.objects:
            self.bot.send_message(chat_id, "❌ Нет добавленных объектов.")
            self.handle_construction_main(message)
            return

        response = "📋 СПИСОК ОБЪЕКТОВ\n\n"

        # Активные объекты по этапам
        for stage in ConstructionStage:
            objects_in_stage = manager.get_objects_by_stage(stage)
            if objects_in_stage:
                response += f"\n{stage.value}:\n"
                for obj in objects_in_stage:
                    resp_count = len(obj.responsible_persons)
                    response += f"• {obj.name} ({obj.address}) - {resp_count} ответственных\n"

        # Завершенные объекты
        completed_objects = manager.get_completed_objects()
        if completed_objects:
            response += f"\n✅ ЗАВЕРШЕННЫЕ ОБЪЕКТЫ:\n"
            for obj in completed_objects:
                completion_date = obj.completion_date.strftime('%d.%m.%Y') if obj.completion_date else "неизвестно"
                response += f"• {obj.name} ({obj.address}) - {completion_date}\n"

        self.bot.send_message(chat_id, response)
        self.handle_construction_main(message)

    def handle_manage_object_menu(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)
        manager = user_data.construction_manager

        if not manager.objects:
            self.bot.send_message(chat_id, "❌ Нет добавленных объектов.")
            self.handle_construction_main(message)
            return

        markup = types.InlineKeyboardMarkup()

        for obj in manager.get_active_objects():
            resp_count = len(obj.responsible_persons)
            button_text = f"🏗 {obj.name} - {obj.current_stage.value} ({resp_count} ответ.)"
            callback_data = f"select_object:{obj.id}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_construction"))

        response = "⚙️ УПРАВЛЕНИЕ ОБЪЕКТОМ\n\nВыберите объект для управления:"
        self.bot.send_message(chat_id, response, reply_markup=markup)

    def handle_object_management(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            self.bot.send_message(chat_id, "❌ Объект не найден.")
            self.handle_construction_main(call.message)
            return

        markup = types.InlineKeyboardMarkup(row_width=2)

        # Кнопки управления
        markup.add(
            types.InlineKeyboardButton("👥 Ответственные лица", callback_data=f"obj_responsible:{object_id}"),
            types.InlineKeyboardButton("💬 Комментарии", callback_data=f"obj_comments:{object_id}")
        )
        markup.add(
            types.InlineKeyboardButton("➡️ Следующий этап", callback_data=f"obj_next_stage:{object_id}"),
            types.InlineKeyboardButton("✅ Завершить", callback_data=f"obj_complete:{object_id}")
        )
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_objects"))

        # Формируем информацию об объекте
        responsible_count = len(obj.responsible_persons)
        comments_count = sum(len(comments) for comments in obj.comments.values())

        response = f"""
🏗️ УПРАВЛЕНИЕ ОБЪЕКТОМ

Название: {obj.name}
Адрес: {obj.address}
Текущий этап: {obj.current_stage.value}
Ответственные лица: {responsible_count} чел.
Комментарии: {comments_count} шт.

Выберите действие:
"""
        self.bot.edit_message_text(
            response,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    def handle_responsible_persons(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            return

        markup = types.InlineKeyboardMarkup()

        # Показываем текущих ответственных
        if obj.responsible_persons:
            for i, person in enumerate(obj.responsible_persons):
                button_text = f"❌ {person.name} - {person.position} ({person.phone})"
                callback_data = f"remove_resp:{object_id}:{i}"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
        else:
            markup.add(types.InlineKeyboardButton("❌ Нет ответственных лиц", callback_data="none"))

        markup.add(types.InlineKeyboardButton("➕ Добавить ответственное лицо", callback_data=f"add_resp:{object_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_object:{object_id}"))

        response = f"👥 ОТВЕТСТВЕННЫЕ ЛИЦА\n\nОбъект: {obj.name}\n\nТекущие ответственные лица:"
        self.bot.edit_message_text(
            response,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    def start_add_responsible_person(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)

        # Сохраняем данные для следующего шага
        user_data.temp_object_id = object_id
        self.set_user_state(chat_id, 'waiting_resp_name')

        self.bot.send_message(chat_id, "Введите ФИО ответственного лица:")

    def handle_resp_name_input(self, message):
        chat_id = message.chat.id
        resp_name = message.text.strip()

        if not resp_name:
            self.bot.send_message(chat_id, "❌ ФИО не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)
        user_data.temp_resp_name = resp_name
        self.set_user_state(chat_id, 'waiting_resp_position')

        self.bot.send_message(chat_id, "Введите должность ответственного лица:")

    def handle_resp_position_input(self, message):
        chat_id = message.chat.id
        position = message.text.strip()

        if not position:
            self.bot.send_message(chat_id, "❌ Должность не может быть пустой.")
            return

        user_data = self.get_user_data(chat_id)
        user_data.temp_resp_position = position
        self.set_user_state(chat_id, 'waiting_resp_phone')

        self.bot.send_message(chat_id, "Введите телефон ответственного лица:")

    def handle_resp_phone_input(self, message):
        chat_id = message.chat.id
        phone = message.text.strip()

        if not phone:
            self.bot.send_message(chat_id, "❌ Телефон не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)

        # Получаем сохраненные данные
        object_id = getattr(user_data, 'temp_object_id', '')
        resp_name = getattr(user_data, 'temp_resp_name', '')
        position = getattr(user_data, 'temp_resp_position', '')

        if not all([object_id, resp_name, position]):
            self.bot.send_message(chat_id, "❌ Ошибка: данные не найдены.")
            self.handle_construction_main(message)
            return

        obj = user_data.construction_manager.get_object(object_id)

        if obj:
            # Создаем ответственное лицо
            person = ResponsiblePerson(
                name=resp_name,
                position=position,
                phone=phone
            )
            obj.add_responsible_person(person)

            # Очищаем временные данные
            for attr in ['temp_object_id', 'temp_resp_name', 'temp_resp_position']:
                if hasattr(user_data, attr):
                    delattr(user_data, attr)

            self.bot.send_message(chat_id,
                                  f"✅ Ответственное лицо добавлено!\nФИО: {resp_name}\nДолжность: {position}\nТелефон: {phone}")
            self.handle_construction_main(message)
        else:
            self.bot.send_message(chat_id, "❌ Объект не найден.")
            self.handle_construction_main(message)

    def handle_remove_responsible_person(self, call, object_id: str, person_index: int):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if obj and obj.remove_responsible_person(person_index):
            self.bot.answer_callback_query(call.id, "✅ Ответственное лицо удалено")
            self.handle_responsible_persons(call, object_id)
        else:
            self.bot.answer_callback_query(call.id, "❌ Ошибка при удалении")

    def handle_construction_callback(self, call):
        chat_id = call.message.chat.id
        data = call.data

        if data == "back_to_construction":
            self.bot.delete_message(chat_id, call.message.message_id)
            self.handle_construction_main(call.message)
            return

        if data == "back_to_objects":
            self.bot.delete_message(chat_id, call.message.message_id)
            self.handle_manage_object_menu(call.message)
            return

        if data.startswith("select_object:"):
            object_id = data.split(":")[1]
            self.handle_object_management(call, object_id)
            return

        if data.startswith("back_to_object:"):
            object_id = data.split(":")[1]
            self.handle_object_management(call, object_id)
            return

        if data.startswith("obj_responsible:"):
            object_id = data.split(":")[1]
            self.handle_responsible_persons(call, object_id)
            return

        if data.startswith("obj_comments:"):
            object_id = data.split(":")[1]
            self.handle_comments(call, object_id)
            return

        if data.startswith("view_comments:"):
            _, object_id, stage_name = data.split(":")
            self.handle_view_comments(call, object_id, stage_name)
            return

        if data.startswith("add_comment:"):
            parts = data.split(":")
            object_id = parts[1]
            stage_name = parts[2] if len(parts) > 2 else None
            self.start_add_comment(call, object_id, stage_name)
            return

        if data.startswith("obj_next_stage:"):
            object_id = data.split(":")[1]
            self.handle_next_stage(call, object_id)
            return

        if data.startswith("obj_complete:"):
            object_id = data.split(":")[1]
            self.handle_complete_object(call, object_id)
            return

        if data.startswith("confirm_complete:"):
            object_id = data.split(":")[1]
            self.handle_confirm_complete(call, object_id)
            return

        if data.startswith("add_resp:"):
            object_id = data.split(":")[1]
            self.start_add_responsible_person(call, object_id)
            return

        if data.startswith("remove_resp:"):
            _, object_id, person_index = data.split(":")
            self.handle_remove_responsible_person(call, object_id, int(person_index))
            return

    def handle_comments(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            return

        markup = types.InlineKeyboardMarkup()

        # Показываем комментарии по этапам
        for stage in ConstructionStage:
            comments = obj.comments[stage]
            if comments:
                button_text = f"💬 {stage.value} ({len(comments)})"
                callback_data = f"view_comments:{object_id}:{stage.name}"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))
            else:
                button_text = f"💬 {stage.value} (нет)"
                callback_data = f"view_comments:{object_id}:{stage.name}"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

        markup.add(types.InlineKeyboardButton("➕ Добавить комментарий", callback_data=f"add_comment:{object_id}"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"back_to_object:{object_id}"))

        response = f"💬 КОММЕНТАРИИ\n\nОбъект: {obj.name}\n\nВыберите этап для просмотра комментариев:"
        self.bot.edit_message_text(
            response,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    def handle_view_comments(self, call, object_id: str, stage_name: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            return

        try:
            stage = ConstructionStage[stage_name]
        except KeyError:
            return

        comments = obj.comments[stage]

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("➕ Добавить комментарий", callback_data=f"add_comment:{object_id}:{stage.name}"))
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"obj_comments:{object_id}"))

        if comments:
            comments_text = "\n".join([f"• {comment}" for comment in comments])
            response = f"💬 КОММЕНТАРИИ - {stage.value}\n\nОбъект: {obj.name}\n\n{comments_text}"
        else:
            response = f"💬 КОММЕНТАРИИ - {stage.value}\n\nОбъект: {obj.name}\n\nНет комментариев"

        self.bot.edit_message_text(
            response,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    def start_add_comment(self, call, object_id: str, stage_name: str = None):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)

        # Сохраняем данные для следующего шага
        user_data.temp_object_id = object_id
        user_data.temp_stage_name = stage_name
        self.set_user_state(chat_id, 'waiting_comment')

        if stage_name:
            try:
                stage = ConstructionStage[stage_name]
                stage_text = stage.value
            except KeyError:
                stage_text = "объекта"
        else:
            stage_text = "объекта"

        self.bot.send_message(chat_id, f"Введите комментарий для {stage_text}:")

    def handle_comment_input(self, message):
        chat_id = message.chat.id
        comment = message.text.strip()

        if not comment:
            self.bot.send_message(chat_id, "❌ Комментарий не может быть пустым.")
            return

        user_data = self.get_user_data(chat_id)

        # Получаем сохраненные данные
        object_id = getattr(user_data, 'temp_object_id', '')
        stage_name = getattr(user_data, 'temp_stage_name', '')

        if not object_id:
            self.bot.send_message(chat_id, "❌ Ошибка: данные объекта не найдены.")
            self.handle_construction_main(message)
            return

        obj = user_data.construction_manager.get_object(object_id)

        if obj:
            if stage_name:
                # Комментарий для конкретного этапа
                try:
                    stage = ConstructionStage[stage_name]
                    obj.add_comment(stage, comment)
                    self.bot.send_message(chat_id, f"✅ Комментарий добавлен к этапу '{stage.value}'!")
                except KeyError:
                    self.bot.send_message(chat_id, "❌ Ошибка: этап не найден.")
            else:
                # Комментарий для текущего этапа объекта
                obj.add_comment(obj.current_stage, comment)
                self.bot.send_message(chat_id, f"✅ Комментарий добавлен к текущему этапу '{obj.current_stage.value}'!")

            # Очищаем временные данные
            for attr in ['temp_object_id', 'temp_stage_name']:
                if hasattr(user_data, attr):
                    delattr(user_data, attr)

            self.handle_construction_main(message)
        else:
            self.bot.send_message(chat_id, "❌ Объект не найден.")
            self.handle_construction_main(message)

    def handle_next_stage(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            return

        if obj.move_to_next_stage():
            self.bot.answer_callback_query(call.id, f"✅ Объект переведен на этап: {obj.current_stage.value}")
            self.handle_object_management(call, object_id)
        else:
            self.bot.answer_callback_query(call.id, "❌ Объект уже на последнем этапе")

    def handle_complete_object(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            return

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Да, завершить", callback_data=f"confirm_complete:{object_id}"),
            types.InlineKeyboardButton("❌ Нет, отменить", callback_data=f"back_to_object:{object_id}")
        )

        response = f"⚠️ ПОДТВЕРЖДЕНИЕ\n\nВы уверены, что хотите завершить объект?\n\nОбъект: {obj.name}\nАдрес: {obj.address}\nТекущий этап: {obj.current_stage.value}"

        self.bot.edit_message_text(
            response,
            chat_id=chat_id,
            message_id=call.message.message_id,
            reply_markup=markup
        )

    def handle_confirm_complete(self, call, object_id: str):
        chat_id = call.message.chat.id
        user_data = self.get_user_data(chat_id)
        obj = user_data.construction_manager.get_object(object_id)

        if not obj:
            return

        obj.complete_object()
        self.bot.answer_callback_query(call.id, "✅ Объект завершен!")
        self.handle_construction_main(call.message)