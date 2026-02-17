#!/usr/bin/env python3
"""
Paper Trading Module for Earnings Monitor
Integrates with Alpaca API to execute trades based on earnings beats/misses
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

# Alpaca API configuration
ALPACA_API_KEY = os.environ.get('ALPACA_API_KEY')
ALPACA_SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY') 
ALPACA_BASE_URL = os.environ.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

class AlpacaTrader:
    def __init__(self):
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise ValueError("Missing Alpaca API credentials")
            
        self.headers = {
            'APCA-API-KEY-ID': ALPACA_API_KEY,
            'APCA-API-SECRET-KEY': ALPACA_SECRET_KEY,
            'Content-Type': 'application/json'
        }
        
        self.positions_file = Path(__file__).parent / 'positions.json'
        
    def get_account(self):
        """Get account information"""
        response = requests.get(f"{ALPACA_BASE_URL}/v2/account", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_position(self, symbol):
        """Get current position for a symbol"""
        try:
            response = requests.get(f"{ALPACA_BASE_URL}/v2/positions/{symbol}", headers=self.headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None
    
    def get_last_price(self, symbol):
        """Get the last trade price for a symbol"""
        response = requests.get(f"{ALPACA_BASE_URL}/v2/stocks/{symbol}/trades/latest", headers=self.headers)
        response.raise_for_status()
        return float(response.json()['trade']['p'])
    
    def place_order(self, symbol, side, notional=None, qty=None, order_type='market'):
        """Place an order"""
        order_data = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'time_in_force': 'day'
        }
        
        if notional:
            order_data['notional'] = str(notional)
        elif qty:
            order_data['qty'] = str(qty)
        else:
            raise ValueError("Must specify either notional or qty")
        
        response = requests.post(f"{ALPACA_BASE_URL}/v2/orders", 
                               headers=self.headers, json=order_data)
        response.raise_for_status()
        return response.json()
    
    def buy_stock(self, symbol, amount=1000):
        """Buy stock with dollar amount"""
        try:
            print(f"Placing BUY order for {symbol}: ${amount}")
            order = self.place_order(symbol, 'buy', notional=amount)
            
            # Log the trade
            self.log_trade(symbol, 'buy', amount, order.get('id'))
            
            return order
        except Exception as e:
            print(f"Failed to buy {symbol}: {e}")
            return None
    
    def short_stock(self, symbol, amount=1000):
        """Short stock with dollar amount"""
        try:
            print(f"Placing SHORT order for {symbol}: ${amount}")
            order = self.place_order(symbol, 'sell', notional=amount)
            
            # Log the trade
            self.log_trade(symbol, 'short', amount, order.get('id'))
            
            return order
        except Exception as e:
            print(f"Failed to short {symbol}: {e}")
            return None
    
    def log_trade(self, symbol, action, amount, order_id):
        """Log trade to positions file"""
        trade_data = {
            'symbol': symbol,
            'action': action,
            'amount': amount,
            'order_id': order_id,
            'timestamp': datetime.now().isoformat()
        }
        
        # Load existing positions
        positions = self.load_positions()
        if 'trades' not in positions:
            positions['trades'] = []
        
        positions['trades'].append(trade_data)
        self.save_positions(positions)
    
    def load_positions(self):
        """Load positions from JSON file"""
        try:
            with open(self.positions_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def save_positions(self, positions):
        """Save positions to JSON file"""
        with open(self.positions_file, 'w') as f:
            json.dump(positions, f, indent=2)
    
    def get_portfolio_summary(self):
        """Get portfolio summary"""
        try:
            account = self.get_account()
            positions = self.load_positions()
            
            summary = {
                'account_value': float(account['portfolio_value']),
                'buying_power': float(account['buying_power']),
                'total_trades': len(positions.get('trades', [])),
                'cash': float(account['cash'])
            }
            
            return summary
        except Exception as e:
            print(f"Error getting portfolio summary: {e}")
            return None

def execute_earnings_trade(symbol, beat_miss, beat_percentage=None):
    """Execute trade based on earnings result"""
    trader = AlpacaTrader()
    
    try:
        if beat_miss == 'beat':
            print(f"📈 {symbol} BEAT earnings - executing BUY trade")
            order = trader.buy_stock(symbol, 1000)
            if order:
                return f"✅ Bought ${1000} of {symbol} (Order ID: {order.get('id')})"
            else:
                return f"❌ Failed to buy {symbol}"
                
        elif beat_miss == 'miss':
            print(f"📉 {symbol} MISSED earnings - executing SHORT trade")
            order = trader.short_stock(symbol, 1000)
            if order:
                return f"✅ Shorted ${1000} of {symbol} (Order ID: {order.get('id')})"
            else:
                return f"❌ Failed to short {symbol}"
        else:
            return f"ℹ️ {symbol} met estimates - no trade executed"
            
    except Exception as e:
        return f"❌ Trading error for {symbol}: {e}"

# Test function
if __name__ == '__main__':
    trader = AlpacaTrader()
    summary = trader.get_portfolio_summary()
    if summary:
        print(f"Portfolio Value: ${summary['account_value']:,.2f}")
        print(f"Buying Power: ${summary['buying_power']:,.2f}")
        print(f"Total Trades: {summary['total_trades']}")
    else:
        print("Failed to get portfolio summary")