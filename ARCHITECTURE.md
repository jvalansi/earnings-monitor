# Earnings Monitor - System Architecture

## 🏗️ High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Earnings Monitor System                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐ │
│  │   Cron      │───▶│  start-monitor  │───▶│   monitor.py    │ │
│  │ (scheduler) │    │     .sh         │    │  (main loop)    │ │
│  └─────────────┘    └─────────────────┘    └─────────────────┘ │
│                                                      │          │
│                              ┌───────────────────────┼─────────┐│
│                              │                       ▼         ││
│                              │              ┌─────────────────┐││
│                              │              │   trader.py     │││
│                              │              │ (AlpacaTrader)  │││
│                              │              └─────────────────┘││
│                              │                       │         ││
└──────────────────────────────┼───────────────────────┼─────────┘│
                               │                       │          │
┌──────────────────────────────┼───────────────────────┼─────────┐│
│                External APIs │                       │         ││
│                              │                       │         ││
│  ┌─────────────────┐        │         ┌─────────────────┐     ││
│  │   Finnhub API   │◀───────┤         │   Alpaca API    │◀────┘│
│  │ (earnings data) │        │         │ (paper trading) │      │
│  └─────────────────┘        │         └─────────────────┘      │
│                              │                                 │
│  ┌─────────────────┐        │                                 │
│  │  OpenClaw CLI   │◀───────┘                                 │
│  │ (Telegram msgs) │                                          │
│  └─────────────────┘                                          │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                          Data Storage                          │
│                                                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ state.json  │  │positions.json│  │ monitor.log/.env/etc   │ │
│  │(reported    │  │(trade       │  │ (logs, config, temp)   │ │
│  │ earnings)   │  │ history)    │  │                        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## 📦 Module Structure

### **monitor.py** (Main Controller)
```python
┌─────────────────────────────────────┐
│            monitor.py               │
├─────────────────────────────────────┤
│ Functions:                          │
│ • load_env()                        │
│ • fetch_earnings(date)              │
│ • send_alert(message)               │
│ • poll_earnings(target_date)        │
│ • load_state() / save_state()       │
│ • main()                            │
├─────────────────────────────────────┤
│ External Dependencies:              │
│ • requests (Finnhub API)            │
│ • subprocess (OpenClaw CLI)         │
│ • trader.execute_earnings_trade()   │
└─────────────────────────────────────┘
```

### **trader.py** (Trading Engine)
```python
┌─────────────────────────────────────┐
│        AlpacaTrader Class           │
├─────────────────────────────────────┤
│ Core Methods:                       │
│ • __init__()                        │
│ • get_account()                     │
│ • get_position(symbol)              │
│ • get_last_price(symbol)            │
│ • place_order(...)                  │
│ • wait_for_fill(order_id)           │
│ • place_stop_orders(...)            │
│ • place_bracket_order(...)          │
│ • buy_stock(symbol, amount)         │
│ • short_stock(symbol, amount)       │
│ • log_trade(...)                    │
│ • load_positions() / save_positions()│
│ • get_portfolio_summary()           │
├─────────────────────────────────────┤
│ Utility Functions:                  │
│ • execute_earnings_trade()          │
└─────────────────────────────────────┘
```

## 🔄 Data Flow Diagram

```
┌─────────────┐
│   Cron      │ 5:55 AM ET (pre-market)
│ Scheduler   │ 4:00 PM ET (after-hours) 
└──────┬──────┘
       │
       ▼
┌─────────────┐
│start-monitor│ Launch background Python process
│    .sh      │ Set duration & interval
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│              monitor.py                     │
│                                             │
│  ┌─────────────────┐                       │
│  │ Main Loop       │ Every 90 seconds      │
│  │ (poll_earnings) │                       │
│  └─────────┬───────┘                       │
│            │                               │
│            ▼                               │
│  ┌─────────────────┐    ┌─────────────────┐│
│  │ fetch_earnings  │───▶│  Finnhub API    ││
│  │ (from Finnhub)  │    │  HTTP Request   ││
│  └─────────┬───────┘    └─────────────────┘│
│            │                               │
│            ▼                               │
│  ┌─────────────────┐                       │
│  │ Check for NEW   │                       │
│  │ epsActual data  │                       │
│  └─────────┬───────┘                       │
│            │                               │
│            ▼                               │
│  ┌─────────────────┐                       │
│  │ Calculate       │                       │
│  │ Beat/Miss/Met   │                       │
│  └─────────┬───────┘                       │
│            │                               │
│            ▼                               │
│  ┌─────────────────┐    ┌─────────────────┐│
│  │execute_earnings │───▶│   trader.py     ││
│  │_trade()         │    │ (if beat/miss)  ││
│  └─────────┬───────┘    └─────────────────┘│
│            │                               │
│            ▼                               │
│  ┌─────────────────┐                       │
│  │ send_alert()    │                       │
│  │ (Telegram)      │                       │
│  └─────────┬───────┘                       │
│            │                               │
│            ▼                               │
│  ┌─────────────────┐                       │
│  │ Update state.json│                      │
│  │ (prevent dups)  │                       │
│  └─────────────────┘                       │
└─────────────────────────────────────────────┘
```

