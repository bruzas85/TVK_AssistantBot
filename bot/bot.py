import os
import atexit
from telebot import TeleBot, types
from typing import Dict

from .models.user_data import UserData
from .handlers.expenses_handler import ExpensesHandler
from .handlers.report_handler import ReportHandler
from .handlers.timesheet_handler import TimesheetHandler
from .handlers.construction_handler import ConstructionHandler
from .services.storage_service import JSONStorageService
from .handlers.running_list_handler import RunningListHandler


class FinanceBot:
    def __init__(self, token: str):
        self.bot = TeleBot(token)

        # Инициализируем сервис хранения
        self.storage_service = JSONStorageService()

        # Загружаем данные при запуске
        self.users_data: Dict[int, UserData] = self.storage_service.load_all_data()

        # ПЕРЕДАЕМ STORAGE_SERVICE В BOT ОБЪЕКТ (важно!)
        self.bot.storage_service = self.storage_service

        # Инициализируем обработчики
        self.expenses_handler = ExpensesHandler(self.bot, self.users_data)
        self.report_handler = ReportHandler(self.bot, self.users_data)
        self.timesheet_handler = TimesheetHandler(self.bot, self.users_data)
        self.construction_handler = ConstructionHandler(self.bot, self.users_data)
        self.running_list_handler = RunningListHandler(self.bot, self.users_data)

        self._register_handlers()
        atexit.register(self._save_all_data)

    def _save_all_data(self):
        """Сохраняет все данные при завершении работы"""
        print("Сохранение данных...")
        self.storage_service.save_all_data(self.users_data)
        print("Данные сохранены!")

    def _register_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def send_welcome(message):
            self._handle_start(message)

        @self.bot.message_handler(commands=['help'])
        def send_help(message):
            self._handle_help(message)

        @self.bot.message_handler(commands=['cancel'])
        def cancel_action(message):
            self._handle_cancel(message)

        @self.bot.message_handler(content_types=['text'])
        def handle_all_messages(message):
            self._handle_text_message(message)

        @self.bot.callback_query_handler(func=lambda call: True)
        def handle_callback(call):
            self._handle_callback(call)

    def _handle_start(self, message):
        user_data = self._get_user_data(message.chat.id)
        user_data.state = 'main_menu'

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [
            'расходы', 'табель', '🏗 Стройобъекты', '📋 Running List', 'СП мусоропровод',
            'расчёт расходов', 'очистить данные'
        ]
        for button in buttons:
            markup.add(types.KeyboardButton(button))

        welcome_text = f"Привет, {message.from_user.first_name}! 👋\n\nЯ бот для управления различными задачами.\nВыберите нужную опцию:"
        self.bot.send_message(message.chat.id, welcome_text, reply_markup=markup)

    def _handle_help(self, message):
        help_text = """
Доступные команды:
/start - Начать работу с кнопками
/help - Помощь
/cancel - Отменить текущее действие

Основные разделы:
• расходы - Управление финансами
• расчёт расходов - Получить отчет по расходам
• очистить данные - Удалить все данные по расходам
• табель - Учет рабочего времени
• СП мусоропровод - Сервис мусоропровода
"""
        self.bot.send_message(message.chat.id, help_text)

    def _handle_cancel(self, message):
        user_data = self._get_user_data(message.chat.id)
        user_data.state = 'main_menu'
        self.bot.send_message(message.chat.id, "Действие отменено. Возврат в главное меню.")
        self._handle_start(message)

    def _handle_text_message(self, message):
        chat_id = message.chat.id
        text = message.text
        user_data = self._get_user_data(chat_id)

        print(f"Получено сообщение: '{text}' от пользователя {chat_id}, состояние: {user_data.state}")

        # Обработка команд Running List
        if text.startswith('/done'):
            task_number = text.split(' ', 1)[1] if ' ' in text else ""
            print(f"DEBUG: Обработка команды /done с номером: '{task_number}'")
            self.running_list_handler.handle_complete_task(message, task_number)
            return

        if text.startswith('/delete'):
            task_number = text.split(' ', 1)[1] if ' ' in text else ""
            print(f"DEBUG: Обработка команды /delete с номером: '{task_number}'")
            self.running_list_handler.handle_delete_task(message, task_number)
            return

        if text.startswith('/reopen'):
            task_number = text.split(' ', 1)[1] if ' ' in text else ""
            print(f"DEBUG: Обработка команды /reopen с номером: '{task_number}'")
            self.running_list_handler.handle_reopen_task(message, task_number)
            return

        # Обработка команды /del для удаления ответственных лиц
        if text.startswith('/del'):
            # Проверяем, находится ли пользователь в режиме управления объектом
            if (hasattr(user_data, 'temp_object_id') and
                    user_data.state == 'construction_main'):
                object_id = getattr(user_data, 'temp_object_id')
                self.construction_handler.handle_delete_responsible(message, object_id)
                return
            else:
                self.bot.send_message(chat_id, "❌ Сначала выберите объект в разделе 'Управление объектом'")
                return

        # Обработка состояний Running List (ПЕРВЫМИ!)
        if user_data.state == 'waiting_task_description':
            print(f"DEBUG: Обнаружено состояние 'waiting_task_description', передаем в running_list_handler")
            self.running_list_handler.handle_task_description_input(message)
            return

        if user_data.state == 'waiting_task_short_name':
            print(f"DEBUG: Обнаружено состояние 'waiting_task_short_name', передаем в running_list_handler")
            self.running_list_handler.handle_task_short_name_input(message)
            return

        if user_data.state == 'waiting_task_comment':
            print(f"DEBUG: Обнаружено состояние 'waiting_task_comment', передаем в running_list_handler")
            self.running_list_handler.handle_comment_input(message)
            return

        # Обработка состояний строительных объектов
        if user_data.state == 'waiting_object_name':
            self.construction_handler.handle_object_name_input(message)
            return

        if user_data.state == 'waiting_object_address':
            self.construction_handler.handle_object_address_input(message)
            return

        if user_data.state == 'waiting_resp_name':
            self.construction_handler.handle_resp_name_input(message)
            return

        if user_data.state == 'waiting_resp_position':
            self.construction_handler.handle_resp_position_input(message)
            return

        if user_data.state == 'waiting_resp_phone':
            self.construction_handler.handle_resp_phone_input(message)
            return

        if user_data.state == 'waiting_comment':
            self.construction_handler.handle_comment_input(message)
            return

        # Обработка состояний табеля
        if user_data.state == 'waiting_employee_name':
            self.timesheet_handler.handle_employee_name_input(message)
            return

        if user_data.state == 'waiting_employee_salary':
            self.timesheet_handler.handle_employee_salary_input(message)
            return

        # Обработка состояний расходов
        if user_data.state == 'waiting_clear_confirmation':
            self._handle_clear_confirmation(message)
            return

        if 'waiting_personal_' in user_data.state:
            self.expenses_handler.handle_expense_input(message, 'personal')
            return

        if 'waiting_work_' in user_data.state:
            self.expenses_handler.handle_expense_input(message, 'work')
            return

        if user_data.state == 'personal_expenses_menu':
            self.expenses_handler.handle_personal_category_selection(message)
            return

        if user_data.state == 'work_expenses_menu':
            self.expenses_handler.handle_work_category_selection(message)
            return

        if user_data.state == 'waiting_period':
            self._handle_period_selection(message)
            return

        # Обработка основных кнопок меню
        if text == 'расходы':
            self.expenses_handler.handle_expenses_menu(message)
        elif text == 'табель':
            self.timesheet_handler.handle_timesheet_main(message)
        elif text == 'СП мусоропровод':
            self._handle_garbage_chute(message)
        elif text == 'личные расходы':
            self.expenses_handler.handle_personal_expenses(message)
        elif text == 'рабочие расходы':
            self.expenses_handler.handle_work_expenses(message)
        elif text == 'расчёт расходов':
            self.report_handler.handle_calculate_expenses(message)
        elif text == 'очистить данные':
            self.report_handler.handle_clear_data(message)
        elif text == '➕ Добавить работника':
            self.timesheet_handler.handle_add_employee(message)
        elif text == '🗑 Удалить работника':
            self.timesheet_handler.handle_remove_employee_menu(message)
        elif text == '📝 Учет присутствия':
            self.timesheet_handler.handle_manage_attendance(message)
        elif text == '💰 Расчет зарплаты':
            self.timesheet_handler.handle_calculate_salary(message)
        elif text == '🏗 Стройобъекты':
            self.construction_handler.handle_construction_main(message)
        elif text == '🏗 Добавить объект':
            self.construction_handler.handle_add_object(message)
        elif text == '📋 Список объектов':
            self.construction_handler.handle_view_objects(message)
        elif text == '⚙️ Управление объектом':
            self.construction_handler.handle_manage_object_menu(message)
        elif text == '📋 Running List':
            print(f"DEBUG: Нажата кнопка '📋 Running List'")
            self.running_list_handler.handle_running_list_main(message)
        elif text == '➕ Добавить задачу':
            print(f"DEBUG: Нажата кнопка '➕ Добавить задачу'")
            self.running_list_handler.handle_add_task(message)
        elif text == '📋 Grid задач':
            print(f"DEBUG: Нажата кнопка '📋 Grid задач'")
            self.running_list_handler.handle_view_grid(message)
        elif text == '📊 По статусам':
            print(f"DEBUG: Нажата кнопка '📊 По статусам'")
            self.running_list_handler.handle_view_by_status(message)
        elif text == 'назад':
            self._handle_start(message)
        else:
            self.bot.send_message(chat_id, "Используйте кнопки меню или команду /help")

    def _handle_callback(self, call):
        """Обработка callback запросов от inline кнопок"""
        chat_id = call.message.chat.id
        user_data = self._get_user_data(chat_id)

        # Обработка callback для running list (ПЕРВЫМ ДЕЛОМ!)
        if call.data.startswith("priority:"):
            self.running_list_handler.handle_running_list_callback(call)
            return

        if call.data.startswith(("view_task:", "set_status:", "add_comment:", "delete_task:", "back_to_grid", "add_new_task")):
            self.running_list_handler.handle_running_list_callback(call)
            return

        # Обработка callback для табеля
        if call.data.startswith(("toggle_attendance:", "save_attendance")):
            self.timesheet_handler.handle_attendance_callback(call)
        elif call.data.startswith("remove_employee:"):
            self.timesheet_handler.handle_remove_employee_callback(call)
        elif call.data == "back_to_timesheet":
            self.timesheet_handler.handle_timesheet_main(call.message)

        # Обработка callback для строительных объектов
        elif call.data.startswith(("select_object:", "obj_responsible:", "obj_comments:", "view_comments:",
                                   "add_comment:", "obj_next_stage:", "obj_complete:", "confirm_complete:",
                                   "resp_stage:", "add_resp:", "remove_resp:", "back_to_object:",
                                   "back_to_construction", "back_to_objects")):
            self.construction_handler.handle_construction_callback(call)

    def _handle_clear_confirmation(self, message):
        chat_id = message.chat.id
        text = message.text

        if text == 'ДА, очистить всё':
            deleted_count = self.report_handler.execute_clear_data(chat_id)
            self.bot.send_message(chat_id, f"✅ Все данные по расходам удалены!\nУдалено записей: {deleted_count}")
            self._handle_start(message)
        elif text == 'НЕТ, отменить':
            self.bot.send_message(chat_id, "❌ Очистка данных отменена.")
            self._handle_start(message)
        else:
            self.bot.send_message(chat_id, "Пожалуйста, выберите ДА или НЕТ")

    def _handle_period_selection(self, message):
        chat_id = message.chat.id
        text = message.text

        period_map = {'неделя': 7, 'месяц': 30, '3 месяца': 90}
        if text in period_map:
            filename, report_text = self.report_handler.create_expense_report(chat_id, period_map[text])
            if filename:
                with open(filename, 'rb') as f:
                    self.bot.send_document(chat_id, f, caption=report_text)
                os.remove(filename)
            else:
                self.bot.send_message(chat_id, report_text)
            self._handle_start(message)
        elif text == 'назад':
            self._handle_start(message)
        else:
            self.bot.send_message(chat_id, "Пожалуйста, выберите период из предложенных вариантов")

    def _handle_timesheet(self, message):
        response = "📊 Раздел: ТАБЕЛЬ\n\nФункции табеля:\n• Отметка времени прихода/ухода\n• Просмотр отработанных часов\n• Формирование отчетов\n• Учет отпусков и больничных\n\nВыберите действие:"
        self.bot.send_message(message.chat.id, response)

    def _handle_garbage_chute(self, message):
        response = "🗑️ Раздел: СЕРВИС МУСОРОПРОВОДА\n\nДоступные опции:\n• Заявка на обслуживание\n• Статус текущих заявок\n• График вывоза мусора\n• Контакты ответственных\n\nЧто необходимо?"
        self.bot.send_message(message.chat.id, response)

    def _get_user_data(self, chat_id: int) -> UserData:
        if chat_id not in self.users_data:
            self.users_data[chat_id] = UserData(chat_id)
        return self.users_data[chat_id]

    def run(self):
        if not os.path.exists('temp'):
            os.makedirs('temp')
        os.chdir('temp')

        print("Бот запущен...")
        try:
            self.bot.polling(none_stop=True)
        except KeyboardInterrupt:
            print("Бот остановлен пользователем")
        except Exception as e:
            print(f"Ошибка: {e}")
        finally:
            self._save_all_data()