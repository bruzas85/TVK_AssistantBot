import logging
from datetime import date, datetime, timedelta
from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, CommandHandler

from ..services.storage_service import StorageService
from ..models.employee import Employee
from ..models.timesheet import TimesheetEntry, WorkStatus
from ..models.salary_report import SalaryReport

logger = logging.getLogger(__name__)


class TimesheetHandlers:
    def __init__(self, storage_service: StorageService):
        self.storage_service = storage_service

    def get_handlers(self) -> List:
        return [
            CommandHandler("timesheet", self.timesheet_menu),
            CallbackQueryHandler(self.handle_timesheet_callback, pattern="^timesheet_"),
            CallbackQueryHandler(self.handle_employee_select, pattern="^select_employee_"),
            CallbackQueryHandler(self.handle_status_select, pattern="^status_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_employee_input)
        ]

    async def timesheet_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главное меню табеля"""
        keyboard = [
            [InlineKeyboardButton("📝 Отметить сотрудника", callback_data="timesheet_mark")],
            [InlineKeyboardButton("👥 Добавить сотрудника", callback_data="timesheet_add_employee")],
            [InlineKeyboardButton("📊 Посмотреть табель", callback_data="timesheet_view")],
            [InlineKeyboardButton("💰 Отчет по зарплате", callback_data="timesheet_salary_report")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📋 Управление табелем учета рабочего времени:\n\n"
            "• Отметить сотрудника - внести отметку о работе на сегодня\n"
            "• Добавить сотрудника - добавить нового сотрудника в систему\n"
            "• Посмотреть табель - просмотреть текущий табель\n"
            "• Отчет по зарплате - сформировать отчет по заработной плате",
            reply_markup=reply_markup
        )

    async def handle_timesheet_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback от меню табеля"""
        query = update.callback_query
        await query.answer()

        data = query.data
        today = date.today()

        if data == "timesheet_mark":
            await self._show_employee_selection(query, today, "mark")
        elif data == "timesheet_add_employee":
            await query.edit_message_text(
                "Введите данные сотрудника в формате:\n"
                "ФИО;Должность;Оклад за день\n\n"
                "Пример:\n"
                "Иванов Иван Иванович;Менеджер;1500"
            )
            context.user_data['awaiting_employee'] = True
        elif data == "timesheet_view":
            await self._show_timesheet_view(query)
        elif data == "timesheet_salary_report":
            await self._generate_salary_report(query, today)

    async def _show_employee_selection(self, query, for_date: date, action: str):
        """Показывает список сотрудников для выбора"""
        employees = self.storage_service.get_all_employees()
        active_employees = [emp for emp in employees if emp.is_active]

        if not active_employees:
            await query.edit_message_text("Нет активных сотрудников. Добавьте сотрудников сначала.")
            return

        keyboard = []
        for employee in active_employees:
            # Проверяем, отмечен ли уже сотрудник на сегодня
            timesheet = self.storage_service.get_or_create_timesheet(employee.id, for_date)
            is_marked = timesheet.is_date_marked(for_date)

            status_icon = "✅" if is_marked else "⏳"
            callback_data = f"select_employee_{employee.id}_{for_date}_{action}"

            keyboard.append([InlineKeyboardButton(
                f"{status_icon} {employee.name} ({employee.position})",
                callback_data=callback_data
            )])

        keyboard.append([InlineKeyboardButton("« Назад", callback_data="timesheet_back")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Выберите сотрудника для отметки на {for_date.strftime('%d.%m.%Y')}:",
            reply_markup=reply_markup
        )

    async def handle_employee_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора сотрудника"""
        query = update.callback_query
        await query.answer()

        data = query.data
        parts = data.split('_')
        employee_id = parts[2]
        selected_date = date.fromisoformat(parts[3])
        action = parts[4]

        employee = self.storage_service.get_employee(employee_id)
        if not employee:
            await query.edit_message_text("Сотрудник не найден.")
            return

        if action == "mark":
            # Проверяем, не отмечен ли уже сотрудник
            timesheet = self.storage_service.get_or_create_timesheet(employee_id, selected_date)
            if timesheet.is_date_marked(selected_date):
                await query.edit_message_text(
                    f"Сотрудник {employee.name} уже отмечен в табеле на {selected_date.strftime('%d.%m.%Y')}."
                )
                return

            # Показываем выбор статуса
            keyboard = [
                [
                    InlineKeyboardButton("✅ Работал", callback_data=f"status_{employee_id}_{selected_date}_worked"),
                    InlineKeyboardButton("❌ Отсутствовал", callback_data=f"status_{employee_id}_{selected_date}_absent")
                ],
                [
                    InlineKeyboardButton("🏥 Больничный", callback_data=f"status_{employee_id}_{selected_date}_sick"),
                    InlineKeyboardButton("🏖 Отпуск", callback_data=f"status_{employee_id}_{selected_date}_vacation")
                ],
                [InlineKeyboardButton("« Назад", callback_data="timesheet_mark")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"Выберите статус для {employee.name} на {selected_date.strftime('%d.%m.%Y')}:",
                reply_markup=reply_markup
            )

    async def handle_status_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора статуса работы"""
        query = update.callback_query
        await query.answer()

        data = query.data
        parts = data.split('_')
        employee_id = parts[1]
        selected_date = date.fromisoformat(parts[2])
        status = parts[3]

        employee = self.storage_service.get_employee(employee_id)
        if not employee:
            await query.edit_message_text("Сотрудник не найден.")
            return

        # Создаем запись в табеле
        timesheet = self.storage_service.get_or_create_timesheet(employee_id, selected_date)
        entry = TimesheetEntry(
            employee_id=employee_id,
            date=selected_date,
            status=WorkStatus(status)
        )
        timesheet.add_entry(entry)
        self.storage_service.save_timesheet(timesheet)

        status_texts = {
            'worked': 'работал',
            'absent': 'отсутствовал',
            'sick': 'на больничном',
            'vacation': 'в отпуске'
        }

        await query.edit_message_text(
            f"✅ Сотрудник {employee.name} отмечен как {status_texts[status]} "
            f"на {selected_date.strftime('%d.%m.%Y')}"
        )

        # Проверяем, нужно ли генерировать отчет по зарплате
        await self._check_and_generate_salary_report(selected_date, context)

    async def handle_employee_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода данных сотрудника"""
        if not context.user_data.get('awaiting_employee'):
            return

        text = update.message.text
        parts = [part.strip() for part in text.split(';')]

        if len(parts) != 3:
            await update.message.reply_text(
                "Неверный формат. Используйте:\n"
                "ФИО;Должность;Оклад за день\n\n"
                "Пример:\n"
                "Иванов Иван Иванович;Менеджер;1500"
            )
            return

        try:
            name, position, salary_str = parts
            daily_salary = float(salary_str)

            # Создаем ID сотрудника (можно улучшить)
            employee_id = f"emp_{len(self.storage_service.get_all_employees()) + 1:04d}"

            employee = Employee(
                id=employee_id,
                name=name,
                position=position,
                daily_salary=daily_salary
            )

            self.storage_service.save_employee(employee)

            context.user_data['awaiting_employee'] = False
            await update.message.reply_text(
                f"✅ Сотрудник добавлен:\n"
                f"ФИО: {name}\n"
                f"Должность: {position}\n"
                f"Оклад за день: {daily_salary} руб."
            )

        except ValueError:
            await update.message.reply_text("Оклад должен быть числом. Попробуйте снова.")

    async def _check_and_generate_salary_report(self, marked_date: date, context: ContextTypes.DEFAULT_TYPE):
        """Проверяет и генерирует отчет по зарплате при необходимости"""
        day = marked_date.day
        month = marked_date.month
        year = marked_date.year

        # Определяем период
        if 1 <= day <= 15:
            period_start = date(year, month, 1)
            period_end = date(year, month, 15)
        else:
            # Последний день месяца
            if month == 12:
                period_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(year, month + 1, 1) - timedelta(days=1)
            period_start = date(year, month, 16)

        # Проверяем, не создан ли уже отчет
        if self.storage_service.is_report_exists(period_start, period_end):
            return

        # Проверяем, все ли дни периода заполнены
        employees = self.storage_service.get_all_employees()
        all_marked = True

        for employee in employees:
            if not employee.is_active:
                continue

            timesheet = self.storage_service.get_or_create_timesheet(employee.id, marked_date)
            current_date = period_start
            while current_date <= period_end:
                if not timesheet.is_date_marked(current_date):
                    all_marked = False
                    break
                current_date += timedelta(days=1)

            if not all_marked:
                break

        if all_marked:
            await self._generate_salary_report_period(period_start, period_end, context)

    async def _generate_salary_report_period(self, period_start: date, period_end: date,
                                             context: ContextTypes.DEFAULT_TYPE):
        """Генерирует отчет по зарплате за период"""
        report = SalaryReport(
            period_start=period_start,
            period_end=period_end,
            generated_at=date.today(),
            entries=[]
        )

        employees = self.storage_service.get_all_employees()

        for employee in employees:
            if not employee.is_active:
                continue

            timesheet = self.storage_service.get_or_create_timesheet(employee.id, period_start)
            period_entries = timesheet.get_entries_for_period(period_start, period_end)

            # Расчет зарплаты
            total_salary = 0
            for entry in period_entries:
                if entry.status == WorkStatus.WORKED:
                    total_salary += employee.daily_salary
                # Можно добавить логику для других статусов

            report.add_employee_calculation(employee, period_entries, total_salary)

        # Сохраняем отчет
        self.storage_service.save_salary_report(report)

        # Отправляем уведомление
        total_payroll = report.get_total_payroll()
        message = (
            f"📊 Автоматически сгенерирован отчет по зарплате:\n"
            f"Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n"
            f"Общий ФОТ: {total_payroll:.2f} руб.\n"
            f"Количество сотрудников: {len(report.entries)}"
        )

        # Здесь можно добавить отправку сообщения админу
        # await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)

    async def _show_timesheet_view(self, query):
        """Показывает текущий табель"""
        today = date.today()
        employees = self.storage_service.get_all_employees()

        message = f"📋 Табель на {today.strftime('%B %Y')}:\n\n"

        for employee in employees:
            if not employee.is_active:
                continue

            timesheet = self.storage_service.get_or_create_timesheet(employee.id, today)

            # Подсчитываем рабочие дни в текущем месяце
            worked_days = len([e for e in timesheet.entries if e.status == WorkStatus.WORKED])
            total_days = len(timesheet.entries)

            message += (
                f"👤 {employee.name}\n"
                f"   Должность: {employee.position}\n"
                f"   Отмечено дней: {total_days}\n"
                f"   Рабочих дней: {worked_days}\n"
                f"   Оклад за день: {employee.daily_salary} руб.\n\n"
            )

        await query.edit_message_text(message)

    async def _generate_salary_report(self, query, for_date: date):
        """Генерирует отчет по зарплате по запросу"""
        # Определяем последний завершенный период
        if for_date.day <= 15:
            period_start = date(for_date.year, for_date.month, 1)
            period_end = date(for_date.year, for_date.month, 15)
        else:
            period_start = date(for_date.year, for_date.month, 16)
            if for_date.month == 12:
                period_end = date(for_date.year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(for_date.year, for_date.month + 1, 1) - timedelta(days=1)

        report = self.storage_service.get_salary_report(period_start, period_end)

        if not report:
            await query.edit_message_text(
                f"Отчет за период {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')} не найден."
            )
            return

        message = (
            f"💰 Отчет по заработной плате\n"
            f"Период: {period_start.strftime('%d.%m.%Y')} - {period_end.strftime('%d.%m.%Y')}\n"
            f"Сгенерирован: {report.generated_at.strftime('%d.%m.%Y')}\n\n"
        )

        for entry in report.entries:
            message += (
                f"👤 {entry['employee_name']}\n"
                f"   Должность: {entry['employee_position']}\n"
                f"   Оклад за день: {entry['daily_salary']} руб.\n"
                f"   Отработано дней: {entry['worked_days']}\n"
                f"   Отсутствовал: {entry['absent_days']}\n"
                f"   Больничный: {entry['sick_days']}\n"
                f"   Отпуск: {entry['vacation_days']}\n"
                f"   К выплате: {entry['total_salary']:.2f} руб.\n\n"
            )

        message += f"📊 Общий ФОТ: {report.get_total_payroll():.2f} руб."

        await query.edit_message_text(message)