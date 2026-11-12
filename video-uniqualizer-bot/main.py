import asyncio
import logging
import ssl
import socket
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiohttp import ClientSession, TCPConnector
from bot.handlers import video_handler
from bot.config import TELEGRAM_BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Проверка "одной копии": бот занимает локальный порт 9090.
# Если порт занят - значит, где-то уже работает ещё одна копия
# (вторая мешает первой, Telegram отвечает Conflict).
_INSTANCE_PORT = 9090
_instance_socket = None


def _acquire_instance_lock() -> bool:
    global _instance_socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', _INSTANCE_PORT))
    except OSError:
        s.close()
        return False
    _instance_socket = s  # держим открытым до конца работы процесса
    return True


async def main():
    """Главная функция запуска бота"""
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен в .env файле!")
        return

    if not _acquire_instance_lock():
        logger.error("Похоже, бот уже запущен другой копией (порт занят). Закройте старое окно и запустите заново.")
        return

    logger.info("Запуск бота...")
    
    # Создаём SSL контекст с отключенной проверкой (для работы через VPN)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Создаём коннектор с нашим SSL контекстом
    connector = TCPConnector(ssl=ssl_context)
    
    # Создаём aiohttp сессию
    aiohttp_session = ClientSession(connector=connector)
    
    # Инициализация бота
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Заменяем стандартную сессию на нашу
    await bot.session.close()
    bot.session._session = aiohttp_session
    
    dp = Dispatcher()
    
    # Регистрируем роутеры
    dp.include_router(video_handler.router)
    
    logger.info("Подключение к Telegram API...")
    
    try:
        # Удаляем вебхук с ПОВТОРАМИ: VPN сразу после включения
        # может ещё устанавливать связь, и первая попытка часто падает.
        # Раньше один сбой убивал весь запуск - теперь ждём и повторяем.
        attempts = 20
        for attempt in range(1, attempts + 1):
            try:
                await bot.delete_webhook(drop_pending_updates=True)
                break
            except TelegramNetworkError as error:
                if attempt == attempts:
                    raise
                logger.warning(
                    f"Попытка {attempt}/{attempts} не удалась ({error}); "
                    "жду 5 секунд и пробую снова..."
                )
                await asyncio.sleep(5)

        logger.info("Бот успешно запущен и готов к работе!")
        
        await dp.start_polling(bot, polling_timeout=30)
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
        raise
    finally:
        await aiohttp_session.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
