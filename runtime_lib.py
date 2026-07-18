"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import logging
from time import sleep
from datetime import datetime

from config import EMA_CROSS_STRATEGY, LOGGING_INDENT, STRATEGY_CHECK_FREQUENCY
import ema_strategy_lib
import mt5_lib
import order_lib

def log_setup_config(
    mt5_configs: dict[str, str],
    symbol_configs: dict[str, str], 
    order_configs: dict[str, str],
) -> None:
    user_name = mt5_configs['username']
    server = mt5_configs['server']

    symbols = symbol_configs['symbols']
    timeframe = symbol_configs['timeframe']

    risk_percentage_per_trade = order_configs['risk_percentage_per_trade']

    logging.info(f"Using account {user_name}, on server {server}.")
    logging.info(f"Using time frame of {timeframe}, for the following symbols: {symbols}.")
    logging.info(f"Using a risk percentage per trade of: {risk_percentage_per_trade * 100}%.\n")

def select_trading_strategy(strategy_configs: dict[str, str]):
    if strategy_configs["strategy"] == EMA_CROSS_STRATEGY:
        ema_period_one = strategy_configs['ema_period_one']
        ema_period_two = strategy_configs['ema_period_two']
        number_of_candles = strategy_configs['number_of_candles']

        logging.info(
            f"Using the EMA cross strategy with periods {ema_period_one} and {ema_period_two} on "
            f"{number_of_candles} candles.\n{LOGGING_INDENT}"
            "Waiting for EMA cross to occure..."
        )
        return ema_strategy_lib.ema_cross_strategy
    else:
        raise RuntimeError(
            f"The selected trading stategy of '{strategy_configs["strategy"]}' is incompatible "
            f"with the available options.")

def run_strategy(
    symbol_configs: dict[str, str],
    order_configs: dict[str, str],
    strategy_configs: dict[str, str]
):
    trading_strategy = select_trading_strategy(strategy_configs)
    symbols = symbol_configs["symbols"]
    timeframe = symbol_configs["timeframe"]
    previous_candle_time = None
    active_position = False

    while True:
        current_candle = mt5_lib.collect_candlesticks(
            symbol=symbols[0],
            timeframe=timeframe,
            number_of_candles=1
        )
        current_candle_time = current_candle.iloc[0]["time"]

        # if order was not placed in the span of the STRATEGY_CHECK_FREQUENCY, cancel the order
        order_lib.cancel_all_pending_orders()
        # TODO for the future: check if there are any active positions for the account 
        # to set the active_position variable

        if current_candle_time != previous_candle_time and not active_position:
            previous_candle_time = current_candle_time

            new_order_placed, report = trading_strategy(
                symbol_configs,
                order_configs,
                strategy_configs
            )
            if new_order_placed:
                logging.info(report)
            else:
                logging.debug(report)

        else:
            logging.debug(
                f"No new candle. Current completed candle: "
                f"{datetime.fromtimestamp(current_candle_time)}"
            )

        # TODO for the future: I would prefer to have the interval computed so the while loop only 
        # ran a few seconds after each new candle.
        # TODO for the future: when the market is closed, make no requests.
        sleep(STRATEGY_CHECK_FREQUENCY)

