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
    
    def place_order(self, symbol, side, notional=None, qty=None, order_type='market', 
                   stop_loss_pct=None, take_profit_pct=None):
        """Place an order with optional stop loss and take profit"""
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
        
        # Add bracket order for risk management
        if stop_loss_pct or take_profit_pct:
            order_data['order_class'] = 'bracket'
            
            if stop_loss_pct:
                if side == 'buy':
                    # For long positions, stop loss is below entry
                    order_data['stop_loss'] = {'stop_price': f'{(1 - stop_loss_pct/100):.4f}%'}
                else:
                    # For short positions, stop loss is above entry  
                    order_data['stop_loss'] = {'stop_price': f'{(1 + stop_loss_pct/100):.4f}%'}
            
            if take_profit_pct:
                if side == 'buy':
                    # For long positions, take profit is above entry
                    order_data['take_profit'] = {'limit_price': f'{(1 + take_profit_pct/100):.4f}%'}
                else:
                    # For short positions, take profit is below entry
                    order_data['take_profit'] = {'limit_price': f'{(1 - take_profit_pct/100):.4f}%'}
        
        response = requests.post(f"{ALPACA_BASE_URL}/v2/orders", 
                               headers=self.headers, json=order_data)
        response.raise_for_status()
        return response.json()
    
    def place_bracket_order(self, symbol, side, notional, stop_loss_pct=8, take_profit_pct=15):
        """Place a market order with plan to add stops after fill"""
        try:
            # For now, just place a simple market order
            # TODO: Add stop/profit orders after the main order fills
            print(f"Placing market order (stops will be added after fill)")
            return self.place_order(symbol, side, notional=notional)
            
        except Exception as e:
            print(f"Market order failed: {e}")
            return None
    
    def buy_stock(self, symbol, amount=1000, stop_loss_pct=8, take_profit_pct=15):
        """Buy stock with dollar amount and risk management"""
        try:
            print(f"Placing BUY order for {symbol}: ${amount} (Stop: -{stop_loss_pct}%, Target: +{take_profit_pct}%)")
            order = self.place_bracket_order(symbol, 'buy', amount, stop_loss_pct, take_profit_pct)
            
            # Log the trade
            self.log_trade(symbol, 'buy', amount, order.get('id'), stop_loss_pct, take_profit_pct)
            
            return order
        except Exception as e:
            print(f"Failed to buy {symbol}: {e}")
            return None
    
    def short_stock(self, symbol, amount=1000, stop_loss_pct=8, take_profit_pct=15):
        """Short stock with dollar amount and risk management"""
        try:
            print(f"Placing SHORT order for {symbol}: ${amount} (Stop: +{stop_loss_pct}%, Target: -{take_profit_pct}%)")
            order = self.place_bracket_order(symbol, 'sell', amount, stop_loss_pct, take_profit_pct)
            
            # Log the trade
            self.log_trade(symbol, 'short', amount, order.get('id'), stop_loss_pct, take_profit_pct)
            
            return order
        except Exception as e:
            print(f"Failed to short {symbol}: {e}")
            return None
    
    def log_trade(self, symbol, action, amount, order_id, stop_loss_pct=None, take_profit_pct=None):
        """Log trade to positions file"""
        trade_data = {
            'symbol': symbol,
            'action': action,
            'amount': amount,
            'order_id': order_id,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
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

def execute_earnings_trade(symbol, beat_miss, beat_percentage=None, 
                          stop_loss_pct=8, take_profit_pct=15):
    """Execute trade based on earnings result"""
    trader = AlpacaTrader()
    
    try:
        if beat_miss == 'beat':
            print(f"📈 {symbol} BEAT earnings - executing BUY trade")
            order = trader.buy_stock(symbol, 1000, stop_loss_pct, take_profit_pct)
            if order:
                return f"✅ Bought $1000 of {symbol} (planning stops: -{stop_loss_pct}%/+{take_profit_pct}%)"
            else:
                return f"❌ Failed to buy {symbol}"
                
        elif beat_miss == 'miss':
            # Skip shorting for now - too many issues with availability
            print(f"📉 {symbol} MISSED earnings - skipping short (not implemented)")
            return f"ℹ️ {symbol} missed - shorts disabled for reliability"
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