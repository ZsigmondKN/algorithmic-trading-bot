"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from decimal import Decimal
import os
import warnings
import webbrowser

import MetaTrader5 as mt5
from nautilus_trader.analysis import create_tearsheet
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, OrderType
from nautilus_trader.model.events import PositionClosed
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.trading.strategy import Strategy
import pandas as pd
import logging

from config import MOCK_ACCOUNT_BALANCE, MT5_TIMEFRAME_TO_NAUTILUS_BAR, LOGGING_INDENT
import ema_lib
import mt5_lib
import order_lib


class BacktestStatistics:
    def __init__(self):
        self.signals_generated = 0
        self.margin_rejections = 0
        self.orders_submitted = 0
        self.positions_closed_by_opposite_signal = 0
        self.backtest_wind_down_closures = 0
        self.positions_closed = 0

    def reset(self):
        self.signals_generated = 0
        self.margin_rejections = 0
        self.orders_submitted = 0
        self.positions_closed_by_opposite_signal = 0
        self.backtest_wind_down_closures = 0
        self.positions_closed = 0

    def report(self, symbol: str):
        logging.info(
            (
                f"For symbol {symbol}, trade signals: {self.signals_generated}, "
                f"margin rejections: {self.margin_rejections}, "
                f"orders submitted: {self.orders_submitted},\n"
                f"{LOGGING_INDENT}positions closed by opposite signal: "
                f"{self.positions_closed_by_opposite_signal}, "
                f"backtest wind down closures: "
                f"{self.backtest_wind_down_closures}, "
                f"positions closed: {self.positions_closed}.\n"
            )
        )

class EMACrossConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    symbol: str
    account_leverage: int
    risk_percentage: float
    max_margin_utilisation: float
    units_per_lot: Decimal
    ema_df: pd.DataFrame
    statistics: BacktestStatistics

class EMACross(Strategy):
    def __init__(self, config: EMACrossConfig):
        super().__init__(config)

        self.ema_df = config.ema_df
        self.stats = config.statistics
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
        
        self.stats.signals_generated += 1

        if signal["order_type"] == "buy_stop":

            if self.portfolio.is_net_short(self.config.instrument_id):
                positions = self.cache.positions_open(
                    instrument_id=self.config.instrument_id,
                )
                self.stats.positions_closed_by_opposite_signal += len(positions)
    
                self.close_all_positions(self.config.instrument_id)

            if self.portfolio.is_flat(self.config.instrument_id):
                self.buy(
                    signal["entry_price"],
                    signal["stop_loss"],
                    signal["take_profit"],
                )

        elif signal["order_type"] == "sell_stop":

            if self.portfolio.is_net_long(self.config.instrument_id):
                positions = self.cache.positions_open(
                    instrument_id=self.config.instrument_id,
                )
                self.stats.positions_closed_by_opposite_signal += len(positions)

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
            self.stats.margin_rejections += 1
            return None

        return instrument.make_qty(
            Decimal(str(lot_size)) * self.config.units_per_lot
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
        self.stats.orders_submitted += 1

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
        self.stats.orders_submitted += 1

    def on_position_closed(self, event: PositionClosed):
        self.stats.positions_closed += 1

    def on_stop(self):
        positions = self.cache.positions_open(
            instrument_id=self.config.instrument_id,
        )
        self.stats.backtest_wind_down_closures += len(positions)

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

def create_backtest_candles(
    symbol: str,
    symbol_configs: dict
):
    if symbol_configs["historical_timeframe"]:
        historical_start_time = symbol_configs["historical_start_time"]
        historical_end_time = symbol_configs["historical_end_time"]

        candles_df = mt5_lib.collect_historical_candlesticks(
            symbol,
            symbol_configs["timeframe"],
            historical_start_time,
            historical_end_time,
        )

        logging.debug(
            f"Backtesting {symbol} on historical data from {historical_start_time} till "
            f"{historical_end_time}."
        )
    else:
        timeframe = symbol_configs["timeframe"]
        number_of_candles = symbol_configs["number_of_candles"]
        candles_df = mt5_lib.collect_current_candlesticks(
            symbol,
            timeframe,
            number_of_candles,
        )

        logging.debug(
            f"Backtesting {symbol} on {number_of_candles} live candles, "
            f"with widths of {timeframe}."
        )

    return candles_df

def get_backtest_bars(bar_type, instrument, ema_df):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=(
                "A value is being set on a copy of a "
                "DataFrame or Series through chained assignment."
            ),
        )

        return BarDataWrangler(bar_type, instrument).process(
            ema_df[["open", "high", "low", "close"]]
        )

def run_symbol_backtest(
    backtest_engine,
    symbol,
    symbol_configs,
    order_configs,
    strategy_configs,
    units_per_lot,
    statistics #TODO add type hints in all files and do some more convension work
):
    symbol_info = mt5_lib.get_symbol_info(symbol)
    if symbol_info.trade_calc_mode == mt5.SYMBOL_CALC_MODE_FOREX:
        instrument = TestInstrumentProvider.default_fx_ccy(symbol)
    else:
        instrument = TestInstrumentProvider.equity(symbol, venue="SIM")

    candles_df = create_backtest_candles(symbol, symbol_configs)
    candles_df = mt5_lib.combine_date_time(candles_df)
    ema_df = ema_lib.create_ema_dataframe(
        symbol,
        candles_df.copy(),
        order_configs["risk_reward_ratio"],
        strategy_configs["ema_period_one"],
        strategy_configs["ema_period_two"],
    ).set_index("datetime")

    bar_time = MT5_TIMEFRAME_TO_NAUTILUS_BAR[symbol_configs["timeframe"]]
    bar_type = BarType.from_str(f"{symbol}.SIM-{bar_time}-LAST-EXTERNAL")
    bars = get_backtest_bars(bar_type, instrument, ema_df)

    strategy = EMACross(
        EMACrossConfig(
            instrument_id=instrument.id,
            symbol=symbol,
            account_leverage=order_configs["account_leverage"],
            risk_percentage=order_configs["risk_percentage_per_trade"],
            max_margin_utilisation=order_configs["max_margin_utilisation"],
            units_per_lot=units_per_lot,
            ema_df=ema_df,
            bar_type=bar_type,
            statistics=statistics
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

    statistics = BacktestStatistics()

    for symbol in symbol_configs["symbols"]:
        units_per_lot = mt5_lib.get_units_per_lot(symbol)
        backtest_engine = create_backtest_engine(
            account_balance, 
            order_configs["account_leverage"]
        )

        logging.info(f"Running backtest on {symbol} symbol.")

        run_symbol_backtest(
            backtest_engine,
            symbol,
            symbol_configs,
            order_configs,
            strategy_configs,
            units_per_lot,
            statistics
        )

        backtest_engine.run()
        statistics.report(symbol)
        statistics.reset()

        tearsheet_name = (f".\\reports\\backtest_tearsheet_{symbol}.html")
        create_tearsheet(engine = backtest_engine, output_path = tearsheet_name)
        report_path = os.path.realpath(tearsheet_name)
        webbrowser.open(report_path)