"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

import pandas as pd
import matplotlib.pyplot as plt

import mt5_lib
import ema_lib

def ema_cross_strategy(
    symbol_configs: dict[str, str], 
    strategy_configs: dict[str, str],
):
    symbols = symbol_configs['symbols']
    timeframe = symbol_configs['timeframe']
    ema_period_one = strategy_configs['ema_period_one']
    ema_period_two = strategy_configs['ema_period_two']
    number_of_candles = strategy_configs['number_of_candles']

    ema_df = ema_lib.create_ema_dataframe(
        symbol_configs["symbols"],
        symbol_configs["timeframe"],
        strategy_configs["ema_period_one"],
        strategy_configs["ema_period_two"],
        strategy_configs["number_of_candles"],
    )

    print(ema_df)