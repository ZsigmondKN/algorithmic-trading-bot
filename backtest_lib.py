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
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide
from nautilus_trader.model.identifiers import InstrumentId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from nautilus_trader.trading.strategy import Strategy

from config import (
    MOCK_ACCOUNT_BALANCE, MT5_TIMEFRAME_TO_NAUTILUS_BAR,
    NAUTILUS_FX_LOT_SIZE,NAUTILUS_TO_STANDARD_FX_MULTIPLIER,
)
import mt5_lib

class EMACrossConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    trade_size_multiplier: Decimal
    fast_ema_period: int
    slow_ema_period: int

class EMACross(Strategy):
    def __init__(self, config: EMACrossConfig):
        super().__init__(config)
        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)

    def on_start(self):
        self.register_indicator_for_bars(self.config.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.config.bar_type, self.slow_ema)
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar):
        if not self.indicators_initialized():
            return

        if self.fast_ema.value >= self.slow_ema.value:
            if self.portfolio.is_flat(self.config.instrument_id):
                self.buy()
            elif self.portfolio.is_net_short(self.config.instrument_id):
                self.close_all_positions(self.config.instrument_id)
                self.buy()
        elif self.fast_ema.value < self.slow_ema.value:
            if self.portfolio.is_flat(self.config.instrument_id):
                self.sell()
            elif self.portfolio.is_net_long(self.config.instrument_id):
                self.close_all_positions(self.config.instrument_id)
                self.sell()

    def buy(self):
        instrument = self.cache.instrument(
            self.config.instrument_id
        )

        # Convert the configured strategy quantity into the quantity expected by
        # the selected instrument. The multiplier is determined from the symbol's
        # MT5 metadata, allowing different asset classes to use different quantity
        # scales.
        quantity = instrument.make_qty(
            self.config.trade_size * self.config.trade_size_multiplier
        )

        order = self.order_factory.market(
            self.config.instrument_id,
            OrderSide.BUY,
            quantity,
        )

        self.submit_order(order)

    def sell(self):
        instrument = self.cache.instrument(
            self.config.instrument_id
        )

        # Convert the configured strategy quantity into the quantity expected by
        # the selected instrument. The multiplier is determined from the symbol's
        # MT5 metadata, allowing different asset classes to use different quantity
        # scales.
        quantity = instrument.make_qty(
            self.config.trade_size * self.config.trade_size_multiplier
        )

        order = self.order_factory.market(
            self.config.instrument_id,
            OrderSide.SELL,
            quantity,
        )

        self.submit_order(order)

    def on_stop(self):
        self.close_all_positions(self.config.instrument_id)

def create_backtest_engine(account_balance: float) -> BacktestEngine:
    backtest_engine = BacktestEngine(
        config=BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"))
    )
    backtest_engine.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.HEDGING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(account_balance, USD)],
        base_currency=USD,
        default_leverage=Decimal(1),
    )

    return backtest_engine

def run_symbol_backtest(
    backtest_engine,
    symbol,
    symbol_configs,
    strategy_configs,
    trade_size_multiplier
):
    if trade_size_multiplier == NAUTILUS_TO_STANDARD_FX_MULTIPLIER:
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
    candles_df = candles_df.set_index("datetime")

    ohlc_df = candles_df[["open", "high", "low", "close"]].astype(float)

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

        bars = BarDataWrangler(bar_type, instrument).process(ohlc_df.copy())

    strategy = EMACross(
        EMACrossConfig(
            instrument_id=instrument.id,
            bar_type=bar_type,

            # Strategy trade size is expressed in Nautilus FX quantity units.
            # 1,000 Nautilus units are converted to 100,000 base-currency
            # units at order creation, equivalent to 1 standard MT5 lot.
            trade_size=NAUTILUS_FX_LOT_SIZE,
            trade_size_multiplier=trade_size_multiplier,

            fast_ema_period=strategy_configs["ema_period_one"],
            slow_ema_period=strategy_configs["ema_period_two"],
        ),
    )

    backtest_engine.add_instrument(instrument)
    backtest_engine.add_data(bars)
    backtest_engine.add_strategy(strategy)

def run_backtest(
    symbol_configs: dict,
    strategy_configs: dict,
    use_real_account_balance: bool = True,
) -> None:

    if use_real_account_balance:
        account_balance = mt5_lib.get_account_balance()
    else:
        account_balance = MOCK_ACCOUNT_BALANCE

    for symbol in symbol_configs["symbols"]:
        trade_size_multiplier = mt5_lib.get_trade_size_multiplier(symbol)
        backtest_engine = create_backtest_engine(account_balance)

        run_symbol_backtest(
            backtest_engine,
            symbol,
            symbol_configs,
            strategy_configs,
            trade_size_multiplier
        )

        backtest_engine.run()

        tearsheet_name = (f".\\reports\\backtest_tearsheet_{symbol}.html")
        create_tearsheet(engine = backtest_engine, output_path = tearsheet_name)
        report_path = os.path.realpath(tearsheet_name)
        webbrowser.open(report_path)