from telebot import types
from .base_handler import BaseHandler
from ..models.user_data import Expense


class ExpensesHandler(BaseHandler):
    def __init__(self, bot, users_data):
        super().__init__(bot, users_data)

        # Категории личных расходов
        self.personal_categories = {
            'Образование': 'Книги, курсы, семинары',
            'Красота и здоровье': 'Парикмахерская, аптека, поликлиника',
            'Подарки': 'На дни рождения, праздники',
            'Питание': 'Продукты, кафе, рестораны',
            'Ремонт и дом': 'Мелкий ремонт, покупка мебели, предметы интерьера',
            'Проезд': 'Безлимитка, автобус, поезд, самолет',
            'Отдых': 'Отпуск, ресторан, дискотека, выходные',
            'Хобби': '3д печать, вязание, рисование, тренировки',
            'Одежда': 'Рубашка, брюки, куртка, ботинки',
            'Автомобиль': 'Бензин, ТО, страховка, мойка (если не используется для работы)',
            'Домашние животные': 'Корм, ветеринар, аксессуары',
            'Проживание': 'Коммунальные услуги, оплата',
            'Резерв/Накопления': 'Отложенные на цель деньги',
            'Связь': 'Интернет, сотовая связь',
            'Другое': 'Подписки'
        }

        # Категории рабочих расходов
        self.work_categories = {
            'Оборудование': 'Покупка компьютера, монитора, телефона',
            'Образование/Курсы': 'Повышение квалификации, профессиональные конференции',
            'Аренда рабочего пространства': 'Гараж, офис',
            'Банковские услуги': 'Проценты по кредитам, комиссии за обслуживание бизнес-счета',
            'Расходники': 'Краски, диски, перчатки',
            'Проезд': 'Безлимитка, поезд, автобус, самолет',
            'Здоровье': 'Аптека, поликлиника',
            'Доставка': 'Каршеринг, такси',
            'Другое': 'Презент, договоренности'
        }

    def handle_expenses_menu(self, message):
        self.set_user_state(message.chat.id, 'expenses_menu')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_personal = types.KeyboardButton('личные расходы')
        btn_work = types.KeyboardButton('рабочие расходы')
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_personal, btn_work, btn_back)

        response = "💸 Раздел: РАСХОДЫ\n\nВыберите тип расходов:"
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_personal_expenses(self, message):
        self.set_user_state(message.chat.id, 'personal_expenses_menu')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        categories = list(self.personal_categories.keys()) + ['назад']
        buttons = [types.KeyboardButton(category) for category in categories]
        markup.add(*buttons)

        response = "👤 ЛИЧНЫЕ РАСХОДЫ\n\nВыберите категорию:\n\n"
        for category, description in self.personal_categories.items():
            response += f"• {category}: {description}\n"

        response += "\nДля добавления расхода выберите категорию, затем введите:\nСумма Описание\nНапример: 1500 Книга по Python"

        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_work_expenses(self, message):
        self.set_user_state(message.chat.id, 'work_expenses_menu')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        categories = list(self.work_categories.keys()) + ['назад']
        buttons = [types.KeyboardButton(category) for category in categories]
        markup.add(*buttons)

        response = "💼 РАБОЧИЕ РАСХОДЫ\n\nВыберите категорию:\n\n"
        for category, description in self.work_categories.items():
            response += f"• {category}: {description}\n"

        response += "\nДля добавления расхода выберите категорию, затем введите:\nСумма Описание\nНапример: 5000 Новый монитор"

        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_personal_category_selection(self, message):
        chat_id = message.chat.id
        text = message.text

        if text == 'назад':
            self.set_user_state(chat_id, 'expenses_menu')
            self.handle_expenses_menu(message)
            return

        if text in self.personal_categories:
            self.set_user_state(chat_id, f'waiting_personal_{text}')
            response = f"📝 Категория: {text}\n\nОписание: {self.personal_categories[text]}\n\nТеперь введите расход в формате:\nСумма Описание\n\nНапример: 1500 Книга по Python"
            self.bot.send_message(chat_id, response)
        else:
            self.bot.send_message(chat_id, "Пожалуйста, выберите категорию из списка")

    def handle_work_category_selection(self, message):
        chat_id = message.chat.id
        text = message.text

        if text == 'назад':
            self.set_user_state(chat_id, 'expenses_menu')
            self.handle_expenses_menu(message)
            return

        if text in self.work_categories:
            self.set_user_state(chat_id, f'waiting_work_{text}')
            response = f"📝 Категория: {text}\n\nОписание: {self.work_categories[text]}\n\nТеперь введите расход в формате:\nСумма Описание\n\nНапример: 5000 Новый монитор"
            self.bot.send_message(chat_id, response)
        else:
            self.bot.send_message(chat_id, "Пожалуйста, выберите категорию из списка")

    def handle_expense_input(self, message, expense_type):
        chat_id = message.chat.id
        text = message.text.strip()

        try:
            parts = text.split(' ', 1)
            if len(parts) < 2:
                self.bot.send_message(chat_id, "❌ Неверный формат. Используйте: Сумма Описание")
                return

            amount = float(parts[0])
            description = parts[1]

            current_state = self.get_user_state(chat_id)
            if expense_type == 'personal' and 'waiting_personal_' in current_state:
                category = current_state.replace('waiting_personal_', '')
            elif expense_type == 'work' and 'waiting_work_' in current_state:
                category = current_state.replace('waiting_work_', '')
            else:
                self.bot.send_message(chat_id, "❌ Ошибка: категория не определена")
                return

            # Импортируем здесь
            from ..models.user_data import Expense
            expense = Expense(category, amount, description, expense_type)
            user_data = self.get_user_data(chat_id)
            user_data.add_expense(expense)

            # АВТОСОХРАНЕНИЕ после добавления расхода
            self._auto_save_user_data(chat_id)

            self.bot.send_message(chat_id,
                                  f"✅ Расход добавлен!\nКатегория: {category}\nСумма: {amount} руб.\nОписание: {description}")

            if expense_type == 'personal':
                self.set_user_state(chat_id, 'personal_expenses_menu')
                self.handle_personal_expenses(message)
            else:
                self.set_user_state(chat_id, 'work_expenses_menu')
                self.handle_work_expenses(message)

        except ValueError:
            self.bot.send_message(chat_id, "❌ Ошибка: сумма должна быть числом")

    def _auto_save_user_data(self, chat_id: int):
        """Автосохранение данных пользователя"""
        try:
            user_data = self.get_user_data(chat_id)
            # Импортируем сервис хранения
            from ..services.storage_service import JSONStorageService
            storage = JSONStorageService()
            storage.save_user_data(user_data)
        except Exception as e:
            print(f"Ошибка автосохранения: {e}")