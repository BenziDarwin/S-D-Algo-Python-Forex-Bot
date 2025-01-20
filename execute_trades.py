import MetaTrader5 as mt

def calculate_trend(mt5, symbol, timeframe=mt.TIMEFRAME_H4, period=20):
    """
    Calculate trend direction using EMA
    Returns: 1 for bullish, -1 for bearish, 0 for neutral/sideways
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 1)
    if rates is None or len(rates) < period:
        print("Failed to get price data for trend calculation")
        return 0
    
    # Calculate EMA
    close_prices = rates['close']
    multiplier = 2 / (period + 1)
    ema = close_prices[0]
    for price in close_prices[1:]:
        ema = price * multiplier + ema * (1 - multiplier)
    
    current_price = close_prices[-1]
    price_change = (current_price - close_prices[-2]) / close_prices[-2] * 100
    
    # Determine trend strength
    if current_price > ema and price_change > 0.1:
        return 1  # Strong bullish
    elif current_price < ema and price_change < -0.1:
        return -1  # Strong bearish
    return 0  # Neutral/sideways

def open_sell_positions(mt5, symbol, supply_zones, max_positions=5):
    trend = calculate_trend(mt5, symbol)
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_SELL]
    
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    if trend == 1:  # Strong bullish trend
        print("Avoiding sell positions during strong bullish trend")
        return
        
    # Use only the most recent supply zone
    if supply_zones:
        date, zone_price = supply_zones[-1]
        bid_price = mt5.symbol_info_tick(symbol).bid
        
        # Modify entry conditions based on trend
        enter_trade = False
        if trend == -1:  # Bearish trend
            # More aggressive entry during bearish trend
            enter_trade = bid_price > (zone_price * 0.997)  # Allow entry slightly below supply zone
        else:  # Neutral trend
            # Standard supply zone entry
            enter_trade = bid_price > zone_price

        if enter_trade and not any(pos.price_open == bid_price for pos in open_positions):
            point = mt5.symbol_info(symbol).point
            
            # Adjust stop loss and take profit based on trend
            if trend == -1:
                sl_price = bid_price + 80 * point  # Tighter stop loss in bearish trend
                tp_price = bid_price - 150 * point  # Larger take profit target
            else:
                sl_price = bid_price + 100 * point
                tp_price = bid_price - 100 * point

            # Check if there are enough funds
            account_info = mt5.account_info()
            if account_info is None:
                print("Failed to get account info.")
                return

            margin_needed = mt5.order_calc_margin(mt5.ORDER_TYPE_SELL, symbol, 0.01, bid_price)
            if margin_needed is None or account_info.margin_free < margin_needed:
                print("Not enough money to open sell order.")
                return

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": 0.01,
                "type": mt5.ORDER_TYPE_SELL,
                "price": bid_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 10,
                "magic": 234000,
                "comment": f"Sell order",
                "type_time": mt5.ORDER_TIME_GTC,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to open sell order. Retcode: {result.retcode}")
            else:
                print(f"Opened sell order at {bid_price} (Price entered supply zone at {zone_price}, Trend: {trend})")
        else:
            print(f"Waiting for appropriate entry conditions (Bid: {bid_price}, Supply: {zone_price}, Trend: {trend})")

def open_buy_positions(mt5, symbol, demand_zones, max_positions=5):
    trend = calculate_trend(mt5, symbol)
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_BUY]
    
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    if trend == -1:  # Strong bearish trend
        print("Avoiding buy positions during strong bearish trend")
        return
        
    # Use only the most recent demand zone
    if demand_zones:
        date, zone_price = demand_zones[-1]
        ask_price = mt5.symbol_info_tick(symbol).ask
        
        # Modify entry conditions based on trend
        enter_trade = False
        if trend == 1:  # Bullish trend
            # More aggressive entry during bullish trend
            enter_trade = ask_price < (zone_price * 1.003)  # Allow entry slightly above demand zone
        else:  # Neutral trend
            # Standard demand zone entry
            enter_trade = ask_price < zone_price

        if enter_trade and not any(pos.price_open == ask_price for pos in open_positions):
            point = mt5.symbol_info(symbol).point
            
            # Adjust stop loss and take profit based on trend
            if trend == 1:
                sl_price = ask_price - 80 * point  # Tighter stop loss in bullish trend
                tp_price = ask_price + 150 * point  # Larger take profit target
            else:
                sl_price = ask_price - 100 * point
                tp_price = ask_price + 100 * point

            # Check if there are enough funds
            account_info = mt5.account_info()
            if account_info is None:
                print("Failed to get account info.")
                return

            margin_needed = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, symbol, 0.01, ask_price)
            if margin_needed is None or account_info.margin_free < margin_needed:
                print("Not enough money to open buy order.")
                return

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": 0.01,
                "type": mt5.ORDER_TYPE_BUY,
                "price": ask_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 10,
                "magic": 234000,
                "comment": f"Buy order",
                "type_time": mt5.ORDER_TIME_GTC,
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to open buy order. Retcode: {result.retcode}")
            else:
                print(f"Opened buy order at {ask_price} (Price entered demand zone at {zone_price}, Trend: {trend})")
        else:
            print(f"Waiting for appropriate entry conditions (Ask: {ask_price}, Demand: {zone_price}, Trend: {trend})")