## 🛠️ Trading Flow Detail

```
Earnings Beat Detected
         │
         ▼
┌─────────────────┐
│ AlpacaTrader    │
│ .buy_stock()    │
└─────┬───────────┘
      │
      ▼
┌─────────────────┐
│place_bracket    │
│_order()         │ 
│                 │
│ Step 1: Market  │───┐
│ Order ($1000)   │   │
│                 │   │
│ Step 2: Wait    │◀──┘
│ for Fill        │   
│                 │   
│ Step 3: Place   │───┐
│ Stop Orders     │   │
└─────┬───────────┘   │
      │               │
      ▼               │
┌─────────────────┐   │
│ Alpaca API      │◀──┤
│ HTTP Requests   │   │
│                 │   │
│ • POST /orders  │   │
│ • GET /orders/id│   │
│ • POST /orders  │◀──┘
│   (stop loss)   │
│ • POST /orders  │
│   (take profit) │
└─────────────────┘
```

## 🗂️ File Dependencies

```
earnings/
├── monitor.py ──────┬─→ trader.py
│                    ├─→ requests (Finnhub)
│                    ├─→ subprocess (OpenClaw CLI)  
│                    └─→ json, time, datetime
│
├── trader.py ───────┬─→ requests (Alpaca API)
│                    ├─→ json, datetime
│                    └─→ os (environment vars)
│
├── start-monitor.sh ─→ monitor.py
│
├── state.json ──────→ monitor.py (read/write)
├── positions.json ──→ trader.py (read/write)
├── monitor.log ─────→ start-monitor.sh (append)
├── .env ────────────→ trader.py, monitor.py (read)
│
└── README.md
```

## ⚡ Process Lifecycle

```
System Cron
     │
     ▼ (5:55 AM or 4:00 PM)
start-monitor.sh
     │
     ├─ Set MODE (pre-market/after-hours)
     ├─ Set DURATION (180/150 minutes)  
     └─ Launch: nohup python3 monitor.py &
              │
              ▼
          monitor.py
              │
              ├─ Load environment (.env)
              ├─ Initialize state (state.json)
              └─ Enter main loop:
                   │
                   └─ Every 90 seconds:
                        ├─ Fetch earnings (Finnhub)
                        ├─ Check for new results
                        ├─ Execute trades (trader.py)
                        ├─ Send alerts (OpenClaw)
                        └─ Update state
                             │
                             └─ Continue until DURATION expires
```

## 🔗 External API Integration Points

| Component | API | Purpose | Rate Limits |
|-----------|-----|---------|-------------|
| `monitor.py` | **Finnhub REST** | Earnings calendar data | 60 calls/min |
| `trader.py` | **Alpaca REST** | Paper trading orders | 200 calls/min |
| `monitor.py` | **OpenClaw CLI** | Telegram messaging | Via CLI subprocess |

## 🛡️ Error Handling Strategy

```
┌─────────────────────────────────────┐
│         Graceful Degradation        │
├─────────────────────────────────────┤
│                                     │
│ Finnhub API Fail ──► Log + Continue │
│                                     │
│ Alpaca API Fail ───► Fallback Order │
│                                     │
│ Order Timeout ─────► Manual Stops   │
│                                     │
│ OpenClaw CLI Fail ─► Write to File  │
│                                     │
│ Process Crash ─────► Cron Restart   │
│                                     │
└─────────────────────────────────────┘
```

This architecture provides **fault tolerance**, **modularity**, and **scalability** for the earnings monitoring and trading system.