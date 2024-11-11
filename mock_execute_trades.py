import secrets

# Mock Data Structures
class MockPosition:
    def __init__(self, symbol, position_type, price_open, volume):
        self.symbol = symbol
        self.type = position_type
        self.price_open = price_open
        self.volume = volume

# Mock Globals
open_positions = []
max_positions = 5
balance = 10000  # Example initial balance

def mock_initialize():
    # Simulate successful initialization
    return True

def mock_shutdown():
    # Simulate shutdown
    pass

def mock_positions_get():
    return open_positions

def mock_order_send(request):
    # Simulate order sending
    print(f"Order request: {request}")
    return {"retcode": secrets.choice([0])}  # 0 for success, 1 for failure

def mock_symbol_info(symbol):
    # Simulate symbol info
    return {"point": 0.0001}  # Example point value

def mock_symbol_info_tick(symbol):
    # Simulate tick info
    return {"bid": secrets.SystemRandom().uniform(1.0, 1.5), "ask": secrets.SystemRandom().uniform(1.0, 1.5)}

def mock_open_sell_positions(symbol, supply_zones, max_positions=5):
    global balance
    if not mock_initialize():
        print("initialize() failed")
        mock_shutdown()
        return

    # Ensure only up to max_positions are open
    if len([pos for pos in mock_positions_get() if pos.symbol == symbol]) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        mock_shutdown()
        return

    # Open a sell position at each supply zone if not already opened

    for date,price in supply_zones:
        if not any(pos.symbol == symbol and pos.type == 'sell' for pos in open_positions):
            # Create and send a sell order
            point = mock_symbol_info(symbol)["point"]  # Get point value
            request = {
                "action": 'sell',
                "symbol": symbol,
                "volume": 0.1,  # Adjust volume as needed
                "price": price,
                "sl": price + 50 * point,  # Example SL
                "tp": price - 50 * point,  # Example TP
                "deviation": 10,
                "magic": 234000,
                "comment": "Sell order",
                "type_time": 'GTC',
                "type_filling": 'IOC'
            }
            result = mock_order_send(request)
            if result["retcode"] == 0:
                # Position opened successfully
                open_positions.append(MockPosition(symbol, 'sell', price, 0.1))
                print(f"Opened sell position at {price}")
            else:
                print(f"Failed to open sell order. Retcode: {result['retcode']}")

    # Close profitable positions
    for pos in open_positions:
        if pos.symbol == symbol and pos.type == 'sell' and is_profitable(pos):
            mock_close_position(pos)

    mock_shutdown()
    return balance

def mock_open_buy_positions(symbol, demand_zones, max_positions=5):
    global balance
    if not mock_initialize():
        print("initialize() failed")
        mock_shutdown()
        return

    # Ensure only up to max_positions are open
    if len([pos for pos in mock_positions_get() if pos.symbol == symbol]) >= max_positions:
        print(f"Maximum of {max_positions} positions already open.")
        mock_shutdown()
        return

    # Open a buy position at each demand zone if not already opened
    for date,price in demand_zones:
        if not any(pos.symbol == symbol and pos.type == 'buy' for pos in open_positions):
            # Create and send a buy order
            point = mock_symbol_info(symbol)["point"]  # Get point value
            request = {
                "action": 'buy',
                "symbol": symbol,
                "volume": 0.1,  # Adjust volume as needed
                "price": price,
                "sl": price - 50 * point,  # Example SL
                "tp": price + 50 * point,  # Example TP
                "deviation": 10,
                "magic": 234000,
                "comment": "Buy order",
                "type_time": 'GTC',
                "type_filling": 'IOC'
            }
            result = mock_order_send(request)
            if result["retcode"] == 0:
                # Position opened successfully
                open_positions.append(MockPosition(symbol, 'buy', price, 0.1))
                print(f"Opened buy position at {price}")
            else:
                print(f"Failed to open buy order. Retcode: {result['retcode']}")

    # Close profitable positions
    for pos in open_positions:
        if pos.symbol == symbol and pos.type == 'buy' and is_profitable(pos):
            mock_close_position(pos)

    mock_shutdown()
    return balance

def is_profitable(position):
    symbol = position.symbol
    entry_price = position.price_open
    volume = position.volume
    # Get the current market price
    tick = mock_symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get tick data for {symbol}")
        return False
    
    # Current price based on position type
    current_price = tick["bid"] if position.type == 'buy' else tick["ask"]
    
    # Calculate profit
    point = mock_symbol_info(symbol)["point"]
    profit = (current_price - entry_price) * volume / point if position.type == 'buy' else (entry_price - current_price) * volume / point
    
    # Update balance if profitable
    global balance
    if profit > 0:
        balance += profit
        print(f"Position closed profitably. Profit: {profit}, New Balance: {balance}")
    
    # Check if profit is greater than 0
    return profit > 0

def mock_close_position(position):
    # Close the given position
    request = {
        "action": 'close',
        "symbol": position.symbol,
        "volume": position.volume,
        "price": mock_symbol_info_tick(position.symbol)["bid"] if position.type == 'buy' else mock_symbol_info_tick(position.symbol)["ask"],
        "deviation": 10,
        "magic": 234000,
        "comment": "Closing profitable position",
        "type_time": 'GTC',
        "type_filling": 'IOC'
    }
    result = mock_order_send(request)
    if result["retcode"] == 0:
        # Successfully closed position
        print(f"Closed position for {position.symbol} at {request['price']}")
    else:
        print(f"Failed to close position. Retcode: {result['retcode']}")
