import random
import uuid
from typing import Tuple


class UniqualizationStrategy:
    """Генератор случайных параметров для уникализации"""
    
    @staticmethod
    def get_noise_level() -> float:
        """Уровень шума: 1-2%"""
        return random.uniform(0.01, 0.02)
    
    @staticmethod
    def get_speed_change() -> float:
        """Изменение скорости: ±2-4%"""
        change = random.uniform(0.02, 0.04)
        return 1 + change if random.choice([True, False]) else 1 - change
    
    @staticmethod
    def get_crop_pixels() -> int:
        """Количество пикселей для обрезки: 2-4px"""
        return random.randint(2, 4)
    
    @staticmethod
    def get_hue_shift() -> float:
        """Сдвиг оттенка: ±1-3%"""
        return random.uniform(-0.03, 0.03)
    
    @staticmethod
    def get_saturation_shift() -> float:
        """Сдвиг насыщенности: ±1-2%"""
        return random.uniform(-0.02, 0.02)
    
    @staticmethod
    def get_brightness_shift() -> float:
        """Сдвиг яркости: ±1-2%"""
        return random.uniform(-0.02, 0.02)
    
    @staticmethod
    def get_audio_pitch_shift() -> float:
        """Изменение питча аудио: ±0.3-0.7%"""
        shift = random.uniform(0.003, 0.007)
        return shift if random.choice([True, False]) else -shift
    
    @staticmethod
    def get_audio_delay_ms() -> int:
        """Задержка аудио в начале: 20-100мс"""
        return random.randint(20, 100)
    
    @staticmethod
    def get_unique_id() -> str:
        """Уникальный ID для метаданных"""
        return str(uuid.uuid4())
    
    @staticmethod
    def get_bitrate_variance() -> float:
        """Вариация битрейта: ±5-10%"""
        return random.uniform(0.90, 1.10)
    
    @staticmethod
    def get_fps_adjustment() -> Tuple[int, int]:
        """Микроизменение FPS через соотношение"""
        # Например: 30fps -> 29.97fps или 30.03fps
        adjustments = [
            (1000, 1001),  # Немного медленнее
            (1001, 1000),  # Немного быстрее
            (1000, 999),   # Еще медленнее
        ]
        return random.choice(adjustments)
