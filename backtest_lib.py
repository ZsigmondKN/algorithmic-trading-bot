"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from datetime import datetime
from decimal import Decimal
import logging
import os
import warnings
import webbrowser

import MetaTrader5 as mt5
from nautilus_trader.analysis import create_tearsheet
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig, StrategyConfig
from nautilus_trader.model import Money, Currency
from nautilus_trader.model.data import Bar, BarType, QuoteTick
from nautilus_trader.model.enums import (
    AccountType, AssetClass, OmsType, OrderSide, OrderType
)
from nautilus_trader.model.events import PositionClosed
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import Instrument, Cfd
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider # TODO consider if I should still be using this
from nautilus_trader.trading.strategy import Strategy
import pandas as pd

from config import LOGGING_INDENT, MOCK_ACCOUNT_BALANCE, MT5_TIMEFRAME_TO_NAUTILUS_BAR
import ema_lib
import mt5_lib
import order_lib

# TODO add descriptive comments where needed and review the rest
class BacktestStatistics:
    def __init__(self):
        self.signals_generated = 0
        self.margin_rejections = 0
        self.orders_submitted = 0
        self.positions_closed_by_opposite_signal = 0
        self.backtest_wind_down_closures = 0
        self.positions_closed = 0

    def reset(self) -> None:
        self.signals_generated = 0
        self.margin_rejections = 0
        self.orders_submitted = 0
        self.positions_closed_by_opposite_signal = 0
        self.backtest_wind_down_closures = 0
        self.positions_closed = 0

    def report(self, symbol: str) -> None:
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

    def on_start(self) -> None:
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
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
                    entry_price=signal["entry_price"],
                    stop_loss=signal["stop_loss"],
                    take_profit=signal["take_profit"],
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
                    entry_price=signal["entry_price"],
                    stop_loss=signal["stop_loss"],
                    take_profit=signal["take_profit"],
                )

    def _calculate_quantity(
        self,
        instrument: Instrument,
        order_type: str,
        entry_price: float,
        stop_loss: float,
    ) -> Quantity | None:
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

    def buy(self, entry_price: float, stop_loss: float, take_profit: float) -> None:
        instrument = self.cache.instrument(self.config.instrument_id)
        quantity = self._calculate_quantity(
            instrument=instrument,
            order_type="buy_stop",
            entry_price=entry_price,
            stop_loss=stop_loss
        )

        if quantity is None:
            return

        entry_price = instrument.make_price(entry_price)
        stop_loss = instrument.make_price(stop_loss)
        take_profit = instrument.make_price(take_profit)
        
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

    def sell(self, entry_price: float, stop_loss: float, take_profit: float) -> None:
        instrument = self.cache.instrument(self.config.instrument_id)
        quantity = self._calculate_quantity(
            instrument=instrument,
            order_type="sell_stop",
            entry_price=entry_price,
            stop_loss=stop_loss
        )

        if quantity is None:
            return

        entry_price = instrument.make_price(entry_price)
        stop_loss = instrument.make_price(stop_loss)
        take_profit = instrument.make_price(take_profit)

        orders = self.order_factory.bracket(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.SELL,
            quantity=quantity,
            entry_order_type=OrderType.MARKET, # TODO not exactly like my code
            sl_trigger_price=stop_loss,
            tp_price=take_profit,
        )

        self.submit_order_list(orders)
        self.stats.orders_submitted += 1

    def on_position_closed(self, event: PositionClosed) -> None:
        self.stats.positions_closed += 1

    def on_stop(self) -> None:
        positions = self.cache.positions_open(
            instrument_id=self.config.instrument_id,
        )
        self.stats.backtest_wind_down_closures += len(positions)

        self.close_all_positions(self.config.instrument_id)


