#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import MetaTrader5 as mt5
import pandas as pd
from typing import Dict

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

def collect_candlesticks(symbol: str, timeframe: str, number_of_candles: int) -> pd.DataFrame:
    if number_of_candles > 50000:
        raise ValueError("Cannot retrieve more than 50,000 candlesticks at once.")
    candles = mt5.copy_rates_from_pos(symbol, set_query_timeframe(timeframe), 1, number_of_candles)
    if candles is None:
        raise RuntimeError(f"Failed to retrieve data for {symbol}")
    
    return pd.DataFrame(candles)

def set_query_timeframe(timeframe: str):
    return getattr(mt5, f"TIMEFRAME_{timeframe}")