
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import os
from dotenv import load_dotenv
import logging

import MetaTrader5 as mt5

# MT5 constants
MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST = 50000

# Runtime constants
STRATEGY_CHECK_FREQUENCY = 10

# Order placing constants
LOT_SIZE_CALCULATION_VALUE = 1.0
ORDER_FULFILL_TIME = mt5.ORDER_TIME_GTC # The order stays in the queue until it is manually canceled

# EMA strategy constants
EMA_CROSS_STRATEGY = 'ema_cross_strategy'
EMA_WARMUP_MULTIPLIER = 1.5

# Loggigng constants
LOGGING_INDENT = '                 '

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s", datefmt="%H:%M:%S"
)

def load_mt5_configs() -> dict[str, any]:
    return {
        'username': os.getenv('MT5_USERNAME'),
        'password': os.getenv('MT5_PASSWORD'),
        'server': os.getenv('MT5_SERVER'),
    }

def load_symbol_configs() -> dict[str, any]:
    return {
        'symbols': os.getenv('MT5_SYMBOLS').split(','),
        'timeframe': os.getenv('MT5_TIMEFRAME')
    }

def load_order_configs() -> dict[str, any]:
    return {
        'risk_percentage_per_trade': float(os.getenv('RISK_PERCENTAGE_PER_TRADE'))
    }

def load_strategy_configs() -> dict[str, any]:
    return {
        'strategy': os.getenv('STRATEGY'),
        'ema_period_one': int(os.getenv('EMA_PERIOD_ONE')),
        'ema_period_two': int(os.getenv('EMA_PERIOD_TWO')),
        'number_of_candles': int(os.getenv('NUMBER_OF_CANDLES'))
    }
