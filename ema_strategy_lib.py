"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

from config import LOGGING_INDENT
import ema_lib
import mt5_lib
import order_lib

def ema_cross_strategy(
    symbol_configs: dict[str, str],
    order_configs: dict[str, str],
    strategy_configs: dict[str, str]
) -> tuple:
    report = ""
    order_placed = False

    for symbol in symbol_configs['symbols']:
        candle_dataframe = mt5_lib.collect_current_candlesticks(
            symbol,
            symbol_configs["timeframe"],
            symbol_configs["number_of_candles"]
        )
        ema_df = ema_lib.create_ema_dataframe(
            symbol,
            candle_dataframe,
            strategy_configs["ema_period_one"],
            strategy_configs["ema_period_two"],
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
            
            order_placed = True
            report += f"New order submitted. The order response is:\n {order_outcome}\n"
        else:
            report += "The EMA values did not cross and so no order was placed.\n"
        
        report += latest_signal.to_frame().T.to_string(index=False)
        report = report.replace("\n", f"\n{LOGGING_INDENT}")

    return order_placed, report