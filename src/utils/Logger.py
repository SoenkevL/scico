import logging
import logging.config
import os
from datetime import datetime


def setup_logging(log_level=logging.INFO, log_file=None):
    """Centralized logging configuration for the entire project"""

    # Create logs directory if it doesn't exist
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
    else:
        log_file = f"logs/run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.FileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': log_file,
                'mode': 'a'
            }
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': False
            }
        }
    })
