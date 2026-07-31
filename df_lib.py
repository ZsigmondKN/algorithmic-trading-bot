"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

from typing import TypeVar

import pandas as pd

T = TypeVar("T")

def get_df_val(df: pd.DataFrame, index: int, column: str, expected_type: type[T]) -> T:
    value = df.loc[index, column]

    if not isinstance(value, expected_type):
        raise TypeError(
            f"Expected '{column}' to contain {type.__name__}, got {type(value).__name__}."
        )

    return value