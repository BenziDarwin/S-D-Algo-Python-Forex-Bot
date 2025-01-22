import numpy as np
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

# Validate and get environment variables
def get_env_var(var_name, var_type, default_value=None):
    """Retrieve and validate environment variable."""
    value = os.getenv(var_name, default_value)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is missing.")
    
    try:
        return var_type(value)
    except ValueError:
        raise ValueError(f"Environment variable '{var_name}' must be of type {var_type.__name__}. Got: {value}")

# Get configurable variables
RISK_PERCENT = get_env_var('RISK_PERCENT', float)
SL_PIPS = get_env_var('SL_PIPS', int)
IMPACT_THRESHOLD_PIPS = get_env_var('IMPACT_THRESHOLD_PIPS', int)
STRONG_TREND_THRESHOLD = get_env_var('STRONG_TREND_THRESHOLD', float)
MAX_POSITIONS = get_env_var('MAX_POSITIONS', int)
MAGIC_NUMBER = get_env_var('MAGIC_NUMBER', int)
MIN_POSITION_SIZE = get_env_var('MIN_POSITION_SIZE', float)
REWARD_RISK_RATIO = get_env_var('REWARD_RISK_RATIO', float)


def check_news_impact(mt5, symbol, impact_threshold_pips=IMPACT_THRESHOLD_PIPS):
    """
    Check for unusual price movements that might indicate news impact
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 2)
    if rates is None:
        return True  # Assume high volatility if we can't get data
        
    price_change = abs(rates[-1]['close'] - rates[-1]['open'])
    point = mt5.symbol_info(symbol).point
    price_change_pips = price_change / point
    
    return price_change_pips > impact_threshold_pips

def get_market_condition(mt5, symbol, period=15, lookback=20):
    """
    Determine if market is bullish, bearish, or ranging using EMA and RSI
    Returns: (condition, strength)
    """
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, lookback + 14)
    if rates is None:
        print("Failed to get historical data")
        return "RANGING", 0
    
    df = pd.DataFrame(rates)
    # Calculate EMAs
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Calculate RSI
    delta = df['close'].diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    
    avg_gains = gains.rolling(window=14).mean()
    avg_losses = losses.rolling(window=14).mean()
    
    rs = avg_gains / avg_losses.replace(0, np.inf)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi'] = df['rsi'].fillna(50)
    
    # Calculate trend strength using both price action and EMAs
    price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
    ema_spread = ((df['ema20'].iloc[-1] - df['ema50'].iloc[-1]) / df['ema50'].iloc[-1]) * 100
    current_rsi = float(df['rsi'].iloc[-1])
    
    # Check EMA crossover and direction
    ema_bullish = df['ema20'].iloc[-1] > df['ema50'].iloc[-1] and price_change > 0
    ema_bearish = df['ema20'].iloc[-1] < df['ema50'].iloc[-1] and price_change < 0
    
    price_volatility = df['close'].std() / df['close'].mean()
    is_choppy = abs(ema_spread) < 0.1  # EMAs are very close together
    
    # Modified condition check
    if ema_bullish and not is_choppy:
        if current_rsi > 70:
            strength *= 0.5
        return "BULLISH", strength
    elif ema_bearish and not is_choppy:
        if current_rsi < 30:
            strength *= 0.5
        return "BEARISH", strength
    else:
        # Calculate ranging strength based on volatility
        ranging_strength = min(price_volatility * 100, 1.0)
        return "RANGING", ranging_strength


def calculate_position_size(mt5, symbol, risk_percent=RISK_PERCENT, sl_pips=SL_PIPS):
    """
    Calculate position size based on account risk management
    """
    account_info = mt5.account_info()
    if account_info is None:
        return MIN_POSITION_SIZE  # Minimum position size if we can't get account info
        
    point = mt5.symbol_info(symbol).point
    tick_value = mt5.symbol_info(symbol).trade_tick_value
    
    # Calculate risk amount in account currency
    risk_amount = account_info.balance * (risk_percent / 100)
    
    # Calculate position size based on risk
    sl_amount = sl_pips * point * (tick_value / point)
    position_size = risk_amount / sl_amount
    
    # Round down to nearest 0.05
    position_size = round(max(position_size, MIN_POSITION_SIZE), 2)
    return position_size

def open_sell_positions(mt5, symbol, supply_zones, max_positions=MAX_POSITIONS):
    if check_news_impact(mt5, symbol):
        print("High volatility detected - avoiding new positions")
        return
    
    market_condition, trend_strength = get_market_condition(mt5, symbol)
    
    # Don't open sell positions in bullish market
    if market_condition == "BULLISH":
        print(f"Avoiding sell positions in {market_condition} market")
        return
    
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_SELL]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("Failed to get current price")
        return
    bid_price = tick.bid
    
    # Only trade if we have a bearish trend or valid supply zone
    should_trade = False

    trend_threshold = STRONG_TREND_THRESHOLD * 0.6 if market_condition == "BEARISH" else STRONG_TREND_THRESHOLD
    
    zone_distance = abs(bid_price - supply_zones[-1][1]) / mt5.symbol_info(symbol).point
    if market_condition == "BEARISH" and trend_strength > trend_threshold:
        should_trade = True
        zone_price = bid_price

    elif market_condition == "RANGING":
        if zone_distance > IMPACT_THRESHOLD_PIPS * 1.5:
            should_trade = True
            zone_price = supply_zones[-1][1]
            print(f"Opening sell position in ranging market - supply zone found at distance: {zone_distance:.1f} pips")
        else:
            print(f"Ranging market - supply zone too close at {zone_distance:.1f} pips")

    
    if should_trade and not any(pos.price_open == bid_price for pos in open_positions):
        point = mt5.symbol_info(symbol).point
        
        # Dynamic SL based on trend strength
        sl_pips = max(100, int(100 * (1 + trend_strength)))
        sl_price = bid_price + sl_pips * point
        tp_price = bid_price - (sl_pips * REWARD_RISK_RATIO) * point  # 1.3 risk:reward ratio
        
        # Calculate position size based on risk management
        volume = calculate_position_size(mt5, symbol, risk_percent=RISK_PERCENT, sl_pips=sl_pips)

        # Check if there are enough funds
        margin_needed = mt5.order_calc_margin(mt5.ORDER_TYPE_SELL, symbol, volume, bid_price)
        account_info = mt5.account_info()
        if margin_needed is None or account_info.margin_free < margin_needed:
            print("Not enough money to open sell order.")
            return

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL,
            "price": bid_price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 10,
            "magic": MAGIC_NUMBER,
            "comment": f"Sell order - {market_condition} market",
            "type_time": mt5.ORDER_TIME_GTC
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to open sell order. Retcode: {result.retcode}")
        else:
            print(f"Opened sell order at {bid_price} ({market_condition} market, strength: {trend_strength:.2f})")
    else:
        print(f"Waiting for better sell conditions. Market: {market_condition}, Strength: {trend_strength:.2f}")

def open_buy_positions(mt5, symbol, demand_zones, max_positions=MAX_POSITIONS):
    if check_news_impact(mt5, symbol):
        print("High volatility detected - avoiding new positions")
        return
    
    market_condition, trend_strength = get_market_condition(mt5, symbol)
    
    # Don't open buy positions in bearish market
    if market_condition == "BEARISH":
        print(f"Avoiding buy positions in {market_condition} market")
        return
    
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_BUY]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("Failed to get current price")
        return
    ask_price = tick.ask
    
    # Only trade if we have a bullish trend or valid demand zone
    should_trade = False
    
    trend_threshold = STRONG_TREND_THRESHOLD * 0.6 if market_condition == "BULLISH" else STRONG_TREND_THRESHOLD
    zone_distance = abs(ask_price - demand_zones[-1][1]) / mt5.symbol_info(symbol).point

    if market_condition == "BULLISH" and trend_strength > trend_threshold:
        should_trade = True
        zone_price = ask_price
    
    elif market_condition == "RANGING":
        if zone_distance > IMPACT_THRESHOLD_PIPS * 1.5:
            should_trade = True
            zone_price = demand_zones[-1][1]
            print(f"Opening buy position in ranging market - demand zone found at distance: {zone_distance:.1f} pips")
        else:
            print(f"Ranging market - demand zone too close at {zone_distance:.1f} pips")
    
    if should_trade and not any(pos.price_open == ask_price for pos in open_positions):
        point = mt5.symbol_info(symbol).point
        
        # Dynamic SL based on trend strength
        sl_pips = max(100, int(100 * (1 + trend_strength)))
        sl_price = ask_price - sl_pips * point
        tp_price = ask_price + (sl_pips * REWARD_RISK_RATIO) * point  # 1.3 risk:reward ratio
        
        # Calculate position size based on risk management
        volume = calculate_position_size(mt5, symbol, risk_percent=RISK_PERCENT, sl_pips=sl_pips)

        # Check if there are enough funds
        margin_needed = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, volume, ask_price)
        account_info = mt5.account_info()
        if margin_needed is None or account_info.margin_free < margin_needed:
            print("Not enough money to open buy order.")
            return

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY,
            "price": ask_price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 10,
            "magic": MAGIC_NUMBER,
            "comment": f"Buy order - {market_condition} market",
            "type_time": mt5.ORDER_TIME_GTC
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to open buy order. Retcode: {result.retcode}")
        else:
            print(f"Opened buy order at {ask_price} ({market_condition} market, strength: {trend_strength:.2f})")
    else:
        print(f"Waiting for better buy conditions. Market: {market_condition}, Strength: {trend_strength:.2f}")