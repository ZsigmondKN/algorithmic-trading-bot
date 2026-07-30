"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from datetime import datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv
import logging
import os

import MetaTrader5 as mt5

# MT5 constants
LOGIN_TIMEOUT = 10000
MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST = 50000

# Runtime constants
STRATEGY_CHECK_FREQUENCY = 10

# Order placing constants
LOT_SIZE_CALCULATION_VALUE = 1.0
ORDER_FULFILL_TIME = mt5.ORDER_TIME_GTC # The order stays in the queue until it is manually canceled

# Backtesting constants
NAUTILUS_TO_STANDARD_FX_MULTIPLIER = Decimal("100") # Nautilus default FX units to standard MT5 FX units.
NAUTILUS_TO_STANDARD_STOCK_MULTIPLIER = Decimal("1") # Nautilus default stock units to standard MT5 FX units.
MT5_TIMEFRAME_TO_NAUTILUS_BAR = {
    "M1": "1-MINUTE",
    "M5": "5-MINUTE",
    "M15": "15-MINUTE",
    "M30": "30-MINUTE",
    "H1": "1-HOUR",
    "H4": "4-HOUR",
    "D1": "1-DAY",
}
MOCK_ACCOUNT_BALANCE = 500000

# EMA strategy constants
EMA_CROSS_STRATEGY = 'ema_cross_strategy'
EMA_WARMUP_MULTIPLIER = 1.5

# Loggigng constants
LOGGING_INDENT = '                 '

load_dotenv()
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s", datefmt="%H:%M:%S"
)

def parse_bool(value: str) -> bool:
    value = value.strip().lower()

    if value in ("true", "yes"):
        return True
    if value in ("false", "no"):
        return False
    
    raise ValueError(f"Invalid boolean configuration value: {value}")

def load_mt5_configs() -> dict[str, any]:
    return {
        'username': os.getenv('MT5_USERNAME'),
        'password': os.getenv('MT5_PASSWORD'),
        'server': os.getenv('MT5_SERVER'),
        'trading_mode': os.getenv('TRADING_MODE')
    }

def load_symbol_configs() -> dict[str, any]:
    return {
        'symbols': os.getenv('MT5_SYMBOLS').split(','),
        'timeframe': os.getenv('MT5_TIMEFRAME'),
        'number_of_candles': int(os.getenv('NUMBER_OF_CANDLES')),
        'historical_timeframe': parse_bool(os.getenv('HISTORICAL_TIMEFRAME')),
        'historical_start_time': datetime.strptime(
            os.getenv('HISTORICAL_START_TIME'), "%Y-%m-%d"
        ).replace(tzinfo=timezone.utc),
        'historical_end_time': datetime.strptime(
            os.getenv("HISTORICAL_END_TIME"),"%Y-%m-%d"
        ).replace(tzinfo=timezone.utc)
    }

def load_order_configs() -> dict[str, any]:
    return {
        'risk_percentage_per_trade': float(os.getenv('RISK_PERCENTAGE_PER_TRADE')),
        'max_margin_utilisation': float(os.getenv('MAX_MARGIN_UTILISATION'))
    }

def load_strategy_configs() -> dict[str, any]:
    return {
        'strategy': os.getenv('STRATEGY'),
        'ema_period_one': int(os.getenv('EMA_PERIOD_ONE')),
        'ema_period_two': int(os.getenv('EMA_PERIOD_TWO')),
    }
