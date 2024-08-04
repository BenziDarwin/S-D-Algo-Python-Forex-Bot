import MetaTrader5 as mt5

def open_sell_positions(symbol, supply_zones, max_positions=5):
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        return

    # Ensure only up to max_positions are open
    open_positions = [pos for pos in mt5.positions_get() if pos.symbol == symbol]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        mt5.shutdown()
        return

    # Open a sell position at each supply zone if not already opened
    for date,price in supply_zones:
        if not any(pos.symbol == symbol and pos.type == mt5.ORDER_SELL for pos in open_positions):
            # Create and send a sell order
            request = {
                "action": mt5.ORDER_BUY,  # Fixed to ORDER_SELL for selling
                "symbol": symbol,
                "volume": 0.1,  # Adjust volume as needed
                "price": price,
                "sl": price + 50 * mt5.symbol_info(symbol).point,  # Example SL
                "tp": price - 50 * mt5.symbol_info(symbol).point,  # Example TP
                "deviation": 10,
                "magic": 234000,
                "comment": "Sell order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to open sell order. Retcode: {result.retcode}")

    # Close profitable positions
    for pos in open_positions:
        if pos.type == mt5.ORDER_SELL and is_profitable(pos):
            close_position(pos)

    mt5.shutdown()

def open_buy_positions(symbol, demand_zones, max_positions=5):
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        return

    # Ensure only up to max_positions are open
    open_positions = [pos for pos in mt5.positions_get() if pos.symbol == symbol]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        mt5.shutdown()
        return

    # Open a buy position at each demand zone if not already opened
    for date,price in demand_zones:
        if not any(pos.symbol == symbol and pos.type == mt5.ORDER_BUY for pos in open_positions):
            # Create and send a buy order
            request = {
                "action": mt5.ORDER_SELL,  # Fixed to ORDER_BUY for buying
                "symbol": symbol,
                "volume": 0.1,  # Adjust volume as needed
                "price": price,
                "sl": price - 50 * mt5.symbol_info(symbol).point,  # Example SL
                "tp": price + 50 * mt5.symbol_info(symbol).point,  # Example TP
                "deviation": 10,
                "magic": 234000,
                "comment": "Buy order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to open buy order. Retcode: {result.retcode}")

    # Close profitable positions
    for pos in open_positions:
        if pos.type == mt5.ORDER_BUY and is_profitable(pos):
            close_position(pos)

    mt5.shutdown()

def is_profitable(position):
    symbol = position.symbol
    entry_price = position.price_open
    volume = position.volume
    # Get the current market price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get tick data for {symbol}")
        return False
    
    # Current price based on position type
    current_price = tick.bid if position.type == mt5.ORDER_BUY else tick.ask
    
    # Calculate profit
    point = mt5.symbol_info(symbol).point
    profit = (current_price - entry_price) * volume / point if position.type == mt5.ORDER_BUY else (entry_price - current_price) * volume / point
    
    # Check if profit is greater than 0
    return profit > 0

def close_position(position):
    # Close the given position
    request = {
        "action": mt5.ORDER_CLOSE,  # Correct action for closing
        "symbol": position.symbol,
        "volume": position.volume,
        "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_BUY else mt5.symbol_info_tick(position.symbol).ask,
        "deviation": 10,
        "magic": position.magic,
        "comment": "Closing profitable position",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close position. Retcode: {result.retcode}")

