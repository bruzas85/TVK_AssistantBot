import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

from database import init_db
from user_service import UserService

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных при запуске
init_db()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Сохраняем/обновляем пользователя в базе
    UserService.get_or_create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
        is_bot=user.is_bot
    )

    welcome_text = f"""
Привет, {user.first_name}! 👋

Я бот-помощник. Вот что я умею:

/start - Начать работу
/phone - Указать телефон
/email - Указать email
/mydata - Посмотреть мои данные
/clear - Очистить мои данные

Я сохраню все введенные данные, и они не пропадут при перезапуске!
    """

    await update.message.reply_text(welcome_text)


async def set_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Сохраняем состояние ожидания телефона
    UserService.save_user_state(user.id, "waiting_for_phone")

    await update.message.reply_text("📱 Пожалуйста, введите ваш номер телефона:")


async def set_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Сохраняем состояние ожидания email
    UserService.save_user_state(user.id, "waiting_for_email")

    await update.message.reply_text("📧 Пожалуйста, введите ваш email:")


async def show_my_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Получаем данные пользователя из базы
    user_data = UserService.get_user_data(user.id)

    if user_data:
        response = f"📊 Ваши данные:\n\n"
        response += f"🆔 ID: {user_data.user_id}\n"
        response += f"👤 Имя: {user_data.first_name or 'Не указано'}\n"
        response += f"📛 Фамилия: {user_data.last_name or 'Не указано'}\n"
        response += f"🌐 Username: @{user_data.username or 'Не указан'}\n"
        response += f"📱 Телефон: {user_data.phone or 'Не указан'}\n"
        response += f"📧 Email: {user_data.email or 'Не указан'}\n"
        response += f"🕐 Зарегистрирован: {user_data.created_at.strftime('%d.%m.%Y %H:%M')}"

        if user_data.preferences:
            response += f"\n\n⭐ Предпочтения: {user_data.preferences}"
    else:
        response = "❌ У нас нет сохраненных данных о вас. Используйте /start"

    await update.message.reply_text(response)


async def clear_my_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Очищаем дополнительные данные (но не удаляем пользователя)
    UserService.update_user_data(
        user_id=user.id,
        phone=None,
        email=None,
        preferences={}
    )
    UserService.clear_user_state(user.id)

    await update.message.reply_text("✅ Ваши дополнительные данные очищены!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text

    # Проверяем состояние пользователя
    user_state = UserService.get_user_state(user.id)

    if user_state and user_state.state == "waiting_for_phone":
        # Сохраняем телефон
        UserService.update_user_data(user_id=user.id, phone=message_text)
        UserService.clear_user_state(user.id)
        await update.message.reply_text("✅ Телефон успешно сохранен!")

    elif user_state and user_state.state == "waiting_for_email":
        # Сохраняем email
        UserService.update_user_data(user_id=user.id, email=message_text)
        UserService.clear_user_state(user.id)
        await update.message.reply_text("✅ Email успешно сохранен!")

    else:
        # Обычное сообщение - сохраняем в историю или обрабатываем
        await update.message.reply_text("💬 Сообщение получено! Используйте команды для управления данными.")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Ошибка при обработке update {update}: {context.error}")


def main():
    # Получаем токен бота из переменных окружения
    token = os.environ.get('TELEGRAM_BOT_TOKEN')

    if not token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения!")
        return

    # Создаем приложение
    application = Application.builder().token(token).build()

    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("phone", set_phone))
    application.add_handler(CommandHandler("email", set_email))
    application.add_handler(CommandHandler("mydata", show_my_data))
    application.add_handler(CommandHandler("clear", clear_my_data))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    application.run_polling()


if __name__ == '__main__':
    main()