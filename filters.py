#!/usr/bin/env python3
"""
Stock filtering for CRSP US Total Market Index approximation
"""

import requests
import os
from pathlib import Path

# Load environment
def load_env():
    env_path = Path(__file__).parent / '.env'
    if not env_path.exists():
        return
    
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

load_env()
FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY')

def get_stock_profile(symbol):
    """Get stock profile data from Finnhub"""
    try:
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={FINNHUB_KEY}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return {}

def is_major_exchange_stock(symbol, earnings_data=None):
    """
    Check if stock is listed on major US exchanges
    
    Criteria:
    - NYSE (New York Stock Exchange)
    - NYSE Market (NYSE American)  
    - NASDAQ
    - ARCA (NYSE Arca)
    """
    
    # Get profile data for exchange info
    profile = get_stock_profile(symbol)
    if not profile:
        return False, "No profile data"
    
    # Check exchange
    exchange = profile.get('exchange', '').upper()
    
    # Major US exchanges
    major_exchanges = [
        'NYSE', 'NEW YORK STOCK EXCHANGE',
        'NASDAQ', 'GLOBAL MARKET', 
        'ARCA', 'NYSE ARCA',
        'NYSE AMERICAN', 'NYSE MKT'
    ]
    
    if any(ex in exchange for ex in major_exchanges):
        return True, f"Major exchange: {exchange}"
    else:
        return False, f"Not major exchange: {exchange}"

def filter_earnings_for_major_exchanges(earnings_list):
    """Filter earnings list to only include major US exchange stocks"""
    
    eligible = []
    stats = {'total': len(earnings_list), 'eligible': 0, 'excluded': 0}
    
    for earning in earnings_list:
        symbol = earning.get('symbol', '')
        
        # Skip if no EPS estimate or actual (probably not a real earnings report)
        if not earning.get('epsEstimate') and not earning.get('epsActual'):
            stats['excluded'] += 1
            continue
            
        is_eligible, reason = is_major_exchange_stock(symbol, earning)
        
        if is_eligible:
            eligible.append(earning)
            stats['eligible'] += 1
            print(f"✅ {symbol:6s}: {reason}")
        else:
            stats['excluded'] += 1
            print(f"❌ {symbol:6s}: {reason}")
    
    print(f"\n📊 Exchange Filter Results: {stats['eligible']}/{stats['total']} stocks eligible ({stats['eligible']/stats['total']*100:.1f}%)")
    return eligible

# Test function
if __name__ == '__main__':
    # Test with some sample symbols
    test_symbols = ['AAPL', 'GOOGL', 'TSLA', 'NVDA', 'MSFT', 'XYZ', 'REIT.TO']
    
    print("Testing major exchange filter:")
    for symbol in test_symbols:
        eligible, reason = is_major_exchange_stock(symbol)
        status = "✅" if eligible else "❌"
        print(f"{status} {symbol:6s}: {reason}")