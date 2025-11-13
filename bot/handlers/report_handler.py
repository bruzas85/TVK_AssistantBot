import os
from datetime import datetime, timedelta
from telebot import types
from .base_handler import BaseHandler


class ReportHandler(BaseHandler):
    def __init__(self, bot, users_data):
        super().__init__(bot, users_data)

    def create_expense_report(self, chat_id, period_days=30):
        user_data = self.get_user_data(chat_id)
        recent_expenses = user_data.get_expenses_by_period(period_days)

        if not recent_expenses:
            return None, f"За последние {period_days} дней расходов не найдено."

        total_amount = sum(exp.amount for exp in recent_expenses)

        categories = {}
        for exp in recent_expenses:
            if exp.category not in categories:
                categories[exp.category] = 0
            categories[exp.category] += exp.amount

        filename = f"expense_report_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"ОТЧЕТ ПО РАСХОДАМ\n")
            f.write(f"Период: последние {period_days} дней\n")
            f.write(f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write("=" * 50 + "\n\n")

            f.write(f"ОБЩАЯ СУММА: {total_amount} руб.\n\n")

            f.write("РАСХОДЫ ПО КАТЕГОРИЯМ:\n")
            for category, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                percentage = (amount / total_amount) * 100
                f.write(f"{category}: {amount} руб. ({percentage:.1f}%)\n")

            f.write("\nДЕТАЛИЗАЦИЯ:\n")
            for exp in sorted(recent_expenses, key=lambda x: x.date, reverse=True):
                date_str = exp.date.strftime('%d.%m.%Y')
                f.write(f"{date_str} | {exp.category} | {exp.amount} руб. | {exp.description}\n")

        report_text = f"📊 ОТЧЕТ ПО РАСХОДАМ\n\nПериод: последние {period_days} дней\nОбщая сумма: {total_amount} руб.\n\nОсновные категории:\n"
        for category, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
            percentage = (amount / total_amount) * 100
            report_text += f"• {category}: {amount} руб. ({percentage:.1f}%)\n"

        return filename, report_text

    def handle_calculate_expenses(self, message):
        chat_id = message.chat.id

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_week = types.KeyboardButton('неделя')
        btn_month = types.KeyboardButton('месяц')
        btn_3months = types.KeyboardButton('3 месяца')
        btn_back = types.KeyboardButton('назад')
        markup.add(btn_week, btn_month, btn_3months, btn_back)

        response = "📈 РАСЧЕТ РАСХОДОВ\n\nВыберите период для отчета:\n• неделя - расходы за 7 дней\n• месяц - расходы за 30 дней\n• 3 месяца - расходы за 90 дней"
        self.bot.send_message(chat_id, response, reply_markup=markup)
        self.set_user_state(chat_id, 'waiting_period')

    def handle_clear_data(self, message):
        chat_id = message.chat.id
        user_data = self.get_user_data(chat_id)

        if not user_data.expenses:
            self.bot.send_message(chat_id, "❌ Нет данных для очистки. Расходы отсутствуют.")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_yes = types.KeyboardButton('ДА, очистить всё')
        btn_no = types.KeyboardButton('НЕТ, отменить')
        markup.add(btn_yes, btn_no)

        total_expenses = len(user_data.expenses)
        total_amount = user_data.get_total_expenses()
        dates = [exp.date for exp in user_data.expenses]

        response = f"⚠️ **ПОДТВЕРЖДЕНИЕ ОЧИСТКИ ДАННЫХ**\n\nВы собираетесь удалить ВСЕ данные по расходам:\n\n📊 Статистика:\n• Количество записей: {total_expenses}\n• Общая сумма: {total_amount} руб.\n• Период: с {min(dates).strftime('%d.%m.%Y')} по {max(dates).strftime('%d.%m.%Y')}\n\n❓ **Вы уверены, что хотите удалить все данные?**\nЭта операция необратима!\n\nВыберите действие:"
        self.bot.send_message(chat_id, response, reply_markup=markup)
        self.set_user_state(chat_id, 'waiting_clear_confirmation')

    def execute_clear_data(self, chat_id):
        user_data = self.get_user_data(chat_id)
        return user_data.clear_expenses()