def create_exchange_rate_quotes(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> tuple[Instrument, list[QuoteTick]]:
    instrument = TestInstrumentProvider.default_fx_ccy(symbol)

    candles_df = mt5_lib.collect_historical_candlesticks(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
    )

    candles_df = mt5_lib.combine_date_time(candles_df)

    quote_ticks = []

    for _, candle in candles_df.iterrows():
        timestamp = pd.Timestamp(candle["datetime"]).value

        bid = float(candle["close"])
        ask = bid

        quote_ticks.append(
            QuoteTick(
                instrument_id=instrument.id,
                bid_price=instrument.make_price(bid),
                ask_price=instrument.make_price(ask),
                bid_size=Quantity.from_int(1),
                ask_size=Quantity.from_int(1),
                ts_event=timestamp,
                ts_init=timestamp,
            )
        )

    return instrument, quote_ticks


CFD_ASSET_CLASSES = {
    "UK100.cash": AssetClass.INDEX,
    "US500.cash": AssetClass.INDEX,
    "AAPL": AssetClass.EQUITY,
    "XAUUSD": AssetClass.COMMODITY,
}

def get_cfd_asset_class(symbol: str) -> AssetClass:
    try:
        return CFD_ASSET_CLASSES[symbol]
    except KeyError:
        raise NotImplementedError(
            f"No asset class configured for CFD '{symbol}'. "
            f"Add '{symbol}' to CFD_ASSET_CLASSES before backtesting."
        )


def assign_cfd_parameters_from_mt5(symbol_info: mt5.SymbolInfo) -> Cfd:
    tick_size = Decimal(str(symbol_info.trade_tick_size))
    volume_step = Decimal(str(symbol_info.volume_step))
    contract_size = mt5_lib.get_units_per_lot(symbol_info) # TODO create own getters with validation like this for the others
    volume_min = Decimal(str(symbol_info.volume_min))
    volume_max = Decimal(str(symbol_info.volume_max))

    if tick_size <= 0:
        raise RuntimeError(
            f"Invalid tick size for '{symbol_info.name}': {tick_size}"
        )

    if volume_step <= 0:
        raise RuntimeError(
            f"Invalid volume step for '{symbol_info.name}': {volume_step}"
        )

    if contract_size <= 0:
        raise RuntimeError(
            f"Invalid contract size for '{symbol_info.name}': {contract_size}"
        )

    if volume_min <= 0:
        raise RuntimeError(
            f"Invalid minimum volume for '{symbol_info.name}': {volume_min}"
        )

    if volume_max < volume_min:
        raise RuntimeError(
            f"Invalid volume limits for '{symbol_info.name}': "
            f"minimum={volume_min}, maximum={volume_max}"
        )

    if volume_step > volume_max:
        raise RuntimeError(
            f"Invalid volume step for '{symbol_info.name}': "
            f"step={volume_step}, maximum={volume_max}"
        )

    if symbol_info.digits < 0:
        raise RuntimeError(
            f"Invalid price precision for '{symbol_info.name}': "
            f"{symbol_info.digits}"
        )

    if not symbol_info.currency_profit:
        raise RuntimeError(
            f"MT5 did not provide a profit currency for '{symbol_info.name}'."
        )

    if not symbol_info.currency_base:
        raise RuntimeError(
            f"MT5 did not provide a base currency for '{symbol_info.name}'."
        )

    def _get_decimal_places(value: Decimal) -> int:
        if not value.is_finite():
            raise ValueError(
                f"Expected a finite Decimal, got {value}."
            )

        exponent = value.as_tuple().exponent

        if not isinstance(exponent, int):
            raise ValueError(
                f"Expected an integer Decimal exponent, got {exponent}."
            )

        if exponent >= 0:
            return 0

        return -exponent

    size_precision = _get_decimal_places(volume_step)

    if _get_decimal_places(tick_size) > symbol_info.digits:
        raise RuntimeError(
            f"Tick size {tick_size} for '{symbol_info.name}' requires more "
            f"decimal places than MT5 digits={symbol_info.digits}."
        )

    return Cfd(
        instrument_id=InstrumentId.from_str(f"{symbol_info.name}.SIM"),
        raw_symbol=Symbol(symbol_info.name),
        asset_class=get_cfd_asset_class(symbol_info.name),
        base_currency=Currency.from_str(symbol_info.currency_base),
        quote_currency=Currency.from_str(symbol_info.currency_profit),

        price_precision=symbol_info.digits,
        price_increment=Price.from_str(str(tick_size)),

        size_precision=size_precision,
        size_increment=Quantity.from_str(str(volume_step)),

        lot_size=Quantity.from_str(str(contract_size)),
        min_quantity=Quantity.from_str(str(volume_min)),
        max_quantity=Quantity.from_str(str(volume_max)),

        ts_event=0,
        ts_init=0,
    )


def create_instrument(symbol_info: mt5.SymbolInfo) -> Instrument:
    if symbol_info is None:
        raise RuntimeError(f"MT5 symbol '{symbol}' was not found.")

    if symbol_info.trade_calc_mode == mt5.SYMBOL_CALC_MODE_FOREX:
        return TestInstrumentProvider.default_fx_ccy(symbol_info.name)

    if symbol_info.trade_calc_mode == mt5.SYMBOL_CALC_MODE_EXCH_STOCKS:
        return TestInstrumentProvider.equity(symbol_info.name, venue="SIM")

    if symbol_info.trade_calc_mode in (
        mt5.SYMBOL_CALC_MODE_CFD,
        mt5.SYMBOL_CALC_MODE_CFDINDEX,
        mt5.SYMBOL_CALC_MODE_CFDLEVERAGE,
    ):
        return assign_cfd_parameters_from_mt5(symbol_info)

    raise NotImplementedError(
        f"Unsupported MT5 trade calculation mode "
        f"{symbol_info.trade_calc_mode} for '{symbol_info.name}'."
    )


def create_backtest_candles(
    symbol: str,
    symbol_configs: dict
) -> pd.DataFrame:
    if symbol_configs["historical_timeframe"]:
        historical_start_time = symbol_configs["historical_start_time"]
        historical_end_time = symbol_configs["historical_end_time"]

        candles_df = mt5_lib.collect_historical_candlesticks(
            symbol=symbol,
            timeframe=symbol_configs["timeframe"],
            start_date=historical_start_time,
            end_date=historical_end_time,
        )

        logging.debug(
            f"Backtesting {symbol} on historical data from "
            f"{historical_start_time} till {historical_end_time}."
        )
    else:
        timeframe = symbol_configs["timeframe"]
        number_of_candles = symbol_configs["number_of_candles"]
        candles_df = mt5_lib.collect_current_candlesticks(
            symbol=symbol,
            timeframe=timeframe,
            number_of_candles=number_of_candles,
        )

        logging.debug(
            f"Backtesting {symbol} on {number_of_candles} live candles, "
            f"with widths of {timeframe}."
        )

    return candles_df


def get_backtest_bars(
    bar_type: BarType,
    instrument: Instrument,
    ema_df: pd.DataFrame
) -> list[Bar]:
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
    

def get_conversion_symbol(
    instrument: Instrument,
    account_currency: str,
) -> str | None:
    quote_currency = str(instrument.quote_currency)

    if quote_currency == account_currency:
        return None

    direct_symbol = f"{account_currency}{quote_currency}"
    inverse_symbol = f"{quote_currency}{account_currency}"

    if mt5.symbol_info(direct_symbol) is not None:
        return direct_symbol

    if mt5.symbol_info(inverse_symbol) is not None:
        return inverse_symbol

    raise RuntimeError(
        f"No FX conversion pair found for "
        f"{quote_currency}/{account_currency}. "
        f"Tried '{direct_symbol}' and '{inverse_symbol}'."
    )


def run_symbol_backtest(
    backtest_engine: BacktestEngine,
    symbol: str,
    symbol_configs: dict,
    order_configs: dict,
    strategy_configs: dict,
    statistics: BacktestStatistics,
) -> None:
    symbol_info = mt5_lib.get_symbol_info(symbol)

    instrument = create_instrument(symbol_info)
    units_per_lot = mt5_lib.get_units_per_lot(symbol_info)

    candles_df = create_backtest_candles(
        symbol=symbol,
        symbol_configs=symbol_configs,
    )
    candles_df = mt5_lib.combine_date_time(candles_df)
    ema_df = ema_lib.create_ema_dataframe(
        symbol=symbol,
        candle_dataframe=candles_df.copy(),
        risk_reward_ratio=order_configs["risk_reward_ratio"],
        ema_period_one=strategy_configs["ema_period_one"],
        ema_period_two=strategy_configs["ema_period_two"],
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

    account_currency = order_configs["base_currency"]
    exchange_rate_symbol = get_conversion_symbol(
        instrument=instrument,
        account_currency=account_currency,
    )
    
    if exchange_rate_symbol is not None:
        (
            exchange_rate_instrument,
            exchange_rate_quotes,
        ) = create_exchange_rate_quotes(
            symbol=exchange_rate_symbol,
            timeframe=symbol_configs["timeframe"],
            start_date=symbol_configs["historical_start_time"],
            end_date=symbol_configs["historical_end_time"],
        )

        backtest_engine.add_instrument(exchange_rate_instrument)
        backtest_engine.add_data(exchange_rate_quotes)

    backtest_engine.add_strategy(strategy)


def create_backtest_engine(
    account_balance: float,
    base_currency: str,
    account_leverage: int
) -> BacktestEngine:
    currency = Currency.from_str(base_currency)
    backtest_engine = BacktestEngine(
        config=BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR"))
    )
    backtest_engine.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.HEDGING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(account_balance, currency)],
        base_currency=currency,
        default_leverage=Decimal(account_leverage)
    )

    return backtest_engine


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
        backtest_engine = create_backtest_engine(
            account_balance=account_balance,
            base_currency=order_configs["base_currency"],
            account_leverage=order_configs["account_leverage"]
        )

        logging.info(f"Running backtest on {symbol} symbol.")

        run_symbol_backtest(
            backtest_engine=backtest_engine,
            symbol=symbol,
            symbol_configs=symbol_configs,
            order_configs=order_configs,
            strategy_configs=strategy_configs,
            statistics=statistics
        )

        backtest_engine.run()
        statistics.report(symbol)
        statistics.reset()

        tearsheet_name = f".\\reports\\backtest_tearsheet_{symbol}.html"
        create_tearsheet(
            engine=backtest_engine,
            output_path=tearsheet_name
        )
        report_path = os.path.realpath(tearsheet_name)
        webbrowser.open(report_path)