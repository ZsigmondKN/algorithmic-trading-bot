"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from datetime import datetime
from decimal import Decimal
import logging
import MetaTrader5 as mt5
import numpy as np
import pandas as pd

from config import LOGIN_TIMEOUT, MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST

def login(configs: dict[str, str]) -> None:
    account_username = configs['username']
    account_server = configs['server']
    account_password = configs['password']

    login_success = mt5.initialize(
        login=int(account_username), 
        password=account_password, 
        server=account_server,
        timeout=LOGIN_TIMEOUT
    )

    if not login_success:
        raise RuntimeError("Failed to initialize MT5 with the provided login credentials.")
    logging.info("Connection established to MT5.")

def validate_and_initialise_symbols(symbol_configs: dict[str, str]) -> None:
    available_symbols = {symbol.name for symbol in mt5.symbols_get()}

    for symbol in symbol_configs['symbols']:
        if symbol not in available_symbols:
            raise ValueError(
                f"Symbol '{symbol}' not found in this MT5 version. Update symbol name."
            )
        # attempt to initialise the symbol
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to initialise symbol: {symbol}")

    logging.info("All requested symbols successfully initialised.\n")

def validate_timeframe(timeframe: str) -> int:
    try:
        return getattr(mt5, f"TIMEFRAME_{timeframe}")
    except AttributeError:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
def validate_candles(symbol, candles) -> np.ndarray:
    if candles is None:
        raise RuntimeError(
            f"Failed to retrieve data for {symbol}. Error provided: {mt5.last_error()}"
        )

    return candles
    
def split_date_time(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe["time"] = pd.to_datetime(dataframe["time"], unit="s", utc=True)

    dataframe.insert( 0, "date", dataframe["time"].dt.date )
    dataframe["time"] = dataframe["time"].dt.time
    
    return dataframe

def combine_date_time(dataframe: pd.DataFrame)-> pd.DataFrame:
    dataframe["datetime"] = pd.to_datetime(
        dataframe["date"].astype(str)
        + " "
        + dataframe["time"].astype(str),
        utc=True,
    )

    return dataframe.sort_values("datetime")

def collect_current_candlesticks(
    symbol: str,
    timeframe: str,
    number_of_candles: int
) -> pd.DataFrame:
    if number_of_candles > MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST:
        raise ValueError(
            f"Cannot retrieve more than {MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST} "
            "candlesticks at once."
        )

    mt5_timeframe = validate_timeframe(timeframe)
    
    # Skip the current candle
    initial_candle_index = 1
    
    candles = mt5.copy_rates_from_pos(
        symbol,
        mt5_timeframe,
        initial_candle_index,
        number_of_candles
    )
    validate_candles(symbol, candles)

    dataframe = pd.DataFrame(candles)
    dataframe = split_date_time(dataframe)
    
    return dataframe

def collect_historical_candlesticks(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    mt5_timeframe = validate_timeframe(timeframe)

    if start_date >= end_date:
        raise ValueError("The start date must be earlier than the end date.")

    candles = mt5.copy_rates_range(
        symbol,
        mt5_timeframe,
        start_date,
        end_date
    )
    candles = validate_candles(symbol, candles)

    if len(candles) == 0:
        raise RuntimeError(
            f"No historical data was returned for {symbol} "
            f"between {start_date} and {end_date}."
        )

    dataframe = pd.DataFrame(candles)
    dataframe = split_date_time(dataframe)

    return dataframe

def get_account_balance() -> float:
    account_info = mt5.account_info()
    if account_info is None:
        raise RuntimeError(f"Unable to retrieve account information: {mt5.last_error()}")

    return account_info.balance

def get_symbol_info(symbol: str) -> mt5.SymbolInfo:
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise ValueError(f"Unknown symbol: {symbol}")
    
    return symbol_info

def validate_order_direction(order_type: str) -> int:
    if order_type == 'buy_stop':
        return mt5.ORDER_TYPE_BUY
    elif order_type == 'sell_stop':
        return mt5.ORDER_TYPE_SELL
    else:
        raise RuntimeError(f"Unrecognised order type of: {order_type}.")

def validate_order_type(order_type: str) -> int:
    if order_type == 'buy_stop':
        return mt5.ORDER_TYPE_BUY_STOP
    elif order_type == 'sell_stop':
        return mt5.ORDER_TYPE_SELL_STOP
    else:
        raise RuntimeError(f"Unrecognised order type of: {order_type}.")

def get_units_per_lot(symbol: str) -> Decimal:
    symbol_info = get_symbol_info(symbol)
    contract_size = symbol_info.trade_contract_size

    if contract_size <= 0:
        raise ValueError(
            f"Invalid trade_contract_size={contract_size} for '{symbol}'."
        )

    return Decimal(str(contract_size))