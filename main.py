import os
from bot.bot import FinanceBot

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        print("💡 Установите переменную окружения BOT_TOKEN на Railway")
        exit(1)

    print(f"✅ BOT_TOKEN получен, запуск бота...")

    # Запускаем бота
    bot = FinanceBot(BOT_TOKEN)

    # Обновляем метод run для облака
    print("🚀 Бот запускается на Railway...")
    try:
        bot.run()
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")
        print("🔄 Перезапуск через 10 секунд...")
        import time

        time.sleep(10)