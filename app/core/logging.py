import logging


class AppLogger:
    """Thin wrapper over stdlib logging — not a singleton, each caller passes its own __name__."""

    _configured = False

    def __init__(self, name: str) -> None:
        AppLogger._configure_once()
        self._logger = logging.getLogger(name)

    @staticmethod
    def _configure_once() -> None:
        if AppLogger._configured:
            return
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
        AppLogger._configured = True

    def debug(self, message: str, *args: object) -> None:
        self._logger.debug(message, *args)

    def info(self, message: str, *args: object) -> None:
        self._logger.info(message, *args)

    def warning(self, message: str, *args: object) -> None:
        self._logger.warning(message, *args)

    def error(self, message: str, *args: object) -> None:
        self._logger.error(message, *args)

    def critical(self, message: str, *args: object) -> None:
        self._logger.critical(message, *args)


def get_logger(name: str) -> AppLogger:
    return AppLogger(name)
