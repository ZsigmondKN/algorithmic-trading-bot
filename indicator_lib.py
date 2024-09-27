import numpy as np

def calc_custom_ema(dataframe, ema_size):
    ema_name = "ema_" + str(ema_size)
    multiplier = 2 / (ema_size + 1)
    initial_mean = dataframe['close'].head(ema_size).mean()

    for i in range(len(dataframe)): 
        if i == ema_size:
            dataframe.loc[i, ema_name] = initial_mean
        elif i > ema_size:
            ema_value = dataframe.loc[i, 'close'] * multiplier + dataframe.loc[i - 1, ema_name] * (1 - multiplier)
            dataframe.loc[i, ema_name] = ema_value
        else:
            dataframe.loc[i, ema_name] = 0.00
    return dataframe