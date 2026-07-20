"""
Author: Zsigmond Kovacs-Nagy
Description: Compute and use Exponential Moving Averages (EMAs).
"""

import logging
import pandas as pd
import matplotlib.dates as mdates
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
    dataframe.loc[dataframe.index[0], "ema_cross"] = False
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
    candle_dataframe: pd.DataFrame,
    ema_period_one: int,
    ema_period_two: int,
) -> pd.DataFrame:
    smaller_ema_period, larger_ema_period = check_and_order_emas(ema_period_one, ema_period_two)
    warmup_period = int(max(smaller_ema_period, larger_ema_period) * EMA_WARMUP_MULTIPLIER)

    candle_dataframe.insert(0, "symbol", symbol)

    # add EMA values and trade parameters
    candle_dataframe = add_ema_to_dataframe(candle_dataframe, smaller_ema_period)
    candle_dataframe = add_ema_to_dataframe(candle_dataframe, larger_ema_period)
    candle_dataframe = add_ema_cross_and_action_to_dataframe(
        candle_dataframe, warmup_period, smaller_ema_period, larger_ema_period
    )
    candle_dataframe = add_ema_trade_parameters_to_dataframe(
        candle_dataframe, smaller_ema_period, larger_ema_period
    )

    return candle_dataframe

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
        plot_datetime = pd.to_datetime(
            symbol_df["date"].astype(str)
            + " "
            + symbol_df["time"].astype(str),
            utc=True
        )

        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(
            plot_datetime,
            symbol_df["close"],
            label="Price",
        )

        ax.plot(
            plot_datetime,
            symbol_df[f"ema_{ema_period_one}"],
            label=f"EMA {ema_period_one}",
        )

        ax.plot(
            plot_datetime,
            symbol_df[f"ema_{ema_period_two}"],
            label=f"EMA {ema_period_two}",
        )

        # Mark EMA crosses
        cross_mask = symbol_df["ema_cross"]

        ax.scatter(
            plot_datetime[cross_mask],
            symbol_df.loc[cross_mask, "close"],
            color="red",
            marker="o",
            label="EMA Cross",
        )

        # Let Matplotlib choose the date or time labels
        locator = mdates.AutoDateLocator()

        ax.xaxis.set_major_locator(locator)

        ax.xaxis.set_major_formatter(
            mdates.ConciseDateFormatter(locator)
        )

        ax.set_title(symbol)
        ax.set_xlabel("Date and Time")
        ax.set_ylabel("Price")

        ax.legend()
        ax.grid(True)

        fig.autofmt_xdate()

        plt.show()

def generate_ema_report(symbol_configs: dict[str, str], strategy_configs: dict[str, str]):
    combined_ema_df = pd.DataFrame()
    for symbol in symbol_configs["symbols"]:
        if symbol_configs["historical_timeframe"]:
            candle_dataframe = mt5_lib.collect_historical_candlesticks(
                symbol,
                symbol_configs["timeframe"],
                symbol_configs["historical_start_time"],
                symbol_configs["historical_end_time"]
            )
        else:
            candle_dataframe = mt5_lib.collect_current_candlesticks(
                symbol,
                symbol_configs["timeframe"],
                symbol_configs["number_of_candles"]
            )
        
        symbol_ema_df = create_ema_dataframe(
            symbol,
            candle_dataframe,
            strategy_configs["ema_period_one"],
            strategy_configs["ema_period_two"],
        )
        combined_ema_df = pd.concat([combined_ema_df, symbol_ema_df], ignore_index = True)

    log_ema_crosses(combined_ema_df)
    plot_ema_charts(
        combined_ema_df, 
        strategy_configs["ema_period_one"], 
        strategy_configs["ema_period_two"]
    )