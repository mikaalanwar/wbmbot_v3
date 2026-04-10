import logging

from colorama import Fore, Style

BASIC_FORMAT = "[%(asctime)s] [%(filename)s:%(lineno)s] %(message)s"
DATE_FORMAT = "%d.%m.%Y - %H:%M"


def configure_logging(
    level: int = logging.INFO,
    force: bool = False,
) -> logging.Logger:
    """
    Configure root logging explicitly at runtime.
    """

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if force or not root_logger.handlers:
        logging.basicConfig(
            format=BASIC_FORMAT,
            level=level,
            datefmt=DATE_FORMAT,
            force=force,
        )
    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


class ColoredLogger:
    def __init__(self, app_name: str) -> None:
        self.app_name = app_name

    def create_logger(self):
        """
        Creates a logger
        """
        return get_logger(self.app_name)

    def green(self, message: str):
        """
        Prints Green
        """
        return f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {message}"

    def red(self, message: str):
        """
        Prints Red
        """
        return f"{Fore.RED}[ERROR]{Style.RESET_ALL} {message}"

    def yellow(self, message: str):
        """
        Prints Yellow
        """
        return f"{Fore.YELLOW}[WARNING]{Style.RESET_ALL} {message}"

    def cyan(self, message: str):
        """
        Prints Blue
        """
        return f"{Fore.CYAN}[INFO]{Style.RESET_ALL} {message}"

    def magenta(self, message: str):
        """
        Prints Magenta
        """
        return f"{Fore.MAGENTA}[DEBUG]{Style.RESET_ALL} {message}"
