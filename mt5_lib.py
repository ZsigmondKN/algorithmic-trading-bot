#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import MetaTrader5 as mt5
import pandas
from typing import Dict

NUMBER_OF_CANDLES_USED = 50000

def initialize_mt5(settings: Dict[str, str]) -> None:
    if not mt5.initialize(login=int(settings['username']),server=settings['server'],password=settings['password']):
        raise RuntimeError("Failed to initialize MT5 with the provided login credentials.")
    print("Trading bot initialized!")

def validate_and_initialise_symbols(settings: Dict[str, str]) -> None:
    available_symbols = {symbol.name for symbol in mt5.symbols_get()}

    for symbol in settings['symbols']:
        if symbol not in available_symbols:
            raise ValueError(f"Symbol '{symbol}' not found in this MT5 version. Update symbol name.")
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to initialise symbol: {symbol}")
        print(f"Initialised: {symbol}")

    print("All requested symbols successfully initialised!")

def collect_candlesticks(settings):
    mt5_timeframe = set_query_timeframe(timeframe=settings["timeframe"])

    for symbol in settings["symbols"]:
        candles = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 1, NUMBER_OF_CANDLES_USED)
        if candles is not None:
            df = pandas.DataFrame(candles)
            print(df)
        else:
            print(f"Failed to retrieve data for {symbol}")

def set_query_timeframe(timeframe: str):
    return getattr(mt5, f"TIMEFRAME_{timeframe}")
