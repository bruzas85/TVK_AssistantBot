import os
import logging
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


class SimpleStorageService:
    """Упрощенный сервис для хранения данных"""

    def __init__(self, session):
        self.session = session

    def add_running_task(self, user_id, task_text, priority="medium"):
        logger.info(f"Добавление задачи: {task_text} для пользователя {user_id}")
        return {"id": 1, "user_id": user_id, "task_text": task_text, "priority": priority}

    def get_running_tasks(self, user_id):
        return []


def check_and_run_migrations():
    """Проверяет и применяет необходимые миграции"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.warning("DATABASE_URL не установлен, пропускаем миграции")
            return

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    logger.info(f"Пользователь {user.first_name} запустил бота")

    welcome_text = (
        f"Привет, {user.first_name}! 👋\n\n"
        "Я TVK Assistant Bot - твой помощник в организации задач.\n\n"
        "📋 **Running List система в разработке**\n"
        "Скоро здесь будет управление повторяющимися задачами!\n\n"
        "Используй кнопки ниже для навигации."
    )

    keyboard = [
        [KeyboardButton("📋 Running List"), KeyboardButton("ℹ️ Помощь")],
        [KeyboardButton("➕ Добавить задачу")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🆘 **Помощь по TVK Assistant Bot**\n\n"
        "📋 **Running List (в разработке):**\n"
        "• Система повторяющихся задач\n"
        "• Приоритеты: 🟦 Низкий, 🟨 Средний, 🟥 Высокий, ⚡ Срочный\n"
        "• Статусы: ✅ Выполнено, 🔳 Частично, ❌ Отменено, ▶️ Перенесено\n\n"
        "⏳ **Скоро будет доступно!**"
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text

    if text == "📋 Running List":
        await update.message.reply_text("📋 Running list находится в разработке. Скоро будет доступен!")
    elif text == "➕ Добавить задачу":
        await update.message.reply_text("➕ Добавление задач будет доступно в следующем обновлении")
    elif text == "ℹ️ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text("Используйте кнопки для навигации")


def main():
    """Основная функция запуска бота"""
    try:
        logger.info("Запуск TVK Assistant Bot...")

        # Проверяем переменные окружения
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN не установлен!")
            return

        # Проверяем и применяем миграции
        check_and_run_migrations()

        # Создаем приложение
        application = Application.builder().token(token).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Запускаем бота
        logger.info("Бот запущен и готов к работе")
        application.run_polling()

    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}")
        raise


if __name__ == '__main__':
    main()