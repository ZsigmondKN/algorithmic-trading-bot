"""
Author: Zsigmond Kovacs-Nagy
Description: ...
"""

import MetaTrader5 as mt5

from config import LOT_SIZE_CALCULATION_VALUE, ORDER_FULFILL_TIME

def get_account_balance() -> float:
    account_info = mt5.account_info()
    if account_info is None:
        raise RuntimeError(f"Unable to retrieve account information: {mt5.last_error()}")

    return account_info.balance

def validate_symbol_info(symbol: str) -> tuple:
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Unknown symbol: {symbol}")
    
    return info

def validate_order_type(order_type: str) -> int:
    if order_type == 'buy_stop':
        return mt5.ORDER_TYPE_BUY_STOP
    elif order_type == 'sell_stop':
        return mt5.ORDER_TYPE_SELL_STOP
    else:
        raise RuntimeError(f"Unrecognised order type of: {order_type}.")

def normalise_price_parameters(
    symbol_info: tuple, stop_loss: float, take_profit: float, entry_price: float
) -> tuple:
    price_digits = symbol_info.digits
    stop_loss = round(stop_loss, price_digits)
    take_profit = round(take_profit, price_digits)
    entry_price = round(entry_price, price_digits)

    return stop_loss, take_profit, entry_price

def normalise_lot_size(symbol_info: tuple, lot_size: float) -> float:
    if lot_size <= 0:
        raise ValueError(f"Lot size must be positive, got {lot_size}.")
    
    step = symbol_info.volume_step
    lot_size = round(lot_size / step) * step
    lot_size = max(symbol_info.volume_min, lot_size)
    lot_size = min(symbol_info.volume_max, lot_size)

    return lot_size

def calculate_lot_size(
    balance: float,
    risk_percentage: float,
    order_type: str,
    symbol: str,
    entry_price: float,
    stop_loss: float
) -> float:
    symbol_info = validate_symbol_info(symbol)
    valid_order_type = validate_order_type(order_type)
    
    # Calculate the loss for a 1.0 lot position
    loss_per_lot = mt5.order_calc_profit(
        valid_order_type,
        symbol,
        LOT_SIZE_CALCULATION_VALUE,
        entry_price,
        stop_loss,
    )

    error_log_parameters = (
        f"order_type={valid_order_type}, "
        f"symbol={symbol}, "
        f"lot_size_calculation_value={LOT_SIZE_CALCULATION_VALUE} ,"
        f"entry_price={entry_price}, "
        f"stop_loss={stop_loss}, "
        f"loss_per_lot={loss_per_lot}"
    )
    if loss_per_lot is None:
        raise RuntimeError(f"MT5 was unable to calculate the loss_per_lot for: {error_log_parameters}.")
    if loss_per_lot >= 0:
        raise ValueError(f"The loss_per_lot was expected to be negative, for: {error_log_parameters}.")
    
    abs_loss_per_lot = -loss_per_lot
    risk_amount = balance * risk_percentage
    lot_size = risk_amount / abs_loss_per_lot
    lot_size = normalise_lot_size(symbol_info, lot_size)

    return lot_size

def build_order_request(
    symbol: str,
    lot_size: float,
    order_type: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    comment: str,
) -> dict:
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot_size,
        "type": validate_order_type(order_type),
        "price": entry_price,
        "sl": stop_loss,
        "tp": take_profit,
        "comment": comment,
        "type_time": ORDER_FULFILL_TIME,
        "type_filling": mt5.ORDER_FILLING_RETURN
    }

    return request

def validate_order_request_response(result, action: str) -> None:
    if result is None:
        raise RuntimeError(
            f"{action} failed: {mt5.last_error()}."
        )

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(
            f"{action} failed with retcode={result.retcode} and comment='{result.comment}'."
        )

def place_order(
    symbol: str,
    lot_size: float,
    order_type: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    comment: str,
    bypass_order_check: bool = False
) -> mt5.OrderSendResult:
    symbol_info = validate_symbol_info(symbol)
    normalised_lot_size = normalise_lot_size(symbol_info, lot_size)
    normalised_stop_loss, normalised_take_profit, normalised_entry_price = normalise_price_parameters(
        symbol_info, stop_loss, take_profit, entry_price
    )

    request = build_order_request(
        symbol,
        normalised_lot_size,
        order_type,
        normalised_entry_price,
        normalised_stop_loss,
        normalised_take_profit,
        comment
    )

    if not bypass_order_check:
        check_result = mt5.order_check(request)
        validate_order_request_response(check_result, "Order check")
    
    order_result = mt5.order_send(request)
    validate_order_request_response(order_result, "Order submission")
    
    return order_result