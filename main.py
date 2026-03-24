#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Zsigmond Kovacs-Nagy
Description: ...Don't forget to look at the TA Lib if not already...
"""

import os
from typing import Any, Dict
from dotenv import load_dotenv
import MetaTrader5 as mt5
# Custom Libraries
import mt5_lib
import ema_cross_strategy

# Load environment variables from .env file
load_dotenv()

def load_settings() -> Dict[str, Any]:
    """Load settings from environment variables"""
    return {
        'username': os.getenv('MT5_USERNAME'),
        'password': os.getenv('MT5_PASSWORD'),
        'server': os.getenv('MT5_SERVER'),
        'mt5_pathway': os.getenv('MT5_PATHWAY'),
        'symbols': os.getenv('MT5_SYMBOLS', 'USDJPY.a').split(','),
        'timeframe': os.getenv('MT5_TIMEFRAME', 'M30')
    }
    
def start_up():
        print("Trading bot starting up!")
        settings = load_settings()
        mt5_lib.initialize_mt5(settings)
        mt5_lib.validate_and_initialise_symbols(settings)
        print("Starting strategies!")
        for symbol in settings['symbols']:
            dataframe = ema_cross_strategy.ema_cross_strategy(symbol, settings['timeframe'], 50, 200)
            dataframe = dataframe[dataframe["ema_cross"] == True]
            print(dataframe)

if __name__ == '__main__':
    try:
        start_up()
        mt5.shutdown()
    except Exception as e:
        print(f"An error occured: {e}")
        mt5.shutdown()