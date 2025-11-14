import os
import threading
from flask import Flask
from bot.bot import FinanceBot

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Простой HTTP сервер для здоровья приложения
app = Flask(__name__)


@app.route('/')
def home():
    return "Bot is running!"


@app.route('/health')
def health():
    return "OK"


def run_flask():
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        print("💡 Установите переменную окружения BOT_TOKEN на Railway")
        exit(1)

    print(f"✅ BOT_TOKEN получен, запуск бота...")

    # Запускаем Flask в отдельном потоке для Railway
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Запускаем бота
    bot = FinanceBot(BOT_TOKEN)
    bot.run()