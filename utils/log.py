# this code was shamelessly stolen from dusty-nv:
# https://github.com/dusty-nv/jetson-containers/blob/master/packages/llm/local_llm/utils/log.py
import logging
import termcolor

logging.SUCCESS = logging.INFO + 5
logging.DEBUG2 = logging.DEBUG + 5


class LogFormatter(logging.Formatter):
    """
    Colorized log formatter (inspired from https://stackoverflow.com/a/56944256)
    Use LogFormatter.config() to enable it with the desired logging level.
    """
    DefaultFormat = "%(asctime)s [%(levelname)s] %(message)s"
    DefaultDateFormat = "%b %d %H:%M:%S"

    DefaultColors = {
        logging.DEBUG: ('light_blue', 'bold'),
        logging.DEBUG2: 'light_blue',
        logging.INFO: None,
        logging.WARNING: 'yellow',
        logging.SUCCESS: 'green',
        logging.ERROR: 'red',
        logging.CRITICAL: 'red'
    }

    @staticmethod
    def config(level='info', format=DefaultFormat, datefmt=DefaultDateFormat, colors=DefaultColors, **kwargs):
        """
        Configure the root logger with formatting and color settings.

        Parameters:
          level (str|int) -- Either the log level name
          format (str) -- Message formatting attributes (https://docs.python.org/3/library/logging.html#logrecord-attributes)

          datefmt (str) -- Date/time formatting string (https://docs.python.org/3/library/logging.html#logging.Formatter.formatTime)

          colors (dict) -- A dict with keys for each logging level that specify the color name to use for those messages
                           You can also specify a tuple for each couple, where the first entry is the color name,
                           followed by style attributes (from https://github.com/termcolor/termcolor#text-properties)
                           If colors is None, then colorization will be disabled in the log.

          kwargs (dict) -- Additional arguments passed to logging.basicConfig() (https://docs.python.org/3/library/logging.html#logging.basicConfig)
        """
        logging.addLevelName(logging.SUCCESS, "SUCCESS")
        logging.addLevelName(logging.DEBUG2, "DEBUG2")

        def log_success(*args, **kwargs):
            logging.log(logging.SUCCESS, *args, **kwargs)

        def log_debug2(*args, **kwargs):
            logging.log(logging.DEBUG2, *args, **kwargs)

        logging.success = log_success
        logging.debug2 = log_debug2

        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        log_handler = logging.StreamHandler()
        log_handler.setFormatter(LogFormatter())
        # log_handler.setLevel(level)

        logging.basicConfig(handlers=[log_handler], level=level, **kwargs)

    def __init__(self, format=DefaultFormat, datefmt=DefaultDateFormat, colors=DefaultColors):
        """
        @internal it's recommended to use LogFormatter.config() above
        """
        self.formatters = {}

        for level in self.DefaultColors:
            if colors is not None and level in colors and colors[level] is not None:
                color = colors[level]
                attrs = None

                if not isinstance(color, str):
                    attrs = color[1:]
                    color = color[0]

                fmt = termcolor.colored(format, color, attrs=attrs)
            else:
                fmt = format

            self.formatters[level] = logging.Formatter(fmt=fmt, datefmt=datefmt)

    def format(self, record):
        """
        Implementation of logging.Formatter record formatting function
        """
        return self.formatters[record.levelno].format(record)