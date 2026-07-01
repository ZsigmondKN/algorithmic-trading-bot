"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

import logging
import pandas as pd
import matplotlib.pyplot as plt

from config import EMA_WARMUP_MULTIPLIER
import mt5_lib

def ema_cross_strategy(
    symbol_configs: dict[str, str], 
    strategy_configs: dict[str, str],
):
    symbols = symbol_configs['symbols']
    timeframe = symbol_configs['timeframe']
    ema_period_one = strategy_configs['ema_period_one']
    ema_period_two = strategy_configs['ema_period_two']
    number_of_candles = strategy_configs['number_of_candles']

    ema_df = pd.DataFrame()
    # combine candlestick data for all symbols
    for symbol in symbols:
        # collect symbol data and add symbol column
        symbol_df = mt5_lib.collect_candlesticks(symbol, timeframe, number_of_candles)

    print(ema_df)