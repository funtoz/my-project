import ffmpeg
import os
import logging
import asyncio
from typing import Optional
from bot.utils.strategy import UniqualizationStrategy
from bot.config import VIDEO_QUALITY, FFMPEG_THREADS

logger = logging.getLogger(__name__)

# Указываем путь к FFmpeg явно
FFMPEG_PATH = r"C:\ffmpeg\ffmpeg-master-latest-win64-gpl\bin"
if FFMPEG_PATH not in os.environ.get('PATH', ''):
    os.environ['PATH'] = FFMPEG_PATH + os.pathsep + os.environ.get('PATH', '')


class VideoProcessor:
    """Класс для обработки и уникализации видео"""
    
    def __init__(self):
        self.strategy = UniqualizationStrategy()
    
    async def uniqualize_video(self, input_path: str, output_path: str) -> bool:
        """
        Применяет многослойную уникализацию к видео
        
        Args:
            input_path: Путь к исходному видео
            output_path: Путь для сохранения результата
            
        Returns:
            True если успешно, False если ошибка
        """
        try:
            logger.info(f"Начинаем уникализацию: {input_path}")
            
            # Получаем информацию о видео
            probe = ffmpeg.probe(input_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            width = int(video_info['width'])
            height = int(video_info['height'])
            
            # Генерируем параметры уникализации
            noise_level = self.strategy.get_noise_level()
            speed = self.strategy.get_speed_change()
            crop_px = self.strategy.get_crop_pixels()
            hue = self.strategy.get_hue_shift()
            saturation = 1 + self.strategy.get_saturation_shift()
            brightness = self.strategy.get_brightness_shift()
            audio_pitch = self.strategy.get_audio_pitch_shift()
            audio_delay = self.strategy.get_audio_delay_ms()
            unique_id = self.strategy.get_unique_id()
            fps_num, fps_den = self.strategy.get_fps_adjustment()

            # fps-фильтр ждёт АБСОЛЮТНУЮ частоту кадров, а стратегия
            # возвращает только её МНОЖИТЕЛЬ (например 1001/1000).
            # Берём исходный fps у видео и домножаем на него.
            src_fps = 30.0
            for probe_rate in (video_info.get('avg_frame_rate'), video_info.get('r_frame_rate')):
                if not probe_rate or probe_rate in ('0/0', 'N/A'):
                    continue
                num_s, _, den_s = probe_rate.partition('/')
                try:
                    candidate = float(num_s) / (float(den_s) if den_s else 1.0)
                except (ValueError, ZeroDivisionError):
                    continue
                if candidate > 1.0:
                    src_fps = candidate
                    break

            new_fps = src_fps * fps_num / fps_den

            logger.info(f"Параметры: шум={noise_level:.4f}, скорость={speed:.4f}, crop={crop_px}px, fps={src_fps:.2f}->{new_fps:.2f}")
            
            # Рассчитываем новые размеры после crop
            new_width = width - (crop_px * 2)
            new_height = height - (crop_px * 2)
            
            # Применяем FFmpeg: строим граф фильтров средствами ffmpeg-python.
            # Каждый фильтр - отдельный узел, экранирование делает библиотека.
            graph = ffmpeg.input(input_path)

            v = graph.video
            # 1. Обрезаем края
            v = v.filter('crop', w=new_width, h=new_height, x=crop_px, y=crop_px)
            # 2. Возвращаем исходный размер
            v = v.filter('scale', w=width, h=height, flags='lanczos')
            # 3. Добавляем шум
            v = v.filter('noise', alls=int(noise_level * 100), allf='t+u')
            # 4. Цветокоррекция (hue, saturation, brightness)
            v = v.filter('hue', h=hue * 360, s=saturation)
            v = v.filter('eq', brightness=brightness)
            # 5. Изменяем скорость
            v = v.filter('setpts', f'{1 / speed}*PTS')
            # 6. Микроизменение FPS (от исходной частоты, не абсолютная!)
            v = v.filter('fps', fps=f'{new_fps:.6f}')

            a = graph.audio
            # 1. Изменяем питч (asetrate принимает целую частоту)
            a = a.filter('asetrate', int(44100 * (1 + audio_pitch)))
            a = a.filter('aresample', 44100)
            # 2. Изменяем скорость (синхронно с видео)
            a = a.filter('atempo', f'{speed:.6f}')
            # 3. Добавляем тишину в начало
            a = a.filter('adelay', f'{audio_delay}|{audio_delay}')
            
            # Выходной поток с метаданными
            output = ffmpeg.output(
                v,
                a,
                output_path,
                vcodec='libx264',
                preset='slow',  # Лучшее качество
                crf=VIDEO_QUALITY,
                acodec='aac',
                audio_bitrate='192k',
                threads=FFMPEG_THREADS,
                # Полностью перезаписываем метаданные
                **{
                    'metadata': f'unique_id={unique_id}',
                    'metadata:s:v:0': 'handler_name=VideoHandler',
                    'metadata:s:a:0': 'handler_name=AudioHandler',
                    'map_metadata': '-1',  # Удаляем все старые метаданные
                }
            )
            
            # Запускаем обработку в отдельном потоке,
            # чтобы бот не переставал отвечать на время кодирования
            try:
                await asyncio.to_thread(
                    ffmpeg.run,
                    output,
                    overwrite_output=True,
                    capture_stdout=True,
                    capture_stderr=True,
                )
                logger.info(f"Уникализация завершена: {output_path}")
                return True
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg ошибка: {e.stderr.decode('utf-8', errors='ignore')}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при уникализации видео: {e}", exc_info=True)
            return False
    
    async def get_video_info(self, video_path: str) -> Optional[dict]:
        """Получает информацию о видео"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            audio_stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
            
            if not video_stream:
                return None
            
            duration = float(probe['format'].get('duration', 0))
            width = int(video_stream.get('width', 0))
            height = int(video_stream.get('height', 0))
            
            return {
                'duration': duration,
                'width': width,
                'height': height,
                'has_audio': audio_stream is not None,
                'size_mb': os.path.getsize(video_path) / (1024 * 1024)
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о видео: {e}")
            return None
    
    def is_vertical_video(self, width: int, height: int) -> bool:
        """Проверяет, является ли видео вертикальным"""
        return height > width
