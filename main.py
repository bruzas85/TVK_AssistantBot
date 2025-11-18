import os
import logging
import sys
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def check_environment():
    """Проверяет необходимые переменные окружения"""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    database_url = os.getenv('DATABASE_URL')

    logger.info("Проверка переменных окружения:")
    logger.info(f"TELEGRAM_BOT_TOKEN: {'✅ Установлен' if token else '❌ Отсутствует'}")
    logger.info(f"DATABASE_URL: {'✅ Установлен' if database_url else '❌ Отсутствует'}")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не найден! Добавьте его в Variables на Railway")
        return False

    return True


def check_and_run_migrations():
    """Проверяет и применяет необходимые миграции"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("DATABASE_URL не установлен, пропускаем миграции")
            return

        logger.info("Проверка и выполнение миграций БД...")
        engine = create_engine(database_url)

        with engine.connect() as conn:
            # Проверяем существование таблицы
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'running_tasks'
                );
            """))
            table_exists = result.scalar()

            if not table_exists:
                logger.info("Создаем таблицу running_tasks...")
                conn.execute(text("""
                    CREATE TABLE running_tasks (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        task_text TEXT NOT NULL,
                        priority VARCHAR(20) DEFAULT 'medium',
                        days_of_week TEXT,
                        status_history TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
                conn.commit()
                logger.info("✅ Таблица running_tasks создана")
            else:
                logger.info("✅ Таблица running_tasks уже существует")

    except Exception as e:
        logger.error(f"Ошибка при применении миграций: {e}")


class SimpleStorageService:
    """Упрощенный сервис для хранения данных"""

    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if self.database_url:
            self.engine = create_engine(self.database_url)
            self.Session = sessionmaker(bind=self.engine)
        else:
            self.engine = None
            self.Session = None

    def add_running_task(self, user_id, task_text, priority="medium"):
        logger.info(f"Добавление задачи: {task_text} для пользователя {user_id}")
        # Временная реализация
        return {"id": 1, "user_id": user_id, "task_text": task_text, "priority": priority}

    def get_running_tasks(self, user_id):
        return []


# Глобальный экземпляр storage
storage_service = SimpleStorageService()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} (ID: {user.id}) запустил бота")

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я TVK Assistant Bot - твой помощник в организации задач.\n\n"
        "🚀 **Running List система АКТИВНА**\n"
        "Теперь с обновленным функционалом!\n\n"
        "📋 Используй кнопки ниже для работы с задачами."
    )

    keyboard = [
        [KeyboardButton("📋 Running List"), KeyboardButton("ℹ️ Помощь")],
        [KeyboardButton("➕ Добавить задачу"), KeyboardButton("🔄 Обновить")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🆘 **Помощь по TVK Assistant Bot**\n\n"
        "📋 **Running List система:**\n"
        "• Создавайте повторяющиеся задачи\n"
        "• Приоритеты: 🟦 Низкий, 🟨 Средний, 🟥 Высокий, ⚡ Срочный\n"
        "• Отслеживайте выполнение по дням недели\n"
        "• Статусы: ✅ Выполнено, 🔳 Частично, ❌ Отменено, ▶️ Перенесено\n\n"
        "✨ **Новый функционал из ветки development!**\n\n"
        "🔧 **Команды:**\n"
        "/start - Перезапустить бота\n"
        "/help - Показать справку\n"
        "/running_list - Показать список задач"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def running_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /running_list"""
    user = update.effective_user
    logger.info(f"Пользователь {user.id} запросил running list")

    # Временная реализация - показываем, что функционал в разработке
    message = (
        "📋 **Running List**\n\n"
        "🔄 Функционал обновляется...\n\n"
        "Скоро здесь будет:\n"
        "• Список ваших задач\n"
        "• Приоритеты и дни выполнения\n"
        "• Статусы выполнения\n"
        "• Управление задачами\n\n"
        "⏳ Ожидайте следующего обновления!"
    )

    await update.message.reply_text(message, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user = update.effective_user

    logger.info(f"Сообщение от {user.first_name}: {text}")

    if text == "📋 Running List":
        await running_list_command(update, context)
    elif text == "➕ Добавить задачу":
        await update.message.reply_text(
            "➕ **Добавление задачи**\n\n"
            "Эта функция скоро будет доступна!\n"
            "Вы сможете создавать задачи с приоритетами и назначать дни выполнения.",
            parse_mode='Markdown'
        )
    elif text == "🔄 Обновить":
        await update.message.reply_text("🔄 Бот обновлен! Используйте /start для перезагрузки")
    elif text == "ℹ️ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text(
            "🤔 Не понял ваше сообщение.\n"
            "Используйте кнопки или команды:\n"
            "/start - Перезапуск\n"
            "/help - Помощь\n"
            "/running_list - Список задач"
        )


def main():
    """Основная функция запуска бота"""
    try:
        logger.info("=" * 50)
        logger.info("ЗАПУСК TVK ASSISTANT BOT")
        logger.info("Ветка: development")
        logger.info("=" * 50)

        # Проверяем переменные окружения
        if not check_environment():
            logger.error("❌ Не удалось запустить бота: отсутствуют необходимые переменные")
            return

        # Получаем токен
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        logger.info("✅ TELEGRAM_BOT_TOKEN получен успешно")

        # Проверяем и применяем миграции
        check_and_run_migrations()

        # Создаем приложение
        application = Application.builder().token(token).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("running_list", running_list_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Запускаем бота
        logger.info("✅ Бот запущен и готов к работе")
        logger.info("⏳ Ожидаем сообщения...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            close_loop=False,
            stop_signals=None  # Отключаем обработку сигналов остановки
        )

    except Exception as e:
        logger.critical(f"❌ Критическая ошибка при запуске бота: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()