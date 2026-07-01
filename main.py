"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import logging
import MetaTrader5 as mt5

import config
import mt5_lib
import ema_lib
    
def start_up():
        mt5_configs = config.load_mt5_configs()
        symbol_configs = config.load_symbol_configs()
        strategy_configs = config.load_strategy_configs()

        config.log_configs(mt5_configs, symbol_configs, strategy_configs)

        mt5_lib.login(mt5_configs)
        mt5_lib.validate_and_initialise_symbols(symbol_configs)
        
        ema_lib.generate_ema_report(symbol_configs, strategy_configs)

if __name__ == '__main__':
    try:
        start_up()
        mt5.shutdown()
    except Exception as e:
        logging.exception("Unhandled exception")
        mt5.shutdown()