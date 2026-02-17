# Earnings Monitor

Real-time earnings results monitoring system. Polls Finnhub for earnings calendar data and sends instant Telegram alerts when companies report results.

## Features

- 📊 **Real-time monitoring** - Polls every 90 seconds during market hours
- 🎯 **Beat/Miss detection** - Compares actual vs estimated EPS
- 📱 **Telegram alerts** - Instant notifications via OpenClaw
- 🔄 **Deduplication** - Tracks already-reported results
- ⚡ **Low resource usage** - ~1 API call per 90 seconds
- 🤖 **No LLM dependency** - Direct system process
- 📈 **Paper Trading** - Auto-trades on Alpaca based on earnings beats/misses
- 💰 **$1000 per trade** - Fixed position sizing for consistent risk

## Setup

1. **API Keys** (create `.env` file):
```bash
FINNHUB_API_KEY=your_finnhub_key
TELEGRAM_CHAT_ID=your_telegram_chat_id

# For paper trading (optional)
ALPACA_API_KEY=your_alpaca_key_id
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

2. **Install dependencies**:
```bash
pip3 install -r requirements.txt
```

3. **Make scripts executable**:
```bash
chmod +x start-monitor.sh
```

4. **Set up cron** (optional - for automated runs):
```bash
# Pre-market: 5:55 AM ET (10:55 UTC)
55 10 * * 1-5 /path/to/earnings/start-monitor.sh pre-market

# After-hours: 4:00 PM ET (21:00 UTC) 
0 21 * * 1-5 /path/to/earnings/start-monitor.sh after-hours
```

## Usage

### Manual run
```bash
# Run for today's earnings, 90s interval, 180 minutes duration
python3 monitor.py

# Custom date and timing
python3 monitor.py --date 2026-02-18 --interval 60 --duration 120
```

### Background process
```bash
# Start pre-market monitor (3 hours)
./start-monitor.sh pre-market

# Start after-hours monitor (2.5 hours)
./start-monitor.sh after-hours
```

## File Structure

- `monitor.py` - Main monitoring script
- `trader.py` - Paper trading module (Alpaca integration)
- `start-monitor.sh` - Background process launcher  
- `requirements.txt` - Python dependencies
- `state.json` - Tracks reported results (auto-created)
- `positions.json` - Trading history and positions (auto-created)
- `monitor.log` - Process logs
- `monitor.pid` - Process ID file

## Alert Format

```
🟢 AAPL Earnings
EPS: $1.52 vs $1.39 est → BEAT by $0.13 (9.4%)
Revenue: $123.95B vs $118.66B est

🤖 ✅ Bought $1000 of AAPL (Order ID: abc123)
```

- 🟢 Beat (actual > estimate)
- 🔴 Miss (actual < estimate)  
- 🟡 Met (actual = estimate)
- 📊 No estimate available

## Trading Strategy

**Automatic paper trading** (when Alpaca credentials are provided):

- **Earnings Beat** → Buy $1000 of the stock
- **Earnings Miss** → Short $1000 of the stock  
- **Met Estimates** → No action
- **No Estimate** → No action

All trades are logged in `positions.json` and orders are placed as market orders during regular/extended trading hours.

## API Limits

- **Finnhub Free**: 60 calls/minute
- **Monitor usage**: ~40 calls/hour (well within limits)
- **Single API call** returns all earnings for the day

## Dependencies

- Python 3.6+
- `requests` library (`pip3 install requests`)
- `openclaw` CLI (for Telegram messaging)
- Finnhub API key (free tier sufficient)

## Future Enhancements

- [ ] Paper trading integration (Alpaca)
- [ ] Multiple notification channels
- [ ] Historical performance tracking
- [ ] Customizable alert strategies
- [ ] Webhook support

## License

MIT