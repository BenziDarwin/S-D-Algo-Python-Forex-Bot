def open_sell_positions(mt5, symbol, supply_zones, max_positions=5):
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_SELL]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    # Use only the most recent supply zone
    if supply_zones:
        date, price = supply_zones[-1]
        if not any(pos.price_open == price for pos in open_positions):
            point = mt5.symbol_info(symbol).point  # Get point value
            bid_price = mt5.symbol_info_tick(symbol).bid  # Use current bid price for sell
            sl_price = bid_price + 100 * point  # Example SL
            tp_price = bid_price - 100 * point  # Example TP

            # Check if there are enough funds for this trade
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
                "volume": 0.01,  # Adjust volume as needed
                "type": mt5.ORDER_TYPE_SELL,
                "price": bid_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 10,
                "magic": 234000,
                "comment": "Sell order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to open sell order. Retcode: {result.retcode}")
            print(f"Opened sell order at {bid_price}")

    # Close profitable positions
    for pos in open_positions:
        if is_profitable(mt5, pos):
            close_position(mt5, pos)


def open_buy_positions(mt5, symbol, demand_zones, max_positions=5):
    # Ensure only up to max_positions are open
    open_positions = [pos for pos in list(mt5.positions_get(symbol=symbol)) if pos.type == mt5.ORDER_TYPE_BUY]
    if len(open_positions) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        return

    # Use only the most recent demand zone
    if demand_zones:
        date, price = demand_zones[-1]
        if not any(pos.price_open == price for pos in open_positions):
            point = mt5.symbol_info(symbol).point  # Get point value
            ask_price = mt5.symbol_info_tick(symbol).ask  # Use current ask price for buy
            sl_price = ask_price - 100 * point  # Example SL
            tp_price = ask_price + 100 * point  # Example TP

            # Check if there are enough funds for this trade
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
                "volume": 0.01,  # Adjust volume as needed
                "type": mt5.ORDER_TYPE_BUY,
                "price": ask_price,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 10,
                "magic": 234000,
                "comment": "Buy order",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"Failed to open buy order. Retcode: {result.retcode}")
            print(f"Opened buy order at {ask_price}")

    # Close profitable positions
    for pos in open_positions:
        if is_profitable(mt5, pos):
            close_position(mt5, pos)

def is_profitable(mt5, position):
    symbol = position.symbol
    entry_price = position.price_open
    volume = position.volume
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get tick data for {symbol}")
        return False
    
    current_price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
    point = mt5.symbol_info(symbol).point
    profit = (current_price - entry_price) * volume / point if position.type == mt5.ORDER_TYPE_BUY else (entry_price - current_price) * volume / point
    return profit > 0

def close_position(mt5, position):
    price = mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
        "position": position.ticket,
        "price": price,
        "deviation": 10,
        "magic": 234000,
        "comment": "Closing profitable position",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Failed to close position. Retcode: {result.retcode}")
