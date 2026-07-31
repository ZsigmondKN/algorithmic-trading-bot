"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import os
import warnings
import webbrowser
from decimal import Decimal

from nautilus_trader.analysis import create_tearsheet
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, OrderType
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.trading.strategy import Strategy
import pandas as pd
import logging

from config import (
    MOCK_ACCOUNT_BALANCE, MT5_TIMEFRAME_TO_NAUTILUS_BAR,
    NAUTILUS_TO_STANDARD_FX_MULTIPLIER,
)
import ema_lib
import mt5_lib
import order_lib

class EMACrossConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    symbol: str
    account_leverage: int
    risk_percentage: float
    max_margin_utilisation: float
    lot_to_quantity_multiplier: Decimal
    ema_df: pd.DataFrame

class EMACross(Strategy):
    def __init__(self, config: EMACrossConfig):
        super().__init__(config)

        self.ema_df = config.ema_df
        self.current_row = 0

    def on_start(self):
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar):
        if self.current_row >= len(self.ema_df):
            return

        signal = self.ema_df.iloc[self.current_row]
        self.current_row += 1

        if not signal["ema_cross"]:
            return

        if signal["order_type"] == "buy_stop":

            if self.portfolio.is_net_short(self.config.instrument_id):
                self.close_all_positions(self.config.instrument_id)

            if self.portfolio.is_flat(self.config.instrument_id):
                self.buy(
                    signal["entry_price"],
                    signal["stop_loss"],
                    signal["take_profit"],
                )

        elif signal["order_type"] == "sell_stop":

            if self.portfolio.is_net_long(self.config.instrument_id):
                self.close_all_positions(self.config.instrument_id)

            if self.portfolio.is_flat(self.config.instrument_id):
                self.sell(
                    signal["entry_price"],
                    signal["stop_loss"],
                    signal["take_profit"],
                )

    def _calculate_quantity(
        self,
        instrument,
        order_type: str,
        entry_price: float,
        stop_loss: float,
    ):
        account = self.portfolio.account(self.config.instrument_id.venue)

        balance = account.balance_total().as_double()

        lot_size = order_lib.calculate_lot_size(
            balance=balance,
            account_leverage=self.config.account_leverage,
            risk_percentage=self.config.risk_percentage,
            max_margin_utilisation=self.config.max_margin_utilisation,
            order_type=order_type,
            symbol=str(instrument.raw_symbol),
            entry_price=entry_price,
            stop_loss=stop_loss,
        )
        if lot_size is None:
            logging.warning("New order exceeds user defined margin requirements.")
            return None

        return instrument.make_qty(
            Decimal(str(lot_size)) * self.config.lot_to_quantity_multiplier
        )

    def buy(self, entry_price, stop_loss, take_profit):
        instrument = self.cache.instrument(self.config.instrument_id)


        quantity = self._calculate_quantity(
            instrument,
            "buy_stop",
            entry_price,
            stop_loss
        )

        entry_price = instrument.make_price(entry_price)
        stop_loss = instrument.make_price(stop_loss)
        take_profit = instrument.make_price(take_profit)

        if quantity is None:
            return
        
        orders = self.order_factory.bracket(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.BUY,
            quantity=quantity,
            entry_order_type=OrderType.MARKET,
            sl_trigger_price=stop_loss,
            tp_price=take_profit,
        )

        self.submit_order_list(orders)

    def sell(self, entry_price, stop_loss, take_profit):
        instrument = self.cache.instrument(self.config.instrument_id)

        quantity = self._calculate_quantity(
            instrument,
            "sell_stop",
            entry_price,
            stop_loss
        )

        entry_price = instrument.make_price(entry_price)
        stop_loss = instrument.make_price(stop_loss)
        take_profit = instrument.make_price(take_profit)

        if quantity is None:
            return

        orders = self.order_factory.bracket(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.SELL,
            quantity=quantity,
            entry_order_type=OrderType.MARKET, #TODO not exactly like my code
            sl_trigger_price=stop_loss,
            tp_price=take_profit,
        )

        self.submit_order_list(orders)

    def on_stop(self):
        self.close_all_positions(self.config.instrument_id)

