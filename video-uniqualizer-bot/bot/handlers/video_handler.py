from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.exceptions import TelegramNetworkError
import asyncio
import os
import logging
import aiofiles
from datetime import datetime
from bot.services.video_processor import VideoProcessor
from bot.config import TEMP_DIR, PROCESSED_DIR, MAX_VIDEO_DURATION, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)
router = Router()
video_processor = VideoProcessor()


async def _safe_edit(message_status: Message, text: str):
    """Обновляет статусное сообщение; сбой сети больше не роняет обработку"""
    try:
        await message_status.edit_text(text, parse_mode="HTML")
    except TelegramNetworkError as e:
        logger.warning(f"Не удалось обновить статус (сеть мигнула): {e}")
    except Exception as e:
        logger.warning(f"Не удалось обновить статус: {e}")


async def _with_network_retries(action, attempts: int = 3, delay: float = 5.0, what: str = ""):
    """Повторяет сетевое действие до `attempts` раз с паузой `delay` секунд"""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return await action()
        except TelegramNetworkError as e:
            last_error = e
            logger.warning(f"Сбой сети при {what} (попытка {attempt}/{attempts}): {e}")
            if attempt < attempts:
                await asyncio.sleep(delay)
    raise last_error


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    welcome_text = (
        "👋 ЭЙ, ПРИВЕТ! ЭТО БОТ-УНИКАЛИЗАТОР ВАШЕГО КОНТЕНТА! 🔥\n\n"
        "📱 <b>Чем я занят:</b>\n"
        "• Превращаю твоё видео в КОНТЕНТ, которого алгоритм ещё НЕ ВИДЕЛ\n"
        "• Шум, цветокор, микро-кроп, питч — TikTok/Shorts/Reels смотрят и говорят «это новенькое» 🧠💥\n"
        "• Внешне — то же видео. Технически — ДРУГОЙ ВИНОГРАД\n\n"
        "📤 <b>Как юзать:</b>\n"
        "Кидай вертикальное видео (до 3 минут) — и мы ПОЛЕТЕЛИ\n\n"
        "⚙️ <b>Границы (даже у великих):</b>\n"
        f"• Хронометраж: до {MAX_VIDEO_DURATION} сек\n"
        f"• Габарит: до {MAX_FILE_SIZE_MB} МБ\n"
        "• Только вертикальные: высота &gt; ширины. Горизонталь не спасёт даже караоке\n\n"
        "🚀 Кидай видео — ЗАРЯЖАЕМ!"
    )
    await message.answer(welcome_text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "🤯 СПРАВКА ДЛЯ ТЕХ, КТО ДОЧИТАЛ ДО КНОПКИ\n\n"
        "<b>Как я варю уникальность:</b>\n"
        "1️⃣ Метаданные — переписываю с нуля. Прощай, история происхождения!\n"
        "2️⃣ Картинка — микро-кроп, шумок, цветокор, чуть-чуть скорости\n"
        "3️⃣ Звук — питч подшаманен, задержка на миллисекунды\n"
        "4️⃣ Полная перекодировка — новый «слепок» файла\n\n"
        "<b>Итог:</b>\n"
        "Выглядит так же, а для платформ — ДРУГОЕ видео. Магия? Нет — ffmpeg 😎\n\n"
        "⏱ <b>Время варки:</b>\n"
        "• 30 сек видео → ~1-2 мин\n"
        "• 3 мин → ~5-7 мин (терпи, шедевры не на спринте)\n\n"
        "📨 Сломалось? Пиши в поддержку @your_support — там сидят суровые люди с клавиатурой"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(F.video)
async def handle_video(message: Message):
    """Обработчик загрузки видео"""
    try:
        video = message.video
        
        # Проверка размера файла
        file_size_mb = video.file_size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await message.answer(
                f"❌ БРАК ПО ГАБАРИТАМ: {file_size_mb:.1f} МБ — наш лимит {MAX_FILE_SIZE_MB} МБ 📦\n"
                "Я стараюсь, но Telegram сильнее. Сожми ролик и кидай снова!"
            )
            return
        
        # Проверка длительности
        if video.duration > MAX_VIDEO_DURATION:
            await message.answer(
                f"❌ {video.duration} сек — это уже ПИЛОТНЫЙ ВЫПУСК СЕРИАЛА 😅\n"
                f"Максимум {MAX_VIDEO_DURATION} сек. Нарежь на части — каждая полетит отдельно!"
            )
            return
        
        # Уведомление о начале обработки
        status_msg = await message.answer(
            "⏳ ЗАПРЯГАЮ... 🔩\n"
            f"📦 Габарит: {file_size_mb:.1f} МБ\n"
            f"⏱ Хронометраж: {video.duration} сек\n"
            "Держись — сейчас будет КОНТЕНТ.",
            parse_mode="HTML"
        )
        
        # Скачиваем файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_filename = f"input_{message.from_user.id}_{timestamp}.mp4"
        output_filename = f"output_{message.from_user.id}_{timestamp}.mp4"
        
        input_path = os.path.join(TEMP_DIR, input_filename)
        output_path = os.path.join(PROCESSED_DIR, output_filename)
        
        await _safe_edit(status_msg, "⬇️ <b>Скачиваю видео...</b>")

        async def _do_download():
            file = await message.bot.get_file(video.file_id)
            await message.bot.download_file(file.file_path, input_path)

        await _with_network_retries(_do_download, what="скачивании видео")
        
        # Проверяем, вертикальное ли видео
        video_info = await video_processor.get_video_info(input_path)
        
        if not video_info:
            await _safe_edit(status_msg, "❌ Не смог распотрошить файл 🤷\nПохоже, видео битое. Кидай нормальный mp4!")
            os.remove(input_path)
            return
        
        if not video_processor.is_vertical_video(video_info['width'], video_info['height']):
            await _safe_edit(
                status_msg,
                "❌ ЭТО ЖЕ ГОРИЗОНТАЛЬНОЕ? ОГОРЧЕНИЕ 😭\n"
                f"📐 Габарит: {video_info['width']}x{video_info['height']}\n\n"
                "TikTok/Shorts/Reels едят вертикальное (высота &gt; ширины). Переверни контент и возвращайся!"
            )
            os.remove(input_path)
            return
        
        # Уникализируем
        await _safe_edit(
            status_msg,
            "🎨 ЗАРЯЖАЮ УНИКАЛИЗАЦИЮ... 🚀\n\n"
            "Видео прямо сейчас проходит обряд: шум, цветокор, микро-кроп —\n"
            "после этого его не узнает даже родная мать (алгоритм).\n"
            "Не кидай ещё видео — я один тут работаю 🤖"
        )
        
        success = await video_processor.uniqualize_video(input_path, output_path)
        
        if not success:
            await _safe_edit(
                status_msg,
                "❌ ФИКС НЕ УДАЛСЯ 😬 ffmpeg сегодня капризничает.\n"
                "Кинь ещё раз или другой файл — второй заход обычно спасает!"
            )
            # Очистка
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
            return
        
        # Отправляем результат
        await _safe_edit(status_msg, "📤 ВЫГРУЖАЮ ШЕДЕВР В ЭФИР... 📡")

        output_info = await video_processor.get_video_info(output_path)

        video_file = FSInputFile(output_path)

        async def _do_send():
            await message.answer_video(
                video_file,
                caption=(
                    "✅ ГОТОВО, ПОЛУЧИЛОСЬ ЯДРО! 🔥🔥🔥\n\n"
                    f"📊 Было: {video_info['size_mb']:.1f} МБ → стало: {output_info['size_mb']:.1f} МБ\n"
                    f"📐 Разрешение как дорогое: {video_info['width']}x{video_info['height']}\n\n"
                    "🎯 Такой контент алгоритмы видят ВПЕРВЫЕ. Вали в тренды — удачи, звёздочка! ⭐"
                ),
                parse_mode="HTML"
            )

        await _with_network_retries(_do_send, what="отправке результата")

        # Удаляем сообщение о статусе
        try:
            await status_msg.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить статусное сообщение: {e}")
        
        # Очищаем временные файлы
        os.remove(input_path)
        os.remove(output_path)
        
        logger.info(f"Успешно обработано видео от пользователя {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка в handle_video: {e}", exc_info=True)
        await message.answer(
            "❌ ТИХО-ТИХО, ЧТО-ТО СЛОМАЛОСЬ ГЛУБОКО В БОТЕ 🤖💔\n"
            "Попробуй ещё раз. Если снова упадёт — пиши в поддержку, разберёмся по-быстрому!"
        )


@router.message(F.document)
async def handle_document(message: Message):
    """Обработчик файлов, отправленных как документы"""
    # Проверяем, является ли документ видео
    if message.document.mime_type and message.document.mime_type.startswith('video/'):
        await message.answer(
            "ℹ️ РОДНОЙ, ТЫ КИНУЛ ФАЙЛ, А НЕ ВИДЕО 🫠\n\n"
            "Telegram-прикол: так видео обрабатываться не хочет.\n"
            "📱 Мобилка: скрепка → Галерея → выбирай\n"
            "💻 Десктоп: перетащи ролик в чат или выбери через меню вложений\n"
            "И мы ПОЛЕТЕЛИ! 🚀"
        )
    else:
        await message.answer(
            "❌ Я ЖРУ ТОЛЬКО ВИДЕО 🍗\n"
            "Стикеры, голосовые и письма о любви — мимо. Кидай вертикальное видео!"
        )


@router.message()
async def handle_other(message: Message):
    """Обработчик всех остальных сообщений"""
    await message.answer(
        "🤔 Хм, это не видео...\n\n"
        "Я без ума от вертикальных роликов (до 3 минут) — присылай, и сразу станет весело!\n\n"
        "/help для интриги."
    )
