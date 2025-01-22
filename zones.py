from typing import Tuple, List, NamedTuple
import pandas as pd
import numpy as np

class Zone(NamedTuple):
    timestamp: pd.Timestamp
    price: float
    strength: float
    tick_volume: float
    type: str

def isSupport(df: pd.DataFrame, i: int) -> bool:
    support = (df['low'][i] < df['low'][i-1] and df['low'][i] < df['low'][i+1] and
               df['low'][i+1] < df['low'][i+2] and df['low'][i-1] < df['low'][i-2])
    return support

def isResistance(df: pd.DataFrame, i: int) -> bool:
    resistance = (df['high'][i] > df['high'][i-1] and df['high'][i] > df['high'][i+1] and
                  df['high'][i+1] > df['high'][i+2] and df['high'][i-1] > df['high'][i-2])
    return resistance

def identify_liquidity_zones(df: pd.DataFrame, 
                           volume_threshold: float = 0.75,
                           swing_length: int = 5,
                           consolidation_threshold: float = 0.0002) -> Tuple[List[Zone], List[Zone]]:
    """
    Identify potential liquidity zones based on tick_volume clusters and price action.
    
    Args:
        df: DataFrame with OHLCV data
        volume_threshold: Percentile threshold for high tick_volume (0-1)
        swing_length: Number of bars to look back for swing points
        consolidation_threshold: Maximum price range for consolidation as percentage
    
    Returns:
        Tuple of buy and sell liquidity zones
    """
    buy_liquidity = []
    sell_liquidity = []
    
    # Calculate tick_volume metrics
    df['volume_ma'] = df['tick_volume'].rolling(20).mean()
    high_volume_threshold = df['tick_volume'].quantile(volume_threshold)
    
    # Calculate price volatility
    df['atr'] = calculate_atr(df, 14)
    
    for i in range(swing_length, len(df) - swing_length):
        # Skip if tick_volume is too low
        if df['tick_volume'][i] < high_volume_threshold:
            continue
            
        price_range = (df['high'][i] - df['low'][i]) / df['low'][i]
        if price_range > consolidation_threshold:
            continue
            
        # Check for tick_volume cluster
        volume_cluster = df['tick_volume'][i] > df['volume_ma'][i] * 1.5
        
        # Calculate zone strength based on tick_volume and price action
        volume_strength = df['tick_volume'][i] / df['volume_ma'][i]
        
        # Look for potential buy liquidity (stops below lows)
        if is_swing_low(df, i, swing_length) and volume_cluster:
            zone_strength = calculate_zone_strength(df, i, volume_strength, 'buy')
            buy_liquidity.append(Zone(
                timestamp=df.index[i],
                price=df['low'][i],
                strength=zone_strength,
                tick_volume=df['tick_volume'][i],
                type='buy_liquidity'
            ))
        
        # Look for potential sell liquidity (stops above highs)
        if is_swing_high(df, i, swing_length) and volume_cluster:
            zone_strength = calculate_zone_strength(df, i, volume_strength, 'sell')
            sell_liquidity.append(Zone(
                timestamp=df.index[i],
                price=df['high'][i],
                strength=zone_strength,
                tick_volume=df['tick_volume'][i],
                type='sell_liquidity'
            ))
    
    return buy_liquidity, sell_liquidity

def calculate_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Calculate Average True Range"""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    return true_range.rolling(period).mean()

def is_swing_low(df: pd.DataFrame, i: int, length: int) -> bool:
    """Check if current bar is a swing low"""
    return all(df['low'][i] <= df['low'][j] for j in range(i-length, i+length+1) if j != i)

def is_swing_high(df: pd.DataFrame, i: int, length: int) -> bool:
    """Check if current bar is a swing high"""
    return all(df['high'][i] >= df['high'][j] for j in range(i-length, i+length+1) if j != i)

def calculate_zone_strength(df: pd.DataFrame, i: int, volume_strength: float, zone_type: str) -> float:
    """Calculate the strength of a liquidity zone based on multiple factors"""
    # Base strength from tick_volume
    strength = volume_strength
    
    # Add strength based on previous attempts to break the level
    if zone_type == 'buy':
        touches = sum(1 for j in range(max(0, i-20), i) 
                     if abs(df['low'][j] - df['low'][i]) < df['atr'][i] * 0.5)
    else:
        touches = sum(1 for j in range(max(0, i-20), i) 
                     if abs(df['high'][j] - df['high'][i]) < df['atr'][i] * 0.5)
    
    strength *= (1 + touches * 0.2)  # Increase strength by 20% for each touch
    
    # Add strength if there's a clean break and return
    if zone_type == 'buy':
        clean_break = df['low'][i:i+5].min() > df['low'][i]
    else:
        clean_break = df['high'][i:i+5].max() < df['high'][i]
    
    if clean_break:
        strength *= 1.5
    
    return min(strength, 10.0)  # Cap strength at 10

def find_all_zones(df: pd.DataFrame, 
                   volume_threshold: float = 0.75,
                   swing_length: int = 5) -> Tuple[List[Zone], List[Zone], List[Zone], List[Zone]]:
    """
    Combine supply/demand zones with liquidity zones
    
    Returns:
        Tuple of (supply_zones, demand_zones, buy_liquidity, sell_liquidity)
    """
    # Find traditional supply/demand zones
    supply_zones = []
    demand_zones = []
    
    for i in range(2, len(df) - 2):
        if isSupport(df, i):
            demand_zones.append(Zone(
                timestamp=df.index[i],
                price=df['low'][i],
                strength=1.0,  # Base strength for traditional zones
                tick_volume=df['tick_volume'][i],
                type='demand'
            ))
        if isResistance(df, i):
            supply_zones.append(Zone(
                timestamp=df.index[i],
                price=df['high'][i],
                strength=1.0,  # Base strength for traditional zones
                tick_volume=df['tick_volume'][i],
                type='supply'
            ))
    
    # Find liquidity zones
    buy_liquidity, sell_liquidity = identify_liquidity_zones(
        df, volume_threshold, swing_length
    )
    
    return supply_zones, demand_zones, buy_liquidity, sell_liquidity

def combine_nearby_zones(zones: List[Zone], 
                        price_threshold: float = 0.0002) -> List[Zone]:
    """Combine zones that are very close to each other"""
    if not zones:
        return zones
    
    # Sort zones by price
    sorted_zones = sorted(zones, key=lambda x: x.price)
    combined = []
    current_zone = sorted_zones[0]
    
    for zone in sorted_zones[1:]:
        # If zones are close enough, combine them
        if abs(zone.price - current_zone.price) / current_zone.price < price_threshold:
            # Create new combined zone with weighted average price and max strength
            new_strength = max(zone.strength, current_zone.strength)
            new_volume = max(zone.tick_volume, current_zone.tick_volume)
            new_price = (zone.price * zone.tick_volume + current_zone.price * current_zone.tick_volume) / (zone.tick_volume + current_zone.tick_volume)
            
            current_zone = Zone(
                timestamp=max(zone.timestamp, current_zone.timestamp),
                price=new_price,
                strength=new_strength,
                tick_volume=new_volume,
                type=current_zone.type
            )
        else:
            combined.append(current_zone)
            current_zone = zone
    
    combined.append(current_zone)
    return combined