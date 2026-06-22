
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import os
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s", datefmt="%H:%M:%S"
)

MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST = 50000

def load_settings() -> dict[str, any]:
    return {
        'username': os.getenv('MT5_USERNAME'),
        'password': os.getenv('MT5_PASSWORD'),
        'server': os.getenv('MT5_SERVER'),
        'symbols': os.getenv('MT5_SYMBOLS').split(','),
        'timeframe': os.getenv('MT5_TIMEFRAME')
    }