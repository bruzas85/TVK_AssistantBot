from datetime import date
from telebot import types
from .base_handler import BaseHandler
from ..models.timesheet import Employee


class TimesheetHandler(BaseHandler):
    def __init__(self, bot, users_data):
        super().__init__(bot, users_data)

    def handle_timesheet_main(self, message):
        self.set_user_state(message.chat.id, 'timesheet_main')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_add_employee = types.KeyboardButton('➕ Добавить работника')
        btn_remove_employee = types.KeyboardButton('🗑 Удалить работника')
        btn_manage_attendance = types.KeyboardButton('📝 Учет присутствия')
        btn_calculate_salary = types.KeyboardButton('💰 Расчет зарплаты')
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_add_employee, btn_remove_employee, btn_manage_attendance, btn_calculate_salary, btn_back)

        user_data = self.get_user_data(message.chat.id)
        employee_count = len(user_data.timesheet.employees)

        response = f"""
    📊 Раздел: ТАБЕЛЬ

    Количество работников: {employee_count}

    Выберите действие:
    • Добавить работника - внести нового сотрудника
    • Удалить работника - удалить сотрудника из табеля
    • Учет присутствия - отметить присутствие на сегодня
    • Расчет зарплаты - рассчитать зарплату за период
    """
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_add_employee(self, message):
        self.set_user_state(message.chat.id, 'waiting_employee_name')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_back)

        response = "👤 ДОБАВЛЕНИЕ РАБОТНИКА\n\nВведите ФИО работника:"
        self.bot.send_message(message.chat.id, response, reply_markup=markup)

    def handle_employee_name_input(self, message):
        chat_id = message.chat.id
        employee_name = message.text.strip()

        if not employee_name:
            self.bot.send_message(chat_id, "❌ Имя работника не может быть пустым.")
            return

        # Сохраняем имя и запрашиваем зарплату
        user_data = self.get_user_data(chat_id)
        user_data.temp_employee_name = employee_name
        self.set_user_state(chat_id, 'waiting_employee_salary')

        response = f"👤 Работник: {employee_name}\n\nВведите дневную ставку (зарплата за один день):"
        self.bot.send_message(chat_id, response)

    def handle_employee_salary_input(self, message):
        chat_id = message.chat.id
        text = message.text.strip()

        try:
            daily_salary = float(text)
            if daily_salary <= 0:
                raise ValueError("Зарплата должна быть положительным числом")

            user_data = self.get_user_data(chat_id)
            employee_name = getattr(user_data, 'temp_employee_name', '')

            if not employee_name:
                self.bot.send_message(chat_id, "❌ Ошибка: данные работника не найдены.")
                self.handle_timesheet_main(message)
                return

            # Добавляем работника
            from ..models.timesheet import Employee
            employee = Employee(name=employee_name, daily_salary=daily_salary)
            user_data.timesheet.employees[employee.id] = employee

            # АВТОСОХРАНЕНИЕ после добавления работника
            self._auto_save_user_data(chat_id)

            # Очищаем временные данные
            if hasattr(user_data, 'temp_employee_name'):
                delattr(user_data, 'temp_employee_name')

            self.bot.send_message(chat_id,
                                  f"✅ Работник добавлен!\nФИО: {employee.name}\nДневная ставка: {daily_salary} руб.")
            self.handle_timesheet_main(message)

        except ValueError:
            self.bot.send_message(chat_id, "❌ Ошибка: введите корректную сумму зарплаты (число больше 0)")

    def _auto_save_user_data(self, chat_id: int):
        """Автосохранение данных пользователя"""
        try:
            user_data = self.get_user_data(chat_id)
            from ..services.storage_service import JSONStorageService
            storage = JSONStorageService()
            storage.save_user_data(user_data)
        except Exception as e:
            print(f"Ошибка автосохранения: {e}")

    def handle_manage_attendance(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)

        if not user_data.timesheet.employees:
            self.bot.send_message(chat_id, "❌ Нет добавленных работников. Сначала добавьте работников.")
            self.handle_timesheet_main(message)
            return

        today = date.today()

        # Проверяем, не заблокирована ли уже сегодняшняя дата
        if user_data.timesheet.is_date_locked(today):
            self.bot.send_message(chat_id,
                                  f"❌ Учет присутствия на {today.strftime('%d.%m.%Y')} уже завершен и заблокирован для изменений.")
            self.handle_timesheet_main(message)
            return

        self.set_user_state(chat_id, 'managing_attendance')
        self._show_attendance_keyboard(chat_id, today)

    def _show_attendance_keyboard(self, chat_id: int, work_date: date):
        user_data = self.get_user_data(chat_id)
        employees = user_data.timesheet.get_all_employees()

        markup = types.InlineKeyboardMarkup()

        for employee in employees:
            # Получаем текущий статус присутствия
            attendance_status = "✅" if self._is_employee_present_today(user_data, employee.id, work_date) else "❌"

            button_text = f"{attendance_status} {employee.name} - {employee.daily_salary} руб./день"
            callback_data = f"toggle_attendance:{employee.id}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

        # Кнопка сохранения
        markup.add(
            types.InlineKeyboardButton("💾 Сохранить и заблокировать на сегодня", callback_data="save_attendance"))

        # Кнопка назад
        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_timesheet"))

        response = f"""
📝 УЧЕТ ПРИСУТСТВИЯ

Дата: {work_date.strftime('%d.%m.%Y')}

Отметьте присутствующих работников:
• ✅ - присутствовал
• ❌ - отсутствовал

После отметки нажмите "Сохранить"
"""
        self.bot.send_message(chat_id, response, reply_markup=markup)

    def _is_employee_present_today(self, user_data, employee_id: str, work_date: date) -> bool:
        """Проверяет, отмечен ли работник как присутствующий на указанную дату"""
        for record in user_data.timesheet.attendance_records:
            if record.employee_id == employee_id and record.work_date == work_date:
                return record.is_present
        return False

    def handle_attendance_callback(self, call):
        chat_id = call.message.chat.id
        data = call.data

        if data == "back_to_timesheet":
            self.bot.delete_message(chat_id, call.message.message_id)
            self.handle_timesheet_main(call.message)
            return

        if data == "save_attendance":
            self._save_attendance(call)
            return

        if data.startswith("toggle_attendance:"):
            self._toggle_attendance(call)
            return

    def _toggle_attendance(self, call):
        chat_id = call.message.chat.id
        employee_id = call.data.split(":")[1]
        today = date.today()

        user_data = self.get_user_data(chat_id)

        # Получаем текущий статус
        current_status = self._is_employee_present_today(user_data, employee_id, today)

        # Меняем статус
        user_data.timesheet.mark_attendance(employee_id, today, not current_status)

        # Обновляем клавиатуру
        self.bot.delete_message(chat_id, call.message.message_id)
        self._show_attendance_keyboard(chat_id, today)

    def _save_attendance(self, call):
        chat_id = call.message.chat.id
        today = date.today()

        user_data = self.get_user_data(chat_id)

        # Блокируем дату для изменений
        user_data.timesheet.lock_attendance_for_date(today)

        # Подсчитываем присутствующих
        present_count = sum(1 for record in user_data.timesheet.attendance_records
                            if record.work_date == today and record.is_present)

        self.bot.delete_message(chat_id, call.message.message_id)
        self.bot.send_message(chat_id,
                              f"✅ Учет присутствия на {today.strftime('%d.%m.%Y')} сохранен!\n\nПрисутствовало: {present_count} работников")
        self.handle_timesheet_main(call.message)

    def handle_calculate_salary(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)

        if not user_data.timesheet.employees:
            self.bot.send_message(chat_id, "❌ Нет добавленных работников.")
            self.handle_timesheet_main(message)
            return

        # Получаем текущий период
        start_date, end_date = user_data.timesheet.get_current_period()
        period_name = "1-15" if start_date.day == 1 else "16-конец месяца"

        response = f"""
💰 РАСЧЕТ ЗАРПЛАТЫ

Период: {period_name} {start_date.strftime('%B %Y')}
Даты: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}

Зарплата работников:
"""

        total_payout = 0
        employees = user_data.timesheet.get_all_employees()

        for employee in employees:
            salary = user_data.timesheet.calculate_salary_for_period(employee.id, start_date, end_date)
            working_days = len(
                [r for r in user_data.timesheet.get_attendance_for_period(employee.id, start_date, end_date)
                 if r.is_present])

            response += f"\n👤 {employee.name}\n"
            response += f"   📅 Отработано дней: {working_days}\n"
            response += f"   💰 Зарплата: {salary:.2f} руб.\n"
            response += f"   📊 Ставка: {employee.daily_salary} руб./день\n"

            total_payout += salary

        response += f"\n📈 ОБЩАЯ СУММА К ВЫПЛАТЕ: {total_payout:.2f} руб."

        self.bot.send_message(chat_id, response)
        self.handle_timesheet_main(message)

    def handle_remove_employee_menu(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)

        if not user_data.timesheet.employees:
            self.bot.send_message(chat_id, "❌ Нет добавленных работников.")
            self.handle_timesheet_main(message)
            return

        markup = types.InlineKeyboardMarkup()

        for employee in user_data.timesheet.get_all_employees():
            button_text = f"❌ {employee.name} - {employee.daily_salary} руб./день"
            callback_data = f"remove_employee:{employee.id}"
            markup.add(types.InlineKeyboardButton(button_text, callback_data=callback_data))

        markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_timesheet"))

        response = "🗑️ УДАЛЕНИЕ РАБОТНИКА\n\nВыберите работника для удаления:"
        self.bot.send_message(chat_id, response, reply_markup=markup)

    def handle_remove_employee_callback(self, call):
        chat_id = call.message.chat.id
        employee_id = call.data.split(":")[1]

        user_data = self.get_user_data(chat_id)
        employee = user_data.timesheet.get_employee(employee_id)

        if employee and user_data.timesheet.remove_employee(employee_id):
            self.bot.delete_message(chat_id, call.message.message_id)
            self.bot.send_message(chat_id, f"✅ Работник {employee.name} удален из табеля.")
            self.handle_timesheet_main(call.message)
        else:
            self.bot.send_message(chat_id, "❌ Ошибка при удалении работника.")
            self.handle_timesheet_main(call.message)