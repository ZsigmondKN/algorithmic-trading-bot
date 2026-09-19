"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from dotenv import load_dotenv
import logging

import MetaTrader5 as mt5

import backtest_lib
import config
import ema_lib
import mt5_lib
import order_lib
import runtime_lib


def main() -> None:
    load_dotenv()

    mt5_configs = config.load_mt5_configs()
    symbol_configs = config.load_symbol_configs()
    order_configs = config.load_order_configs()
    strategy_configs = config.load_strategy_configs()
    backtest_config = config.load_backtest_config()
    config.load_and_set_ui_config()

    mt5_lib.login(mt5_configs)
    mt5_lib.validate_and_initialise_symbols(symbol_configs)

    runtime_lib.log_setup_config(
        mt5_configs=mt5_configs,
        symbol_configs=symbol_configs,
        order_configs=order_configs
    )

    trading_mode = mt5_configs["trading_mode"]
    if trading_mode == "backtesting":
        backtest_lib.run_backtest(
            symbol_configs=symbol_configs,
            order_configs=order_configs,
            strategy_configs=strategy_configs,
            backtest_config=backtest_config
        )
    elif trading_mode == "live_trading":
        account_info = mt5_lib.get_account_info()
        mt5_lib.log_account_details(
            account_balance=account_info.balance,
            account_currency=account_info.currency
        )
        if strategy_configs["generate_strategy_report"]:
            ema_lib.generate_ema_report(
                symbol_configs=symbol_configs,
                order_configs=order_configs,
                strategy_configs=strategy_configs
            )
        runtime_lib.run_strategy(
            symbol_configs=symbol_configs,
            order_configs=order_configs,
            strategy_configs=strategy_configs
        )
    else:
        raise RuntimeError(f"Unexpected trading mode '{trading_mode}' selected.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Shutdown request by user.")
    except mt5_lib.LoginError as e:
        logging.error(e)
    except Exception as e:
        logging.exception("Unhandled exception.")
        order_lib.cancel_all_pending_orders() 
        mt5.shutdown()
        logging.info("Disconnected MT5.")