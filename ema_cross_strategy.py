#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import mt5_lib
import indicator_lib

NUMBER_OF_CANDLES_USED = 1000

def calc_indicators(dataframe, ema_one, ema_two):
    dataframe = indicator_lib.calculate_ema(dataframe, ema_one)
    dataframe = indicator_lib.calculate_ema(dataframe, ema_two)
    return indicator_lib.ema_cross_calculator(dataframe, ema_one, ema_two)

def ema_cross_strategy(symbol: str, timeframe: str, ema_one:int, ema_two:int):
    dataframe = mt5_lib.collect_candlesticks(symbol, timeframe, NUMBER_OF_CANDLES_USED)
    dataframe = calc_indicators(dataframe, ema_one, ema_two)
    return dataframe
    