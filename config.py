
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import os
from dotenv import load_dotenv
import logging

import MetaTrader5 as mt5

MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST = 50000
LOT_SIZE_CALCULATION_VALUE = 1.0
ORDER_FULFILL_TIME = mt5.ORDER_TIME_GTC # The order stays in the queue until it is manually canceled
EMA_WARMUP_MULTIPLIER = 1.5

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

def load_strategy_configs() -> dict[str, any]:
    return {
        'strategy': os.getenv('STRATEGY'),
        'ema_period_one': int(os.getenv('EMA_PERIOD_ONE')),
        'ema_period_two': int(os.getenv('EMA_PERIOD_TWO')),
        'number_of_candles': int(os.getenv('NUMBER_OF_CANDLES'))
    }

def log_configs(
    mt5_configs: dict[str, str],
    symbol_configs: dict[str, str], 
    strategy_configs: dict[str, str],
) -> None:
    user_name = mt5_configs['username']
    server = mt5_configs['server']

    symbols = symbol_configs['symbols']
    timeframe = symbol_configs['timeframe']

    ema_period_one = strategy_configs['ema_period_one']
    ema_period_two = strategy_configs['ema_period_two']
    number_of_candles = strategy_configs['number_of_candles']

    logging.info(f"Using account {user_name}, on server {server}.")
    logging.info(f"Using time frame of {timeframe}, for the following symbols: {symbols}.")
    logging.info(
        f"Strategy uses EMA periods {ema_period_one} and {ema_period_two}, "
        f"with the {number_of_candles} candles."
    )
