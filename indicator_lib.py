import pandas as pd

def calculate_ema(dataframe: pd.DataFrame, ema_period: int) -> pd.DataFrame:
    ema_column = f"ema_{ema_period}"
    dataframe[ema_column] = dataframe['close'].ewm(span=ema_period, adjust=False).mean()
    return dataframe

def ema_cross_calculator(dataframe: pd.DataFrame, ema_one: int, ema_two: int) -> pd.DataFrame:
    current_position = dataframe[f"ema_{ema_one}"] > dataframe[f"ema_{ema_two}"]
    previous_position  = current_position.shift(1)
    dataframe['ema_cross'] = current_position != previous_position
    dataframe['ema_cross'].iat[0] = False
    return dataframe