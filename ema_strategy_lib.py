"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

import logging

import ema_lib
import order_lib

def ema_cross_strategy(
    symbol_configs: dict[str, str],
    order_configs: dict[str, str],
    strategy_configs: dict[str, str],
) -> None:
    for symbol in symbol_configs['symbols']:
        ema_df = ema_lib.create_ema_dataframe(
            symbol,
            symbol_configs["timeframe"],
            strategy_configs["ema_period_one"],
            strategy_configs["ema_period_two"],
            strategy_configs["number_of_candles"],
        )

        latest_signal = ema_df.iloc[-1]

        if latest_signal["ema_cross"]:
            lot_size = order_lib.calculate_lot_size(
                balance = order_lib.get_account_balance(),
                risk_percentage = order_configs["risk_percentage_per_trade"],
                order_type = latest_signal["order_type"],
                symbol = symbol,
                entry_price = latest_signal["entry_price"],
                stop_loss = latest_signal["stop_loss"]
            )
            order_outcome = order_lib.place_order(
                symbol = symbol,
                lot_size = lot_size,
                order_type = latest_signal["order_type"],
                entry_price = latest_signal["entry_price"],
                stop_loss = latest_signal["stop_loss"],
                take_profit = latest_signal["take_profit"],
                comment = f"EMA_Cross_Strategy_{symbol}",
                bypass_order_check = False
            )
            logging.info(order_outcome)
        logging.info(latest_signal.to_frame().T)