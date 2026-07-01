"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

import logging
import pandas as pd
import matplotlib.pyplot as plt

from config import EMA_WARMUP_MULTIPLIER
import mt5_lib

def add_ema_to_dataframe(dataframe: pd.DataFrame, ema_period: int) -> pd.DataFrame:
    ema_column = f"ema_{ema_period}"

    # add an EMA column to the dataframe using pandas' Exponential Moving Window (EWM)
    dataframe[ema_column] = dataframe['close'].ewm(
        # use the specified period for the EMA calculation
        span = ema_period,
        # calculate the EMA without adjusting for previous values, this is standard trading
        adjust = False 
    ).mean() # convert EWM into EMA
    
    return dataframe

def add_ema_cross_to_dataframe(
    dataframe: pd.DataFrame,
    ema_period_one: int,
    ema_period_two: int
) -> pd.DataFrame:
    current_position = dataframe[f"ema_{ema_period_one}"] > dataframe[f"ema_{ema_period_two}"]
    previous_position = current_position.shift(1)

    # add EMA cross column to the dataframe, setting the first value to False
    dataframe['ema_cross'] = current_position != previous_position
    dataframe['ema_cross'].iat[0] = False

    # calculate the warmup period for EMA and set the warmup values to False in the ema_cross column
    warmup = max(ema_period_one, ema_period_two) * EMA_WARMUP_MULTIPLIER
    dataframe.loc[: warmup - 1, "ema_cross"] = False
    return dataframe

def create_ema_dataframe(
    symbols: list[str],
    timeframe: str,
    ema_period_one: int,
    ema_period_two: int,
    number_of_candles: int
) -> pd.DataFrame:
    ema_df = pd.DataFrame()
    # combine candlestick data for all symbols
    for symbol in symbols:
        # collect symbol data and add symbol column
        symbol_df = mt5_lib.collect_candlesticks(symbol, timeframe, number_of_candles)
        symbol_df.insert(0, "symbol", symbol)

        # add EMA columns and EMA cross column to the dataframe
        symbol_df = add_ema_to_dataframe(symbol_df, ema_period_one)
        symbol_df = add_ema_to_dataframe(symbol_df, ema_period_two)
        symbol_df = add_ema_cross_to_dataframe(symbol_df, ema_period_one, ema_period_two)
        ema_df = pd.concat([ema_df, symbol_df], ignore_index=True)

    return ema_df

def log_ema_crosses(ema_df: pd.DataFrame) -> None:
    ema_df_cross = ema_df[ema_df["ema_cross"]]

    logging.info(f"EMA crosses:")
    print(ema_df_cross)

def plot_ema_charts(
    ema_df: pd.DataFrame,
    ema_period_one: int,
    ema_period_two: int,
) -> None:
    for symbol, symbol_df in ema_df.groupby("symbol"):
        plt.figure(figsize=(12, 6))

        plt.plot(
            symbol_df.index,
            symbol_df["close"],
            label = "Price",
        )

        plt.plot(
            symbol_df.index,
            symbol_df[f"ema_{ema_period_one}"],
            label = f"EMA {ema_period_one}",
        )

        plt.plot(
            symbol_df.index,
            symbol_df[f"ema_{ema_period_two}"],
            label = f"EMA {ema_period_two}",
        )

        # mark EMA crosses
        cross_df = symbol_df[symbol_df["ema_cross"]]
        plt.scatter(
            x = cross_df.index,
            y = cross_df["close"],
            color="red",
            marker = "o",
            label = "EMA Cross",
        )

        plt.title(symbol)
        plt.xlabel("Candle")
        plt.ylabel("Price")
        plt.legend()
        plt.grid(True)

        plt.show()

def generate_ema_report(symbol_configs: dict[str, str], strategy_configs: dict[str, str]):
    ema_df = create_ema_dataframe(
        symbol_configs["symbols"],
        symbol_configs["timeframe"],
        strategy_configs["ema_period_one"],
        strategy_configs["ema_period_two"],
        strategy_configs["number_of_candles"],
    )

    log_ema_crosses(ema_df)
    plot_ema_charts(ema_df, strategy_configs["ema_period_one"], strategy_configs["ema_period_two"])