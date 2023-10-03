import logging
from logging.handlers import RotatingFileHandler

# Define a custom formatter that uses ANSI escape codes to colorize log levels.
class ColorizedFormatter(logging.Formatter):

    COLORS = {
        'DEBUG': '\033[0;36m',  # Cyan
        'INFO': '\033[0;37m',  # White
        'WARNING': '\033[1;33m',  # Yellow
        'ERROR': '\033[1;31m',  # Red
        'CRITICAL': '\033[1;41m',  # Red background
    }

    def format(self, record):
        log_message = super(ColorizedFormatter, self).format(record)
        return f"{self.COLORS.get(record.levelname, '')}{log_message}\033[0m"  # Reset to default after log message

# Configure the root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Console handler configuration
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = ColorizedFormatter(
    '%(asctime)s [%(levelname)s] (%(process)d:%(thread)d) {%(pathname)s:%(lineno)d} - %(message)s'
)
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler configuration
file_handler = RotatingFileHandler(filename='app.log', maxBytes=50000000, backupCount=5)  # Keeping more backups
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] (%(process)d:%(thread)d) {%(pathname)s:%(lineno)d} - %(message)s'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

