import logging
import os
from typing import List, Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler,
)

from .services.storage_service import StorageService
from .handlers.timesheet_handlers import TimesheetHandlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class Bot:
    def __init__(self, token: str):
        self.token = token
        self.storage_service = StorageService()
        self.application = Application.builder().token(token).build()

        # Инициализация обработчиков
        self.timesheet_handlers = TimesheetHandlers(self.storage_service)

        # Настройка хендлеров
        self.setup_handlers()

    def setup_handlers(self):
        """Настройка всех обработчиков бота"""

        # Базовые команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))

        # Обработчики табеля
        timesheet_handlers_list = self.timesheet_handlers.get_handlers()
        for handler in timesheet_handlers_list:
            self.application.add_handler(handler)

        # Обработчик неизвестных команд
        self.application.add_handler(MessageHandler(filters.COMMAND, self.unknown_command))

        # Обработчик текстовых сообщений (для fallback)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_text = (
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для управления табелем учета рабочего времени.\n\n"
            "Доступные команды:\n"
            "/timesheet - Управление табелем\n"
            "/help - Помощь\n\n"
            "Нажмите /timesheet чтобы начать работу с табелем."
        )

        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик команды /help"""
        help_text = (
            "📋 **Управление табелем учета рабочего времени**\n\n"
            "**Основные команды:**\n"
            "/start - Начать работу с ботом\n"
            "/timesheet - Меню управления табелем\n"
            "/help - Показать эту справку\n\n"
            "**Функции табеля:**\n"
            "• Добавление сотрудников в систему\n"
            "• Ежедневная отметка сотрудников\n"
            "• Просмотр текущего табеля\n"
            "• Автоматическое формирование отчетов по зарплате\n"
            "• Расчет заработной платы за периоды (1-15 и 16-конец месяца)\n\n"
            "**Как добавить сотрудника:**\n"
            "1. Нажмите /timesheet\n"
            "2. Выберите 'Добавить сотрудника'\n"
            "3. Введите данные в формате:\n"
            "   *ФИО;Должность;Оклад за день*\n"
            "   Пример: *Иванов Иван Иванович;Менеджер;1500*\n\n"
            "**Как отметить сотрудника:**\n"
            "1. Нажмите /timesheet\n"
            "2. Выберите 'Отметить сотрудника'\n"
            "3. Выберите сотрудника из списка\n"
            "4. Выберите статус работы\n\n"
            "Отчеты по зарплате генерируются автоматически при заполнении всех дней периода."
        )

        await update.message.reply_text(help_text)

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик текстовых сообщений"""
        # Если ожидается ввод сотрудника, пропускаем обработку
        if context.user_data.get('awaiting_employee'):
            return

        text = update.message.text
        response = (
            "Я понимаю только команды. Используйте /help для просмотра доступных команд.\n"
            "Или нажмите /timesheet для работы с табелем."
        )
        await update.message.reply_text(response)

    async def unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Обработчик неизвестных команд"""
        await update.message.reply_text(
            "Неизвестная команда. Используйте /help для просмотра доступных команд."
        )

    def run(self):
        """Запуск бота"""
        logger.info("Бот запущен")

        # Запуск бота
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )


def create_bot() -> Bot:
    """Фабрика для создания экземпляра бота"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

    return Bot(token)


if __name__ == "__main__":
    # Для прямого запуска файла
    try:
        bot = create_bot()
        bot.run()
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        raise