"""Настройка логирования ZapretDesktop."""
import logging
import os

from src.shared.lib.path_utils import get_appdata_config_dir


def setup_logging(level=logging.INFO) -> logging.Logger:
    """Инициализирует логгер приложения (файл в AppData + консоль при dev-запуске)."""
    logger = logging.getLogger('ZapretDesktop')
    if logger.handlers:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    try:
        log_dir = get_appdata_config_dir()
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(
            os.path.join(log_dir, 'zapret_desktop.log'),
            encoding='utf-8',
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass

    import sys
    if not getattr(sys, 'frozen', False):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
