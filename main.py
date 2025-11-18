import os
import logging
from bot import create_bot

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Основная функция запуска бота"""
    try:
        logger.info("Запуск TVK Assistant Bot...")

        # Создание и запуск бота
        bot = create_bot()
        bot.run()

    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}")
        raise


if __name__ == "__main__":
    main()