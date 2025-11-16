import os
import logging
from datetime import date
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

from database import init_db
from user_service import UserService
from task_service import TaskService

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

Я бот для управления задачами (Running List). Вот что я умею:

📅 **Управление задачами:**
/tasks - Посмотреть running list на неделю
/newtask - Создать новую задачу
/completetask - Отметить выполнение задачи сегодня

👤 **Управление данными:**
/phone - Указать телефон
/email - Указать email
/mydata - Посмотреть мои данные
/clear - Очистить мои данные

Все задачи сохраняются и не пропадут при перезапуске!
    """

    await update.message.reply_text(welcome_text)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает running list на неделю"""
    user = update.effective_user

    # Получаем задачи на неделю
    week_tasks = TaskService.get_week_tasks(user.id)

    if not any(len(day_data['tasks']) > 0 for day_data in week_tasks.values()):
        await update.message.reply_text(
            "📝 У вас пока нет задач на эту неделю.\n\n"
            "Создайте первую задачу с помощью /newtask"
        )
        return

    # Форматируем отображение
    tasks_display = TaskService.format_week_tasks_display(week_tasks)
    await update.message.reply_text(tasks_display, parse_mode='Markdown')


async def new_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс создания новой задачи"""
    user = update.effective_user

    # Сохраняем состояние
    UserService.save_user_state(user.id, "waiting_for_task_title")

    await update.message.reply_text(
        "📝 Создание новой задачи:\n\n"
        "Введите название задачи:"
    )


async def complete_task_day_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмечает выполнение задачи за сегодня"""
    user = update.effective_user

    # Получаем задачи на сегодня
    today = date.today().weekday()
    task_days = TaskService.get_tasks_for_day(user.id, today)

    if not task_days:
        await update.message.reply_text("✅ На сегодня задач нет!")
        return

    # Создаем клавиатуру для выбора задачи
    keyboard = []
    for task_day in task_days:
        task = task_day.task
        keyboard.append([f"✅ {task.title}"])

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    UserService.save_user_state(user.id, "waiting_for_task_completion")

    await update.message.reply_text(
        "Выберите задачу для отметки выполнения:",
        reply_markup=reply_markup
    )


