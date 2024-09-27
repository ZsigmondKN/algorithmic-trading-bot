#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import json
from typing import Any, Dict
import MetaTrader5 as mt5
# Custom Libraries
import mt5_lib

SETTINGS_FILE = "../trading_bot_personal_settings/personal_settings.json"

def load_settings() -> Dict[str, Any]:
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)
    
def start_up():
        print("Trading bot starting up!")
        settings = load_settings()
        mt5_lib.initialize_mt5(settings)
        mt5_lib.validate_and_initialise_symbols(settings)
        mt5_lib.collect_candlesticks(settings)

if __name__ == '__main__':
    try:
        start_up()
        mt5.shutdown()
    except Exception as e:
        print(f"An error occured: {e}")
        mt5.shutdown()