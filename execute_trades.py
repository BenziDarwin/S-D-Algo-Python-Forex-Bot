def check_news_impact(mt5, symbol, impact_threshold_pips=50):
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
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, lookback + 14)  # Extra data for RSI
    if rates is None:
        print("Failed to get historical data")
        return "RANGING", 0
    
    import numpy as np
    import pandas as pd
    
    df = pd.DataFrame(rates)
    # Calculate EMAs
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
    
    # Calculate RSI with error handling
    delta = df['close'].diff()
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)
    
    # Calculate average gains and losses
    avg_gains = gains.rolling(window=14).mean()
    avg_losses = losses.rolling(window=14).mean()
    
    # Calculate RS with handling for zero division
    rs = avg_gains / avg_losses.replace(0, np.inf)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Handle any potential NaN values
    df['rsi'] = df['rsi'].fillna(50)
    
    # Calculate trend strength
    price_change = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0] * 100
    current_rsi = float(df['rsi'].iloc[-1])  # Convert to float to avoid comparison issues
    
    # Strong trend thresholds
    STRONG_TREND_THRESHOLD = 0.5  # 0.5% price change
    
    if df['ema20'].iloc[-1] > df['ema50'].iloc[-1]:
        strength = abs(price_change) if price_change > 0 else 0
        if current_rsi > 70:
            strength *= 0.5  # Reduce strength if potentially overbought
        return "BULLISH", strength
    elif df['ema20'].iloc[-1] < df['ema50'].iloc[-1]:
        strength = abs(price_change) if price_change < 0 else 0
        if current_rsi < 30:
            strength *= 0.5  # Reduce strength if potentially oversold
        return "BEARISH", strength
    else:
        return "RANGING", 0

def calculate_position_size(mt5, symbol, risk_percent=1.0, sl_pips=100):
    """
    Calculate position size based on account risk management
    """
    account_info = mt5.account_info()
    if account_info is None:
        return 0.01  # Minimum position size if we can't get account info
        
    point = mt5.symbol_info(symbol).point
    tick_value = mt5.symbol_info(symbol).trade_tick_value
    
    # Calculate risk amount in account currency
    risk_amount = account_info.balance * (risk_percent / 100)
    
    # Calculate position size based on risk
    sl_amount = sl_pips * point * (tick_value / point)
    position_size = risk_amount / sl_amount
    
    # Round down to nearest 0.01
    position_size = round(max(position_size, 0.01), 2)
    return position_size

def open_sell_positions(mt5, symbol, supply_zones, max_positions=5):
    # Check for high volatility/news impact first
    if check_news_impact(mt5, symbol):
        print("High volatility detected - avoiding new positions")
        return
    
    # Check market conditions
    market_condition, trend_strength = get_market_condition(mt5, symbol)
    
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_SELL]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("Failed to get current price")
        return
    bid_price = tick.bid
    
    # Determine if we should trade based on both trend and supply zones
    should_trade = False
    zone_price = None
    
    if market_condition == "BEARISH" and trend_strength > 0.5:
        # Strong bearish trend - we can trade even without supply zone
        should_trade = True
        zone_price = bid_price
    elif supply_zones and bid_price > supply_zones[-1][1]:
        # We have a valid supply zone entry
        should_trade = True
        zone_price = supply_zones[-1][1]
    
    if should_trade and not any(pos.price_open == bid_price for pos in open_positions):
        point = mt5.symbol_info(symbol).point
        
        # Dynamic SL based on trend strength
        sl_pips = max(100, int(100 * (1 + trend_strength)))
        sl_price = bid_price + sl_pips * point
        tp_price = bid_price - (sl_pips * 1.5) * point  # 1.5 risk:reward ratio
        
        # Calculate position size based on risk management
        volume = calculate_position_size(mt5, symbol, risk_percent=1.0, sl_pips=sl_pips)

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
            "magic": 234000,
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

def open_buy_positions(mt5, symbol, demand_zones, max_positions=5):
    # Check for high volatility/news impact first
    if check_news_impact(mt5, symbol):
        print("High volatility detected - avoiding new positions")
        return
    
    # Check market conditions
    market_condition, trend_strength = get_market_condition(mt5, symbol)
    
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_BUY]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("Failed to get current price")
        return
    ask_price = tick.ask
    
    # Determine if we should trade based on both trend and demand zones
    should_trade = False
    zone_price = None
    
    if market_condition == "BULLISH" and trend_strength > 0.5:
        # Strong bullish trend - we can trade even without demand zone
        should_trade = True
        zone_price = ask_price
    elif demand_zones and ask_price < demand_zones[-1][1]:
        # We have a valid demand zone entry
        should_trade = True
        zone_price = demand_zones[-1][1]
    
    if should_trade and not any(pos.price_open == ask_price for pos in open_positions):
        point = mt5.symbol_info(symbol).point
        
        # Dynamic SL based on trend strength
        sl_pips = max(100, int(100 * (1 + trend_strength)))
        sl_price = ask_price - sl_pips * point
        tp_price = ask_price + (sl_pips * 1.5) * point  # 1.5 risk:reward ratio
        
        # Calculate position size based on risk management
        volume = calculate_position_size(mt5, symbol, risk_percent=1.0, sl_pips=sl_pips)

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
            "magic": 234000,
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