async def move_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переносит задачу на следующий день"""
    user = update.effective_user

    # Получаем задачи на сегодня
    today = date.today().weekday()
    task_days = TaskService.get_tasks_for_day(user.id, today)

    if not task_days:
        await update.message.reply_text("📝 На сегодня задач для переноса нет!")
        return

    # Создаем клавиатуру для выбора задачи
    keyboard = []
    for task_day in task_days:
        task = task_day.task
        keyboard.append([f"➡️ {task.title}"])

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    UserService.save_user_state(user.id, "waiting_for_task_move")

    await update.message.reply_text(
        "Выберите задачу для переноса на завтра:",
        reply_markup=reply_markup
    )


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

    if user_state and user_state.state == "waiting_for_task_title":
        # Сохраняем название задачи и запрашиваем день
        context.user_data['new_task_title'] = message_text
        UserService.save_user_state(user.id, "waiting_for_task_day")

        keyboard = [
            ['Пн', 'Вт', 'Ср'],
            ['Чт', 'Пт', 'Сб'],
            ['Вс']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        await update.message.reply_text(
            "Выберите день недели для задачи:",
            reply_markup=reply_markup
        )

    elif user_state and user_state.state == "waiting_for_task_day":
        # Обрабатываем выбор дня
        day_mapping = {'Пн': 0, 'Вт': 1, 'Ср': 2, 'Чт': 3, 'Пт': 4, 'Сб': 5, 'Вс': 6}
        day_of_week = day_mapping.get(message_text)

        if day_of_week is not None:
            context.user_data['new_task_day'] = day_of_week
            UserService.save_user_state(user.id, "waiting_for_task_priority")

            keyboard = [
                ['🟦 Низкий', '🟨 Средний'],
                ['🟥 Высокий', '⚡ Срочный']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

            await update.message.reply_text(
                "Выберите приоритет задачи:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("Пожалуйста, выберите день из предложенных вариантов")

    elif user_state and user_state.state == "waiting_for_task_priority":
        # Обрабатываем выбор приоритета и создаем задачу
        priority_mapping = {
            '🟦 Низкий': 'low',
            '🟨 Средний': 'medium',
            '🟥 Высокий': 'high',
            '⚡ Срочный': 'urgent'
        }

        priority = priority_mapping.get(message_text, 'medium')
        title = context.user_data.get('new_task_title')
        day_of_week = context.user_data.get('new_task_day')

        if title and day_of_week is not None:
            task = TaskService.create_task(
                user_id=user.id,
                title=title,
                day_of_week=day_of_week,
                priority=priority
            )

            if task:
                UserService.clear_user_state(user.id)
                # Очищаем временные данные
                context.user_data.pop('new_task_title', None)
                context.user_data.pop('new_task_day', None)

                await update.message.reply_text(
                    f"✅ Задача создана!\n\n"
                    f"Название: {title}\n"
                    f"День: {TaskService.DAYS_OF_WEEK[day_of_week]}\n"
                    f"Приоритет: {TaskService.PRIORITY_SYMBOLS[priority]}\n\n"
                    f"Посмотреть все задачи: /tasks"
                )
            else:
                await update.message.reply_text("❌ Ошибка при создании задачи")
        else:
            await update.message.reply_text("❌ Ошибка: данные задачи не найдены")

    elif user_state and user_state.state == "waiting_for_task_completion":
        # Обрабатываем завершение задачи
        task_title = message_text[2:]  # Убираем "✅ "

        # Находим задачу
        today = date.today().weekday()
        task_days = TaskService.get_tasks_for_day(user.id, today)

        for task_day in task_days:
            if task_day.task.title == task_title:
                TaskService.update_task_status(
                    user_id=user.id,
                    task_id=task_day.task_id,
                    day_of_week=today,
                    status='completed'
                )

                UserService.clear_user_state(user.id)
                await update.message.reply_text(f"✅ Задача '{task_title}' выполнена!")
                return

        await update.message.reply_text("❌ Задача не найдена")

    elif user_state and user_state.state == "waiting_for_task_move":
        # Обрабатываем перенос задачи
        task_title = message_text[2:]  # Убираем "➡️ "

        # Находим задачу
        today = date.today().weekday()
        task_days = TaskService.get_tasks_for_day(user.id, today)

        for task_day in task_days:
            if task_day.task.title == task_title:
                TaskService.update_task_status(
                    user_id=user.id,
                    task_id=task_day.task_id,
                    day_of_week=today,
                    status='moved'
                )

                UserService.clear_user_state(user.id)
                await update.message.reply_text(f"➡️ Задача '{task_title}' перенесена на завтра!")
                return

        await update.message.reply_text("❌ Задача не найдена")

    elif user_state and user_state.state == "waiting_for_phone":
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
        await update.message.reply_text(
            "💬 Сообщение получено!\n\n"
            "Используйте команды для управления задачами:\n"
            "/tasks - посмотреть running list\n"
            "/newtask - создать задачу\n"
            "/completetask - отметить выполнение"
        )


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

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))

    # Обработчики для задач
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("newtask", new_task_command))
    application.add_handler(CommandHandler("completetask", complete_task_day_command))
    application.add_handler(CommandHandler("movetask", move_task_command))

    # Обработчики для пользовательских данных
    application.add_handler(CommandHandler("phone", set_phone))
    application.add_handler(CommandHandler("email", set_email))
    application.add_handler(CommandHandler("mydata", show_my_data))
    application.add_handler(CommandHandler("clear", clear_my_data))

    # Обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    # Запускаем бота
    logger.info("🤖 Бот запускается...")
    application.run_polling()


if __name__ == '__main__':
    main()