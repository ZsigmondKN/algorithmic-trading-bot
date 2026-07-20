"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from datetime import datetime
import logging
import MetaTrader5 as mt5
import pandas as pd

from config import MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST

def login(configs: dict[str, str]) -> None:
    account_username = configs['username']
    account_server = configs['server']
    account_password = configs['password']

    login_success = mt5.initialize(
        login=int(account_username), 
        password=account_password, 
        server=account_server
    )

    if not login_success:
        raise RuntimeError("Failed to initialize MT5 with the provided login credentials.")
    logging.info("Connection established to MT5.")

def validate_and_initialise_symbols(symbol_configs: dict[str, str]) -> None:
    available_symbols = {symbol.name for symbol in mt5.symbols_get()}

    for symbol in symbol_configs['symbols']:
        if symbol not in available_symbols:
            raise ValueError(f"Symbol '{symbol}' not found in this MT5 version. Update symbol name.")
        # attempt to initialise the symbol
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Failed to initialise symbol: {symbol}")

    logging.info("All requested symbols successfully initialised.\n")

def validate_timeframe(timeframe: str) -> int:
    try:
        return getattr(mt5, f"TIMEFRAME_{timeframe}")
    except AttributeError:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    
def validate_candles(symbol, candles) -> None:
    if candles is None:
        raise RuntimeError(
            f"Failed to retrieve data for {symbol}. Error provided: {mt5.last_error()}"
        )
    
def time_date_convert(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe["time"] = pd.to_datetime(dataframe["time"], unit="s", utc=True)

    dataframe.insert( 0, "date", dataframe["time"].dt.date )
    dataframe["time"] = dataframe["time"].dt.time
    
    return dataframe

def collect_current_candlesticks(symbol: str, timeframe: str, number_of_candles: int) -> pd.DataFrame:
    if number_of_candles > MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST:
        raise ValueError(
            f"Cannot retrieve more than {MAXIMUM_MT5_CANDLE_COUNT_PER_REQUEST} candlesticks at once."
        )

    mt5_timeframe = validate_timeframe(timeframe)
    
    # Skip the current candle
    initial_candle_index = 1
    
    candles = mt5.copy_rates_from_pos(symbol, mt5_timeframe, initial_candle_index, number_of_candles)
    validate_candles(symbol, candles)

    dataframe = pd.DataFrame(candles)
    dataframe = time_date_convert(dataframe)
    
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
    validate_candles(symbol, candles)

    if len(candles) == 0:
        raise RuntimeError(
            f"No historical data was returned for {symbol} between {start_date} and {end_date}."
        )

    dataframe = pd.DataFrame(candles)
    dataframe = time_date_convert(dataframe)

    return dataframe