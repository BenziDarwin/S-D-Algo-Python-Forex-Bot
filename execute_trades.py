import numpy as np
import pandas as pd
from dotenv import load_dotenv
import os

from zones import combine_nearby_zones, Zone

load_dotenv()

def get_env_var(var_name, var_type, default_value=None):
    """Retrieve and validate environment variable."""
    value = os.getenv(var_name, default_value)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is missing.")
    
    try:
        return var_type(value)
    except ValueError:
        raise ValueError(f"Environment variable '{var_name}' must be type {var_type.__name__}. Got: {value}")

# Configuration variables
RISK_PERCENT = get_env_var('RISK_PERCENT', float)
MIN_POSITION_SIZE = get_env_var('MIN_POSITION_SIZE', float)
REWARD_RISK_RATIO = get_env_var('REWARD_RISK_RATIO', float)
MAX_POSITIONS = get_env_var('MAX_POSITIONS', int)
MAGIC_NUMBER = get_env_var('MAGIC_NUMBER', int)
ZONE_BUFFER_PIPS = get_env_var('ZONE_BUFFER_PIPS', int, 10)
IMPACT_THRESHOLD_PIPS = get_env_var('IMPACT_THRESHOLD_PIPS', int)

def check_news_impact(mt5, symbol, impact_threshold_pips=IMPACT_THRESHOLD_PIPS):
    """Check for unusual price movements that might indicate high volatility"""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 2)
    if rates is None:
        return True
        
    price_change = abs(rates[-1]['close'] - rates[-1]['open'])
    point = mt5.symbol_info(symbol).point
    price_change_pips = price_change / point
    
    return price_change_pips > impact_threshold_pips

def calculate_position_size(mt5, symbol, risk_percent=RISK_PERCENT, sl_pips=None):
    """Calculate position size based on account risk management"""
    account_info = mt5.account_info()
    if account_info is None:
        return MIN_POSITION_SIZE
        
    point = mt5.symbol_info(symbol).point
    tick_value = mt5.symbol_info(symbol).trade_tick_value
    
    risk_amount = account_info.balance * (risk_percent / 100)
    
    sl_amount = sl_pips * point * (tick_value / point)
    position_size = risk_amount / sl_amount
    
    position_size = round(max(position_size, MIN_POSITION_SIZE), 2)
    return position_size

from typing import List

def open_sell_positions(mt5, symbol: str, supply_zones: List[Zone], sell_liquidity: List[Zone], max_positions=MAX_POSITIONS):
    """Open sell positions based on the most recent supply or sell liquidity zone using bid price."""
    if check_news_impact(mt5, symbol):
        print("High volatility detected - avoiding new positions.")
        return

    open_positions = [
        pos for pos in mt5.positions_get(symbol=symbol) if pos.type == mt5.ORDER_TYPE_SELL
    ]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} sell positions already open.")
        return

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("Failed to retrieve current price.")
        return

    bid_price = tick.bid
    point = mt5.symbol_info(symbol).point

    # Combine zones and use the most recent one
    all_zones = combine_nearby_zones(supply_zones + sell_liquidity)
    if not all_zones:
        print("No valid supply or sell liquidity zones available.")
        return

    recent_zone = max(all_zones, key=lambda z: z.timestamp)  # Most recent zone

    if bid_price < recent_zone.price:
        print(f"Current bid price {bid_price} is below the sell zone at {recent_zone.price}. Skipping trade.")
        return
    
    entry_price = bid_price  # Use current bid price
    sl_price = recent_zone.price + (ZONE_BUFFER_PIPS * point)
    tp_price = entry_price - ((sl_price - entry_price) * REWARD_RISK_RATIO)

    # Ensure no duplicate positions near the entry price
    if any(abs(pos.price_open - entry_price) < (5 * point) for pos in open_positions):
        print(f"Sell position already exists near the most recent zone at {recent_zone.price}.")
        return

    # Calculate position size
    volume = calculate_position_size(mt5, symbol, risk_percent=RISK_PERCENT, sl_pips=(sl_price - entry_price) / point)
    if volume <= 0:
        print("Position size calculation resulted in zero or negative volume.")
        return

    # Check margin requirements
    margin_needed = mt5.order_calc_margin(mt5.ORDER_TYPE_SELL, symbol, volume, entry_price)
    account_info = mt5.account_info()
    if not account_info or account_info.margin_free < margin_needed:
        print("Insufficient margin to open sell order.")
        return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL,
        "price": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": f"Sell order at zone {recent_zone.type}",
        "type_time": mt5.ORDER_TIME_GTC
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to open sell order. Retcode: {result.retcode}")
    else:
        print(f"Sell order opened at {entry_price}. SL: {sl_price}, TP: {tp_price}, Volume: {volume}")


def open_buy_positions(mt5, symbol: str, demand_zones: List[Zone], buy_liquidity: List[Zone], max_positions=MAX_POSITIONS):
    """Open buy positions based on the most recent demand or buy liquidity zone using ask price."""
    if check_news_impact(mt5, symbol):
        print("High volatility detected - avoiding new positions.")
        return

    open_positions = [
        pos for pos in mt5.positions_get(symbol=symbol) if pos.type == mt5.ORDER_TYPE_BUY
    ]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} buy positions already open.")
        return

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print("Failed to retrieve current price.")
        return

    ask_price = tick.ask
    point = mt5.symbol_info(symbol).point
    
        # Combine zones and use the most recent one
    all_zones = combine_nearby_zones(demand_zones + buy_liquidity)
    if not all_zones:
        print("No valid demand or buy liquidity zones available.")
        return
    
    recent_zone = max(all_zones, key=lambda z: z.timestamp)  # Most recent zone

    if ask_price > recent_zone.price:
        print(f"Current ask price {ask_price} is above the buy zone at {recent_zone.price}. Skipping trade.")
        return
    


    entry_price = ask_price  # Use current ask price
    sl_price = recent_zone.price - (ZONE_BUFFER_PIPS * point)
    tp_price = entry_price + ((entry_price - sl_price) * REWARD_RISK_RATIO)

    # Ensure no duplicate positions near the entry price
    if any(abs(pos.price_open - entry_price) < (5 * point) for pos in open_positions):
        print(f"Buy position already exists near the most recent zone at {recent_zone.price}.")
        return

    # Calculate position size
    volume = calculate_position_size(mt5, symbol, risk_percent=RISK_PERCENT, sl_pips=(entry_price - sl_price) / point)
    if volume <= 0:
        print("Position size calculation resulted in zero or negative volume.")
        return

    # Check margin requirements
    margin_needed = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, volume, entry_price)
    account_info = mt5.account_info()
    if not account_info or account_info.margin_free < margin_needed:
        print("Insufficient margin to open buy order.")
        return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_BUY,
        "price": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": f"Buy order at zone {recent_zone.type}",
        "type_time": mt5.ORDER_TIME_GTC
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to open buy order. Retcode: {result.retcode}")
    else:
        print(f"Buy order opened at {entry_price}. SL: {sl_price}, TP: {tp_price}, Volume: {volume}")

