"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import logging
import MetaTrader5 as mt5

import config
import ema_lib
import mt5_lib
import order_lib
import runtime_lib
    
def start_up():
        mt5_configs = config.load_mt5_configs()
        symbol_configs = config.load_symbol_configs()
        order_configs = config.load_order_configs()
        strategy_configs = config.load_strategy_configs()
        runtime_lib.log_setup_config(mt5_configs, symbol_configs, order_configs)

        mt5_lib.login(mt5_configs)
        mt5_lib.validate_and_initialise_symbols(symbol_configs)
        
        # ema_lib.generate_ema_report(symbol_configs, strategy_configs)
        runtime_lib.run_strategy(symbol_configs, order_configs, strategy_configs)

if __name__ == '__main__':
    try:
        start_up()
    except KeyboardInterrupt:
        logging.info("Shutdowwn request by user.")
    except Exception as e:
        logging.exception("Unhandled exception.")
    finally:
        order_lib.cancel_all_pending_orders()
        mt5.shutdown()
        logging.info("Disconnected MT5.")