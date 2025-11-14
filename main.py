import os
import threading

try:
    from flask import Flask
except ImportError:
    print("⚠️ Flask не установлен, запускаем без web-сервера")
    Flask = None

from bot.bot import FinanceBot

# Получаем токен из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')


def run_flask():
    """Запускает Flask сервер если установлен"""
    if Flask is not None:
        app = Flask(__name__)

        @app.route('/')
        def home():
            return "Bot is running!"

        @app.route('/health')
        def health():
            return "OK"

        port = int(os.getenv('PORT', 5000))
        app.run(host='0.0.0.0', port=port)
    else:
        print("ℹ️ Flask не установлен, web-сервер не запущен")


if __name__ == '__main__':
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        print("💡 Установите переменную окружения BOT_TOKEN на Railway")
        exit(1)

    print(f"✅ BOT_TOKEN получен, запуск бота...")

    # Запускаем Flask в отдельном потоке если он установлен
    if Flask is not None:
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        print("✅ Web-сервер запущен")
    else:
        print("ℹ️ Web-сервер не запущен (Flask не установлен)")

    # Запускаем бота
    bot = FinanceBot(BOT_TOKEN)
    bot.run()