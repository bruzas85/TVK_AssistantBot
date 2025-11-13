from bot.bot import FinanceBot

# Замените 'YOUR_TELEGRAM_BOT_TOKEN' на реальный токен вашего бота
BOT_TOKEN = '8160851122:AAF8GaJ72Cdnkz8IAuZo402Eaxv6WaTctdo'

if __name__ == '__main__':
    bot = FinanceBot(BOT_TOKEN)
    bot.run()