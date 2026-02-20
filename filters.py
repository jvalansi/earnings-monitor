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

def is_crsp_eligible(symbol, earnings_data=None):
    """
    Check if stock is eligible for CRSP US Total Market Index
    
    CRSP Total Market criteria (approximation):
    - US incorporated company
    - Market cap > $100M
    - Listed on major US exchange (NYSE, NASDAQ)
    - Common stock (not REITs, ADRs, etc.)
    """
    
    # Quick exclude list for common non-equity tickers
    exclude_patterns = [
        'REIT', 'LP', 'PFD', '/WS', '/WT', '-', '.'
    ]
    
    for pattern in exclude_patterns:
        if pattern in symbol:
            return False, f"Excluded pattern: {pattern}"
    
    # Use market cap from earnings data if available
    if earnings_data:
        # Check if we have revenue estimate (proxy for real companies)
        revenue_est = earnings_data.get('revenueEstimate')
        if revenue_est and revenue_est > 50000000:  # $50M+ revenue
            return True, "Revenue-based inclusion"
    
    # Fallback: get profile data
    profile = get_stock_profile(symbol)
    if not profile:
        return False, "No profile data"
    
    # Check market cap
    market_cap = profile.get('marketCapitalization')
    if not market_cap or market_cap < 100:  # $100M
        return False, f"Market cap too small: ${market_cap}M"
    
    # Check exchange (flexible matching)
    exchange = profile.get('exchange', '').upper()
    major_exchanges = ['NASDAQ', 'NYSE', 'NEW YORK', 'GLOBAL MARKET']
    if not any(ex in exchange for ex in major_exchanges):
        return False, f"Not major US exchange: {exchange}"
    
    # Check country
    country = profile.get('country', '').upper()
    if country != 'US':
        return False, f"Not US company: {country}"
    
    return True, f"Eligible: ${market_cap}M market cap, {exchange}"

def filter_earnings_for_crsp(earnings_list):
    """Filter earnings list to only include CRSP-eligible stocks"""
    
    eligible = []
    stats = {'total': len(earnings_list), 'eligible': 0, 'excluded': 0}
    
    for earning in earnings_list:
        symbol = earning.get('symbol', '')
        
        # Skip if no EPS estimate or actual (probably not a real earnings report)
        if not earning.get('epsEstimate') and not earning.get('epsActual'):
            stats['excluded'] += 1
            continue
            
        is_eligible, reason = is_crsp_eligible(symbol, earning)
        
        if is_eligible:
            eligible.append(earning)
            stats['eligible'] += 1
            print(f"✅ {symbol:6s}: {reason}")
        else:
            stats['excluded'] += 1
            print(f"❌ {symbol:6s}: {reason}")
    
    print(f"\n📊 Filter Results: {stats['eligible']}/{stats['total']} stocks eligible ({stats['eligible']/stats['total']*100:.1f}%)")
    return eligible

# Test function
if __name__ == '__main__':
    # Test with some sample symbols
    test_symbols = ['AAPL', 'GOOGL', 'TSLA', 'NVDA', 'MSFT', 'XYZ', 'REIT.TO']
    
    print("Testing CRSP eligibility filter:")
    for symbol in test_symbols:
        eligible, reason = is_crsp_eligible(symbol)
        status = "✅" if eligible else "❌"
        print(f"{status} {symbol:6s}: {reason}")