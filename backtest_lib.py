"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import warnings
from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider

import numpy as np
import pandas as pd
from nautilus_trader.analysis import create_tearsheet
import webbrowser
import os

from config import BACKTEST_TEARSHEET_NAME
import mt5_lib


class EMACrossConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
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
        instrument = self.cache.instrument(self.config.instrument_id)
        order = self.order_factory.market(
            self.config.instrument_id,
            OrderSide.BUY,
            instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)

    def sell(self):
        instrument = self.cache.instrument(self.config.instrument_id)
        order = self.order_factory.market(
            self.config.instrument_id,
            OrderSide.SELL,
            instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)

    def on_stop(self):
        self.close_all_positions(self.config.instrument_id)

def run_backtest(
    strategy_configs: dict,
    symbol_configs: dict,
    use_real_account_balance:bool = True
) -> None:

    # Create a EUR/USD instrument on the SIM venue
    EURUSD = TestInstrumentProvider.default_fx_ccy("EUR/USD")

    # Generate synthetic 1-minute bars (random walk around 1.10)
    rng = np.random.default_rng(42)
    n = 100_000
    price = 1.10 + np.cumsum(rng.normal(0, 0.0002, n))
    spread = np.abs(rng.normal(0, 0.0003, n))
    bars_df = pd.DataFrame(
        {
            "open": price,
            "high": price + spread,
            "low": price - spread,
            "close": price + rng.normal(0, 0.00005, n),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC"),
    )
    bars_df["high"] = bars_df[["open", "high", "close"]].max(axis=1)
    bars_df["low"] = bars_df[["open", "low", "close"]].min(axis=1)

    bar_type = BarType.from_str("EUR/USD.SIM-1-MINUTE-LAST-EXTERNAL")

    # suppress insignificant known library warning
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="A value is being set on a copy of a DataFrame or "
            "Series through chained assignment."
        )
        bars = BarDataWrangler(bar_type, EURUSD).process(bars_df.copy())

    if use_real_account_balance:
        account_balance = mt5_lib.get_account_balance()
    else:
        account_balance = 500000

    strategy = EMACross(
        EMACrossConfig(
            instrument_id=EURUSD.id, #TODO
            bar_type=bar_type, #TODO
            trade_size=Decimal(100000), #TODO
            fast_ema_period=strategy_configs["ema_period_one"],
            slow_ema_period=strategy_configs["ema_period_two"],
        ),
    )

    backtest_engin = BacktestEngine(
        config=BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"))
    )
    backtest_engin.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.HEDGING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(account_balance, USD)],
        base_currency=USD,
        default_leverage=Decimal(1),
    )
    backtest_engin.add_instrument(EURUSD)
    backtest_engin.add_data(bars)
    backtest_engin.add_strategy(strategy)

    backtest_engin.run()

    create_tearsheet(engine = backtest_engin, output_path = BACKTEST_TEARSHEET_NAME)
    report_path = os.path.realpath(BACKTEST_TEARSHEET_NAME)
    webbrowser.open(report_path)