import time
import MetaTrader5 as mt5
import pandas as pd
from zones import find_zones
from execute_trades import open_sell_positions, open_buy_positions
from mock_execute_trades import mock_open_sell_positions, mock_open_buy_positions
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Choose mode: 'live' or 'mock'
MODE = 'mock'  # Set to 'mock' for mock trading

def main():
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        return
        
    # Replace with your login credentials
    account = 179389112
    password = "PheroriaZero0"
    server = "Exness-MT5Trial9"

    authorized = mt5.login(account, password=password, server=server)
    if not authorized:
        print(f"Failed to connect at account #{account}, error code: {mt5.last_error()}")
        mt5.shutdown()
        return
        
    print(f"Connected to account #{account}")

    # Set the symbol and timeframe
    symbol = "EURUSDm"
    timeframe = mt5.TIMEFRAME_H1  # Hourly data

    if MODE == 'live':  
        start_date = pd.Timestamp('2024-01-01')
        end_date = pd.Timestamp.now()
        # Fetch historical data
        rates = mt5.copy_rates_range(symbol, timeframe, start_date.to_pydatetime(), end_date.to_pydatetime())
        
        if rates is None:
            print(f"Failed to get rates for {symbol}, error code: {mt5.last_error()}")
            mt5.shutdown()
            return
      
        # Create DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Find supply and demand zones
        supply_zones, demand_zones = find_zones(df)
        
        # Execute live trades
        open_sell_positions(symbol, supply_zones)
        open_buy_positions(symbol, demand_zones)
        
        # Shutdown MT5
        mt5.shutdown()

    elif MODE == 'mock':
        # Mock trading setup
        global open_positions, balance
        open_positions = []  # Clear mock positions
        balance = 10000  # Reset balance

        # Set the symbol and timeframe for mock testing
        start_date = pd.Timestamp('2023-01-01')
        end_date = pd.Timestamp('2023-12-31')

        # Fetch historical data
        rates = mt5.copy_rates_range(symbol, timeframe, start_date.to_pydatetime(), end_date.to_pydatetime())
        
        if rates is None:
            print(f"Failed to get rates for {symbol}, error code: {mt5.last_error()}")
            mt5.shutdown()
            return
      
        # Create DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)

        # Find supply and demand zones
        supply_zones, demand_zones = find_zones(df)
        
        # Loop through each row of the DataFrame
        for index, row in df.iterrows():
            current_price = row['close']
            print(f"Processing date: {index}, Price: {current_price}, Balance: {balance}")

            # Execute mock trades
            print(mock_open_sell_positions(symbol, supply_zones))
            print(mock_open_buy_positions(symbol, demand_zones))

            # Pause for a short duration to simulate trading time
            time.sleep(1)

            # Optionally, you can simulate more actions here


if __name__ == "__main__":
    main()