def create_backtest_engine(
    account_balance: float,
    account_leverage: int
) -> BacktestEngine:
    backtest_engine = BacktestEngine(
        config=BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"))
    )
    backtest_engine.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.HEDGING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(account_balance, USD)],
        base_currency=USD,
        default_leverage=Decimal(account_leverage)
    )

    return backtest_engine

def run_symbol_backtest(
    backtest_engine,
    symbol,
    symbol_configs,
    order_configs,
    strategy_configs,
    lot_to_quantity_multiplier
):
    if lot_to_quantity_multiplier == NAUTILUS_TO_STANDARD_FX_MULTIPLIER: #TODO this could be done better
        instrument = TestInstrumentProvider.default_fx_ccy(symbol)
    else:
        instrument = TestInstrumentProvider.equity(symbol, venue="SIM")

    if symbol_configs["historical_timeframe"]:
        candles_df = mt5_lib.collect_historical_candlesticks(
            symbol,
            symbol_configs["timeframe"],
            symbol_configs["historical_start_time"],
            symbol_configs["historical_end_time"],
        )
    else:
        candles_df = mt5_lib.collect_current_candlesticks(
            symbol,
            symbol_configs["timeframe"],
            symbol_configs["number_of_candles"],
        )

    candles_df = mt5_lib.combine_date_time(candles_df)
    ema_df = ema_lib.create_ema_dataframe(
        symbol,
        candles_df.copy(),
        strategy_configs["ema_period_one"],
        strategy_configs["ema_period_two"],
    ).set_index("datetime")

    # ohlc_df = candles_df[["open", "high", "low", "close"]].astype(float)

    bar_time = MT5_TIMEFRAME_TO_NAUTILUS_BAR[symbol_configs["timeframe"]]
    bar_type = BarType.from_str(f"{symbol}.SIM-{bar_time}-LAST-EXTERNAL")

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=(
                "A value is being set on a copy of a "
                "DataFrame or Series through chained assignment."
            ),
        )

        bars = BarDataWrangler(bar_type, instrument).process(
            ema_df[["open", "high", "low", "close"]]
        )

    strategy = EMACross(
        EMACrossConfig(
            instrument_id=instrument.id,
            bar_type=bar_type,
            symbol=symbol,
            account_leverage=order_configs["account_leverage"],
            risk_percentage=order_configs["risk_percentage_per_trade"],
            max_margin_utilisation=order_configs["max_margin_utilisation"],
            lot_to_quantity_multiplier=lot_to_quantity_multiplier,
            ema_df=ema_df,
        ),
    )

    backtest_engine.add_instrument(instrument)
    backtest_engine.add_data(bars)
    backtest_engine.add_strategy(strategy)

def run_backtest(
    symbol_configs: dict,
    order_configs: dict,
    strategy_configs: dict,
    use_real_account_balance: bool = True,
) -> None:

    if use_real_account_balance:
        account_balance = mt5_lib.get_account_balance()
    else:
        account_balance = MOCK_ACCOUNT_BALANCE

    for symbol in symbol_configs["symbols"]:
        lot_to_quantity_multiplier = mt5_lib.get_lot_to_quantity_multiplier(symbol)
        backtest_engine = create_backtest_engine(
            account_balance, 
            order_configs["account_leverage"]
        )

        run_symbol_backtest(
            backtest_engine,
            symbol,
            symbol_configs,
            order_configs,
            strategy_configs,
            lot_to_quantity_multiplier
        )

        backtest_engine.run()

        tearsheet_name = (f".\\reports\\backtest_tearsheet_{symbol}.html")
        create_tearsheet(engine = backtest_engine, output_path = tearsheet_name)
        report_path = os.path.realpath(tearsheet_name)
        webbrowser.open(report_path)