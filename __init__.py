import time
import MetaTrader5 as mt5
import pandas as pd
from zones import find_zones
from execute_trades import open_sell_positions, open_buy_positions
from mock_execute_trades import mock_open_sell_positions, mock_open_buy_positions

MODE = 'live'

def main():
    if not mt5.initialize():
        print("initialize() failed")
        mt5.shutdown()
        return
        
    # Replace with your login credentials
    account = 48688301
    password = "Homethe06!"
    server = "HFMarketsGlobal-Demo"

    authorized = mt5.login(account, password=password, server=server)
    if not authorized:
        print(f"Failed to connect at account #{account}, error code: {mt5.last_error()}")
        mt5.shutdown()
        return
        
    print(f"Connected to account #{account}")

    # Set the symbol and timeframe
    symbol = "EURUSD"
    timeframe = mt5.TIMEFRAME_M15  # Hourly data


    if MODE == 'live':
        try:
            while True:
                # Define the time range for fetching historical data
                end_date = pd.Timestamp.now()
                start_date = end_date - pd.DateOffset(days=30)  # Adjust as needed

                # Fetch historical data
                rates = mt5.copy_rates_range(symbol, timeframe, start_date.to_pydatetime(), end_date.to_pydatetime())
                if rates is None:
                    print(f"Failed to get rates for {symbol}, error code: {mt5.last_error()}")
                    time.sleep(300)  # Wait before retrying
                    continue

                # Create DataFrame
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)

                # Find supply and demand zones
                supply_zones, demand_zones = find_zones(df)

                print("Processing live data...")

                # Execute live trades
                open_sell_positions(mt5, symbol, supply_zones)
                open_buy_positions(mt5, symbol, demand_zones)

            
                # Wait for 10 seconds before checking again
                time.sleep(10)
        finally:
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
