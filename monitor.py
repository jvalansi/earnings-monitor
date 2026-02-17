#!/usr/bin/env python3
"""
Earnings Monitor
Polls Finnhub earnings calendar, alerts via OpenClaw when results come in.
Usage: python monitor.py [--date YYYY-MM-DD] [--interval 90] [--duration 180]
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import requests

# --- Config ---
SCRIPT_DIR = Path(__file__).parent
ENV_PATH = SCRIPT_DIR.parent / '.env'
STATE_PATH = SCRIPT_DIR / 'state.json'

def load_env():
    """Load environment variables from .env file"""
    if not ENV_PATH.exists():
        return
    
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

load_env()

FINNHUB_KEY = os.environ.get('FINNHUB_API_KEY')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '1007445801')

if not FINNHUB_KEY:
    print("Error: Missing FINNHUB_API_KEY in environment")
    sys.exit(1)

# --- Args ---
def parse_args():
    parser = argparse.ArgumentParser(description='Earnings Monitor')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'),
                       help='Target date (YYYY-MM-DD)')
    parser.add_argument('--interval', type=int, default=90,
                       help='Polling interval in seconds')
    parser.add_argument('--duration', type=int, default=180,
                       help='Total duration in minutes')
    return parser.parse_args()

# --- State ---
def load_state():
    """Load state from JSON file"""
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'reported': {}}

def save_state(state):
    """Save state to JSON file"""
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)

# --- Finnhub ---
def fetch_earnings(date):
    """Fetch earnings calendar from Finnhub"""
    url = f"https://finnhub.io/api/v1/calendar/earnings"
    params = {
        'from': date,
        'to': date,
        'token': FINNHUB_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('earningsCalendar', [])
    except requests.RequestException as e:
        raise Exception(f"Finnhub API error: {e}")

# --- Alert ---
def send_alert(message):
    """Send alert via OpenClaw Telegram"""
    print(f"ALERT: {message}")
    
    try:
        cmd = [
            'openclaw', 'message', 'send',
            '--channel', 'telegram',
            '--target', TELEGRAM_CHAT_ID,
            '--message', message
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            print(f"Message send failed: {result.stderr}")
            # Fallback: write to alerts file
            alerts_file = SCRIPT_DIR / 'pending-alerts.txt'
            with open(alerts_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()} | {message}\n")
                
    except subprocess.TimeoutExpired:
        print("Message send timed out")
    except Exception as e:
        print(f"Message send error: {e}")

# --- Main loop ---
def poll_earnings(target_date):
    """Poll for new earnings results"""
    state = load_state()
    
    try:
        earnings = fetch_earnings(target_date)
    except Exception as e:
        print(f"Fetch error: {e}")
        return 0
    
    new_results = 0
    
    for earning in earnings:
        eps_actual = earning.get('epsActual')
        if eps_actual is None:
            continue
            
        symbol = earning.get('symbol')
        key = f"{symbol}_{target_date}"
        
        if state['reported'].get(key):
            continue
            
        # New result found!
        eps_estimate = earning.get('epsEstimate')
        revenue_actual = earning.get('revenueActual')
        revenue_estimate = earning.get('revenueEstimate')
        
        # Calculate beat/miss
        beat = None
        diff = None
        pct = None
        
        if eps_estimate is not None:
            beat = eps_actual > eps_estimate
            diff = eps_actual - eps_estimate
            if eps_estimate != 0:
                pct = (diff / abs(eps_estimate)) * 100
        
        # Format emoji and verdict
        if beat is True:
            emoji = "🟢"
            verdict = f"BEAT by ${diff:.4f} ({pct:.1f}%)"
        elif beat is False and eps_actual < eps_estimate:
            emoji = "🔴"
            verdict = f"MISSED by ${abs(diff):.4f} ({pct:.1f}%)"
        elif beat is False:
            emoji = "🟡"
            verdict = "MET estimates"
        else:
            emoji = "📊"
            verdict = "No estimate available"
        
        # Format revenue
        rev_actual_str = f"${revenue_actual/1e9:.2f}B" if revenue_actual else "N/A"
        rev_est_str = f"${revenue_estimate/1e9:.2f}B" if revenue_estimate else "N/A"
        
        # Create alert message
        eps_est_str = f"${eps_estimate}" if eps_estimate is not None else "N/A"
        message = (f"{emoji} {symbol} Earnings\n"
                  f"EPS: ${eps_actual} vs {eps_est_str} est → {verdict}\n"
                  f"Revenue: {rev_actual_str} vs {rev_est_str} est")
        
        send_alert(message)
        
        # Record the result
        state['reported'][key] = {
            'actual': eps_actual,
            'estimate': eps_estimate,
            'time': datetime.now().isoformat()
        }
        new_results += 1
    
    if new_results > 0:
        save_state(state)
    
    # Status report
    pending = sum(1 for e in earnings if e.get('epsActual') is None)
    done = sum(1 for e in earnings if e.get('epsActual') is not None)
    
    print(f"{datetime.now().isoformat()} | {done} reported, {pending} pending, {new_results} new alerts")
    return new_results

def main():
    """Main monitoring loop"""
    args = parse_args()
    
    print(f"Earnings monitor started: date={args.date} interval={args.interval}s duration={args.duration}m")
    
    # Initialize state
    state = load_state()
    if 'reported' not in state:
        state['reported'] = {}
        save_state(state)
    
    # Calculate end time
    end_time = time.time() + (args.duration * 60)
    
    try:
        while time.time() < end_time:
            poll_earnings(args.date)
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\nMonitor interrupted by user")
    
    print("Monitor duration ended. Exiting.")

if __name__ == '__main__':
    main()