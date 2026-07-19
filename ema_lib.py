"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

import logging
import pandas as pd
import matplotlib.pyplot as plt

from config import EMA_WARMUP_MULTIPLIER
import mt5_lib

def check_and_order_emas(ema_period_one: int, ema_period_two: int) -> tuple[int, int]:
    if ema_period_one == ema_period_two:
        raise ValueError("EMA periods are equivalent.")

    return min(ema_period_one, ema_period_two), max(ema_period_one, ema_period_two)

def add_ema_to_dataframe(dataframe: pd.DataFrame, ema_period: int) -> pd.DataFrame:
    ema_column = f"ema_{ema_period}"

    # add an EMA column to the dataframe using pandas' Exponential Moving Window (EWM)
    dataframe[ema_column] = dataframe['close'].ewm(
        span = ema_period,
        # calculate the EMA without adjusting for previous values, this is standard for trading
        adjust = False 
    ).mean() # convert EWM into EMA
    
    return dataframe

def add_ema_cross_and_action_to_dataframe(
    dataframe: pd.DataFrame,
    warmup_period: int,
    smaller_ema_period: int,
    larger_ema_period: int
) -> pd.DataFrame:
    is_current_pos_bullish = dataframe[f"ema_{larger_ema_period}"] < dataframe[f"ema_{smaller_ema_period}"]
    is_previous_pos_bullish = is_current_pos_bullish.shift(1)

    dataframe['ema_cross'] = is_current_pos_bullish != is_previous_pos_bullish
    dataframe['ema_cross'].iat[0] = False
    dataframe.loc[:warmup_period - 1, "ema_cross"] = False

    dataframe["order_type"] = "n/a"
    dataframe.loc[
        dataframe["ema_cross"] & is_current_pos_bullish, "order_type"
    ] = "buy_stop"
    dataframe.loc[
        dataframe["ema_cross"] & ~is_current_pos_bullish, "order_type"
    ] = "sell_stop"

    return dataframe

def add_ema_trade_parameters_to_dataframe(
    dataframe: pd.DataFrame,
    smaller_ema_period: int,
    larger_ema_period: int
) -> pd.DataFrame:
    dataframe["stop_loss"] = float("nan")
    dataframe["entry_price"] = float("nan")
    dataframe["take_profit"] = float("nan")
    dataframe["valid_trade"] = False

    crosses = dataframe.index[dataframe["ema_cross"]]
    
    for i in crosses:
        order_type = dataframe.loc[i, 'order_type']
        if order_type == "buy_stop":
            stop_loss = min(
                dataframe.loc[i, f"ema_{smaller_ema_period}"],
                dataframe.loc[i, f"ema_{larger_ema_period}"],
            )
            entry_price = dataframe.loc[i, 'high']
            valid_trade = stop_loss < entry_price

            if not valid_trade:
                continue

            diff = entry_price - stop_loss
            take_profit = entry_price + diff
        elif order_type == "sell_stop":
            stop_loss = max(
                dataframe.loc[i, f"ema_{smaller_ema_period}"],
                dataframe.loc[i, f"ema_{larger_ema_period}"],
            )
            entry_price = dataframe.loc[i, 'low']
            valid_trade = entry_price < stop_loss

            if not valid_trade:
                continue

            diff = stop_loss - entry_price
            take_profit = entry_price - diff
        else:
            raise ValueError(f"Unrecognised order type of '{order_type}' assigned to ema cross.")

        dataframe.loc[i, 'valid_trade'] = True
        dataframe.loc[i, 'stop_loss'] = stop_loss
        dataframe.loc[i, 'entry_price'] = entry_price
        dataframe.loc[i, 'take_profit'] = take_profit

    return dataframe

def create_ema_dataframe(
    symbol: str,
    timeframe: str,
    ema_period_one: int,
    ema_period_two: int,
    number_of_candles: int
) -> pd.DataFrame:
    smaller_ema_period, larger_ema_period = check_and_order_emas(ema_period_one, ema_period_two)
    warmup_period = int(max(smaller_ema_period, larger_ema_period) * EMA_WARMUP_MULTIPLIER)

    symbol_ema_df = mt5_lib.collect_candlesticks(symbol, timeframe, number_of_candles)
    symbol_ema_df.insert(0, "symbol", symbol)

    # add EMA values and trade parameters
    symbol_ema_df = add_ema_to_dataframe(symbol_ema_df, smaller_ema_period)
    symbol_ema_df = add_ema_to_dataframe(symbol_ema_df, larger_ema_period)
    symbol_ema_df = add_ema_cross_and_action_to_dataframe(
        symbol_ema_df, warmup_period, smaller_ema_period, larger_ema_period
    )
    symbol_ema_df = add_ema_trade_parameters_to_dataframe(
        symbol_ema_df, smaller_ema_period, larger_ema_period
    )

    return symbol_ema_df

def log_ema_crosses(ema_df: pd.DataFrame) -> None:
    ema_df_cross = ema_df[ema_df["ema_cross"]]

    logging.info(f"EMA dataframe:")
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
    combined_ema_df = pd.DataFrame()
    for symbol in symbol_configs["symbols"]:
        symbol_ema_df = create_ema_dataframe(
            symbol,
            symbol_configs["timeframe"],
            strategy_configs["ema_period_one"],
            strategy_configs["ema_period_two"],
            strategy_configs["number_of_candles"],
        )
        combined_ema_df = pd.concat([combined_ema_df, symbol_ema_df], ignore_index = True)

    log_ema_crosses(combined_ema_df)
    plot_ema_charts(
        combined_ema_df, 
        strategy_configs["ema_period_one"], 
        strategy_configs["ema_period_two"]
    )