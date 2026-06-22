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
        # set up trading bot and symbols 
        settings = config.load_settings()
        mt5_lib.login(settings)
        mt5_lib.validate_and_initialise_symbols(settings)

        ema_dataframe = ema_lib.create_ema_dataframe(
            symbols = settings['symbols'], 
            timeframe = settings['timeframe'], 
            ema_period_one = 50, 
            ema_period_two = 200, 
            number_of_candles = 2000
        )

        # load symbol statistics
        ema_lib.log_ema_crosses(
            ema_dataframe = ema_dataframe,
            settings = settings, 
            ema_period_one = 50, 
            ema_period_two = 200, 
            number_of_candles = 5000
        )

        ema_lib.plot_ema_charts(
            ema_dataframe,
            ema_period_one=50,
            ema_period_two=200,
        )

if __name__ == '__main__':
    try:
        start_up()
        mt5.shutdown()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        mt5.shutdown()