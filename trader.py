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
    
    def wait_for_fill(self, order_id, timeout_seconds=120):
        """Wait for an order to fill with detailed status updates"""
        import time
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < timeout_seconds:
            try:
                response = requests.get(f"{ALPACA_BASE_URL}/v2/orders/{order_id}", 
                                      headers=self.headers)
                response.raise_for_status()
                order = response.json()
                
                current_status = order['status']
                if current_status != last_status:
                    print(f"Order status: {current_status}")
                    last_status = current_status
                
                if order['status'] == 'filled':
                    filled_qty = order['filled_qty']
                    avg_price = order['filled_avg_price']
                    print(f"✅ Order filled: {filled_qty} shares @ ${avg_price}")
                    return order
                elif order['status'] in ['canceled', 'rejected']:
                    print(f"❌ Order {order_id} failed: {order['status']}")
                    return None
                elif order['status'] == 'partially_filled':
                    filled = order['filled_qty']
                    total = order['qty'] or order.get('notional', 'N/A')
                    print(f"⏳ Partial fill: {filled}/{total}")
                    
                time.sleep(3)  # Check every 3 seconds
            except Exception as e:
                print(f"Error checking order status: {e}")
                time.sleep(3)
                
        print(f"⏰ Order {order_id} timeout after {timeout_seconds}s (last status: {last_status})")
        return None
    
    def place_stop_orders(self, symbol, side, quantity, avg_fill_price, stop_loss_pct=8, take_profit_pct=15):
        """Place stop loss and take profit orders after main order fills"""
        try:
            if side == 'buy':
                # Long position: stop below, profit above
                stop_price = avg_fill_price * (1 - stop_loss_pct/100)
                profit_price = avg_fill_price * (1 + take_profit_pct/100)
                
                # Stop loss order
                stop_order_data = {
                    'symbol': symbol,
                    'side': 'sell',
                    'type': 'stop',
                    'qty': str(quantity),
                    'time_in_force': 'gtc',  # Good till canceled
                    'stop_price': f'{stop_price:.2f}'
                }
                
                # Take profit order
                profit_order_data = {
                    'symbol': symbol,
                    'side': 'sell', 
                    'type': 'limit',
                    'qty': str(quantity),
                    'time_in_force': 'gtc',
                    'limit_price': f'{profit_price:.2f}'
                }
                
            else:
                # Short position: stop above, profit below
                stop_price = avg_fill_price * (1 + stop_loss_pct/100)
                profit_price = avg_fill_price * (1 - take_profit_pct/100)
                
                stop_order_data = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': 'stop',
                    'qty': str(quantity),
                    'time_in_force': 'gtc',
                    'stop_price': f'{stop_price:.2f}'
                }
                
                profit_order_data = {
                    'symbol': symbol,
                    'side': 'buy',
                    'type': 'limit', 
                    'qty': str(quantity),
                    'time_in_force': 'gtc',
                    'limit_price': f'{profit_price:.2f}'
                }
            
            # Place both orders
            stop_response = requests.post(f"{ALPACA_BASE_URL}/v2/orders", 
                                        headers=self.headers, json=stop_order_data)
            profit_response = requests.post(f"{ALPACA_BASE_URL}/v2/orders",
                                          headers=self.headers, json=profit_order_data)
            
            results = {}
            if stop_response.status_code == 201:
                results['stop_order'] = stop_response.json()
                print(f"✅ Stop loss placed at ${stop_price:.2f}")
            else:
                print(f"❌ Stop loss failed: {stop_response.text}")
                
            if profit_response.status_code == 201:
                results['profit_order'] = profit_response.json()
                print(f"✅ Take profit placed at ${profit_price:.2f}")
            else:
                print(f"❌ Take profit failed: {profit_response.text}")
                
            return results
            
        except Exception as e:
            print(f"Error placing stop orders: {e}")
            return {}
    
    def place_bracket_order(self, symbol, side, notional, stop_loss_pct=8, take_profit_pct=15):
        """Place market order and then add stop/profit orders after fill"""
        try:
            # Step 1: Place market order
            print(f"Step 1: Placing market order for {symbol}")
            market_order = self.place_order(symbol, side, notional=notional)
            if not market_order:
                return None
                
            order_id = market_order['id']
            print(f"Market order placed: {order_id}")
            
            # Step 2: Wait for fill
            print("Step 2: Waiting for fill...")
            filled_order = self.wait_for_fill(order_id, timeout_seconds=60)
            if not filled_order:
                print("⚠️  Order did not fill in time, stops will need to be placed manually")
                market_order['stop_orders'] = {'status': 'timeout', 'message': 'Manual stops required'}
                return market_order
            
            # Step 3: Place stop and profit orders
            quantity = abs(float(filled_order['filled_qty']))
            avg_price = float(filled_order['filled_avg_price'])
            
            print(f"Step 3: Filled {quantity} shares at ${avg_price:.2f}, placing stops...")
            stop_orders = self.place_stop_orders(symbol, side, quantity, avg_price, 
                                               stop_loss_pct, take_profit_pct)
            
            # Combine results
            market_order['stop_orders'] = stop_orders
            return market_order
            
        except Exception as e:
            print(f"Bracket order process failed: {e}")
            return self.place_order(symbol, side, notional=notional)  # Fallback
    
    def buy_stock(self, symbol, amount=1000, stop_loss_pct=8, take_profit_pct=15):
        """Buy stock with dollar amount and automatic stop/profit orders"""
        try:
            print(f"Executing BUY strategy for {symbol}: ${amount}")
            order = self.place_bracket_order(symbol, 'buy', amount, stop_loss_pct, take_profit_pct)
            
            # Enhanced logging with stop order details
            stop_orders = order.get('stop_orders', {}) if order else {}
            self.log_trade(symbol, 'buy', amount, order.get('id'), stop_loss_pct, take_profit_pct, stop_orders)
            
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
    
    def log_trade(self, symbol, action, amount, order_id, stop_loss_pct=None, take_profit_pct=None, stop_orders=None):
        """Log trade to positions file"""
        trade_data = {
            'symbol': symbol,
            'action': action,
            'amount': amount,
            'order_id': order_id,
            'stop_loss_pct': stop_loss_pct,
            'take_profit_pct': take_profit_pct,
            'stop_orders': stop_orders or {},
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
    """Execute trade based on earnings result with automatic stops"""
    trader = AlpacaTrader()
    
    try:
        if beat_miss == 'beat':
            print(f"📈 {symbol} BEAT earnings - executing BUY with stops")
            order = trader.buy_stock(symbol, 1000, stop_loss_pct, take_profit_pct)
            if order:
                stop_orders = order.get('stop_orders', {})
                stop_status = "✅ Stops placed" if stop_orders else "⚠️ Manual stops needed"
                return f"✅ Bought $1000 of {symbol} | {stop_status} (Stop: -{stop_loss_pct}%, Target: +{take_profit_pct}%)"
            else:
                return f"❌ Failed to buy {symbol}"
                
        elif beat_miss == 'miss':
            print(f"📉 {symbol} MISSED earnings - no action (shorts disabled)")
            return f"ℹ️ {symbol} missed - no trade (shorts disabled)"
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