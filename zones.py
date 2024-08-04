from typing import Tuple, List
import pandas as pd

def isSupport(df: pd.DataFrame, i: int) -> bool:
    support = (df['low'][i] < df['low'][i-1] and df['low'][i] < df['low'][i+1] and
               df['low'][i+1] < df['low'][i+2] and df['low'][i-1] < df['low'][i-2])
    return support

def isResistance(df: pd.DataFrame, i: int) -> bool:
    resistance = (df['high'][i] > df['high'][i-1] and df['high'][i] > df['high'][i+1] and
                  df['high'][i+1] > df['high'][i+2] and df['high'][i-1] > df['high'][i-2])
    return resistance

def find_zones(df: pd.DataFrame) -> Tuple[List[Tuple[pd.Timestamp, float]], List[Tuple[pd.Timestamp, float]]]:
    supply_zones = []
    demand_zones = []
    
    for i in range(2, len(df) - 2):  # Ensure enough data around the current index
        if isSupport(df, i):
            demand_zones.append((df.index[i], df['low'][i]))
        if isResistance(df, i):
            supply_zones.append((df.index[i], df['high'][i]))
            
    return supply_zones, demand_zones
