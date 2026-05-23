# AI Stock Analyzer

A Streamlit app that analyzes stocks and generates options trading signals
powered by Claude AI.

## Run
```
streamlit run app.py
```

## Stack
- Python + Streamlit
- Claude AI (Anthropic API)
- yfinance for stock data
- ntfy.sh for mobile notifications

## Key Files
- `app.py`              - main UI (5 tabs)
- `ai_engine.py`        - Claude AI analysis
- `data_engine.py`      - stock data fetching
- `indicator_engine.py` - RSI, MACD, EMA, VWAP
- `options_engine.py`   - Greeks, IV, contract selection
- `risk_engine.py`      - position sizing, targets
- `market_engine.py`    - SPY, VIX, sector data
- `scanner_engine.py`   - scans 10 stocks every 5 min
- `tracker.py`          - trade journal
- `notifier.py`         - mobile alerts via ntfy.sh

## Trading Strategy (validated by backtest)

### Account
- Size: $2,000
- Max premium: $3.00 per contract ($300/contract)
- One trade per day max

### Entry Rules
- Only trade STRONG BUY 80%+ confidence
- Never trade plain BUY signals
- SPY must be flat or bullish at open
- Skip if SPY down 1%+ at open
- Skip if VIX above 25
- Skip AMD when price above $440 and VIX above 20

### Exit Rules
- Stop loss: -30% on premium
- Trail after +20% gain hit
- Sell when drops 10% from peak after target
- Never hold past 4 hours intraday

### Stock Priority (from backtest)
1. AMD  - PRIMARY - 58.7% win rate, $1,156/60d
2. TSLA - strong bull days - 38.9% win rate
3. COIN - backup, 82%+ only - 47.2% win rate
4. NVDA - solid backup - 44.2% win rate
5. AAPL - high VIX/safe days - 38.1% win rate

### Backtest Results (60 days)
AMD:  46 signals, 58.7% win rate, $1,156 profit, avg $25/trade
TSLA: 36 signals, 38.9% win rate, $697 profit,  avg $19/trade
NVDA: 43 signals, 44.2% win rate, $394 profit,  avg $9/trade
COIN: 36 signals, 47.2% win rate, $334 profit,  avg $9/trade
AAPL: 42 signals, 38.1% win rate, $367 profit,  avg $8/trade

## Rules
- API keys in secrets.toml only — never hardcode
- All UI code stays in app.py
- Don't manually edit trades.json or patterns.json
- Mobile alerts via ntfy.sh channel: stocktrader2026