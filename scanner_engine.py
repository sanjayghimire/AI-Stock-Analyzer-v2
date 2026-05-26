import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date
import time
import warnings
warnings.filterwarnings('ignore')

from data_engine      import get_all_data
from indicator_engine import calculate_indicators, get_signals, calculate_score
from market_engine    import get_market_conditions
from options_engine   import (get_best_option, get_most_active_expiry,
                               get_best_options)
from notifier         import alert_scanner_found

# ── Watchlist ─────────────────────────────────────────────────
# Top 50 most active options stocks
WATCHLIST = [
    # Big Tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA",
    # Chips & Hardware
    "AMD", "INTC", "QCOM", "MU", "AVGO",
    # High-beta Tech
    "PLTR", "COIN", "HOOD", "CRWD", "SNOW", "DDOG", "SQ",
    # Finance
    "JPM", "BAC", "GS", "V", "MA",
    # Healthcare
    "LLY", "MRNA", "PFE",
    # Consumer
    "NFLX", "SHOP", "UBER", "ABNB", "NKE", "DIS",
    # Energy
    "XOM", "CVX",
    # ETFs (most liquid options)
    "SPY", "QQQ", "IWM",
    # Meme / High vol
    "AMC", "GME",
    # Other active
    "BA", "BABA", "ORCL", "CRM", "NOW",
]

# ── IV Rank ───────────────────────────────────────────────────

def calculate_iv_rank(ticker):
    """
    Calculate IV Rank using 52-week high/low IV
    IV Rank = (current IV - 52w low) / (52w high - 52w low) * 100
    Low IV Rank = cheap options = good to buy
    """
    try:
        stock    = yf.Ticker(ticker)
        hist     = stock.history(period="1y", interval="1wk")
        options  = stock.options

        if not options:
            return None

        # Get current IV from nearest expiry
        nearest  = options[0]
        chain    = stock.option_chain(nearest)
        calls    = chain.calls

        # Filter ATM options
        current_price = hist['Close'].iloc[-1]
        atm_calls = calls[
            (calls['strike'] >= current_price * 0.95) &
            (calls['strike'] <= current_price * 1.05)
        ]

        if atm_calls.empty:
            return None

        current_iv = atm_calls['impliedVolatility'].median() * 100

        # Estimate 52w IV range from historical volatility
        returns    = hist['Close'].pct_change().dropna()
        # Rolling 30-day HV
        hv_series  = returns.rolling(4).std() * np.sqrt(52) * 100
        iv_52w_low = hv_series.min()
        iv_52w_high= hv_series.max() * 1.5  # IV tends to be higher than HV

        if iv_52w_high == iv_52w_low:
            return 50

        iv_rank = ((current_iv - iv_52w_low) /
                   (iv_52w_high - iv_52w_low)) * 100
        return round(max(0, min(100, iv_rank)), 1)

    except Exception as e:
        return None

# ── Unusual Flow Detection ────────────────────────────────────

def detect_unusual_flow(options_data, current_price):
    """
    Detect unusual options activity
    Volume/OI > 3x = new money entering
    Premium > $25K = not retail noise
    """
    if not options_data:
        return 0, []

    score    = 0
    signals  = []

    try:
        for expiry, chain in list(options_data.items())[:3]:
            calls = chain['calls']
            puts  = chain['puts']

            for _, row in calls.iterrows():
                try:
                    vol = row.get('volume', 0) or 0
                    oi  = row.get('openInterest', 1) or 1
                    bid = row.get('bid', 0) or 0
                    ask = row.get('ask', 0) or 0
                    mid = (bid + ask) / 2

                    # Volume/OI ratio > 3x = unusual
                    if vol > 0 and oi > 0 and (vol / oi) > 3:
                        premium_total = mid * vol * 100
                        if premium_total > 25000:
                            score += 20
                            signals.append(
                                f"CALL sweep ${row['strike']} — "
                                f"{int(vol)} contracts "
                                f"(${int(premium_total/1000)}K premium)"
                            )
                        elif premium_total > 10000:
                            score += 10
                            signals.append(
                                f"Unusual CALL ${row['strike']} — "
                                f"Vol/OI: {round(vol/oi, 1)}x"
                            )
                except:
                    continue

            for _, row in puts.iterrows():
                try:
                    vol = row.get('volume', 0) or 0
                    oi  = row.get('openInterest', 1) or 1
                    bid = row.get('bid', 0) or 0
                    ask = row.get('ask', 0) or 0
                    mid = (bid + ask) / 2

                    if vol > 0 and oi > 0 and (vol / oi) > 3:
                        premium_total = mid * vol * 100
                        if premium_total > 25000:
                            score += 15
                            signals.append(
                                f"PUT sweep ${row['strike']} — "
                                f"{int(vol)} contracts "
                                f"(${int(premium_total/1000)}K premium)"
                            )
                except:
                    continue

    except Exception as e:
        pass

    return min(25, score), signals[:3]

# ── Gamma Squeeze Detection ───────────────────────────────────

def detect_gamma_squeeze(ticker, options_data, current_price):
    """
    Gamma squeeze conditions:
    - High call volume relative to float
    - OTM calls being bought aggressively
    - Short interest high (if available)
    """
    score   = 0
    signals = []

    try:
        if not options_data:
            return 0, []

        stock = yf.Ticker(ticker)
        info  = stock.info

        # Short interest
        short_pct = info.get('shortPercentOfFloat', 0) or 0
        if short_pct > 0.20:
            score += 10
            signals.append(f"High short interest: {round(short_pct*100, 1)}%")
        elif short_pct > 0.10:
            score += 5
            signals.append(f"Moderate short interest: {round(short_pct*100, 1)}%")

        # OTM call buying pressure
        for expiry, chain in list(options_data.items())[:2]:
            calls = chain['calls']
            # OTM calls = strike > current price * 1.05
            otm_calls = calls[calls['strike'] > current_price * 1.05]
            if not otm_calls.empty:
                otm_vol   = otm_calls['volume'].sum()
                total_vol = calls['volume'].sum()
                if total_vol > 0 and otm_vol / total_vol > 0.4:
                    score += 8
                    signals.append(
                        f"OTM call buying: {round(otm_vol/total_vol*100)}% of volume"
                    )

    except Exception as e:
        pass

    return min(15, score), signals

# ── Main Score Calculator ─────────────────────────────────────

def score_ticker(ticker, market_conditions, interval='1h'):
    """
    Score a single ticker 0-100
    Returns dict with score, signals, best contract
    """
    result = {
        'ticker':          ticker,
        'score':           0,
        'signal':          'SKIP',
        'reasons':         [],
        'best_contract':   None,
        'unusual_flow':    [],
        'gamma_signals':   [],
        'iv_rank':         None,
        'error':           None
    }

    try:
        # Fetch all data
        data = get_all_data(ticker, interval)

        if data['df'] is None or len(data['df']) < 50:
            result['error'] = 'Insufficient data'
            return result

        # Calculate indicators
        df      = calculate_indicators(data['df'])
        if df is None:
            result['error'] = 'Indicator calculation failed'
            return result

        signals = get_signals(df)
        signal, confidence, bull, bear = calculate_score(signals)

        total_score = 0

        # ── Signal 1: Technical Confluence (0-25 pts) ─────────
        tech_score = 0
        reasons    = []

        if signals.get('above_ema200'):
            tech_score += 5
            reasons.append("Above EMA200")
        if signals.get('ema_bullish'):
            tech_score += 5
            reasons.append("EMA stack bullish")
        if signals.get('macd_bullish'):
            tech_score += 4
            reasons.append("MACD bullish")
        if signals.get('rsi_bullish'):
            tech_score += 4
            reasons.append("RSI in bull zone")
        if signals.get('above_vwap'):
            tech_score += 4
            reasons.append("Above VWAP")
        if signals.get('high_volume'):
            tech_score += 3
            reasons.append(f"Volume spike {signals.get('vol_ratio')}x")

        total_score += min(25, tech_score)

        # ── Signal 2: Unusual Options Flow (0-25 pts) ─────────
        flow_score, flow_signals = detect_unusual_flow(
            data['options'], signals['close'])
        total_score += flow_score
        result['unusual_flow'] = flow_signals
        if flow_signals:
            reasons.extend(flow_signals[:2])

        # ── Signal 3: IV Rank (0-20 pts) ──────────────────────
        iv_rank = calculate_iv_rank(ticker)
        result['iv_rank'] = iv_rank

        if iv_rank is not None:
            if iv_rank < 30:
                total_score += 20
                reasons.append(f"IV Rank {iv_rank}% — options CHEAP")
            elif iv_rank < 50:
                total_score += 10
                reasons.append(f"IV Rank {iv_rank}% — options fair")
            else:
                reasons.append(f"IV Rank {iv_rank}% — options expensive")

        # ── Signal 4: Market Conditions (0-15 pts) ────────────
        mkt_score = 0
        if market_conditions.get('spy_trend') == 'BULLISH':
            mkt_score += 7
            reasons.append("SPY bullish")
        if market_conditions.get('vix', 99) < 20:
            mkt_score += 5
            reasons.append(f"VIX low: {market_conditions.get('vix')}")
        if market_conditions.get('market_mood') == 'Risk-ON':
            mkt_score += 3
            reasons.append("Risk-ON market")

        total_score += min(15, mkt_score)

        # ── Signal 5: Gamma Squeeze (0-15 pts) ────────────────
        gamma_score, gamma_signals = detect_gamma_squeeze(
            ticker, data['options'], signals['close'])
        total_score += gamma_score
        result['gamma_signals'] = gamma_signals
        if gamma_signals:
            reasons.extend(gamma_signals[:1])

        # ── Deductions ─────────────────────────────────────────
        if data['earnings'].get('warning'):
            total_score -= 15
            reasons.append(
                f"EARNINGS in {data['earnings'].get('days_until')} days — RISK")

        if market_conditions.get('vix', 0) > 30:
            total_score -= 10
            reasons.append("VIX too high — market fearful")

        # ── Final Score ────────────────────────────────────────
        total_score = max(0, min(100, total_score))

        # Determine signal label
        if total_score >= 80:
            trade_signal = 'STRONG BUY'
        elif total_score >= 65:
            trade_signal = 'BUY'
        elif total_score >= 50:
            trade_signal = 'WATCH'
        else:
            trade_signal = 'SKIP'

        # Get best contract
        # Fix 1: pass correct current_price from THIS ticker's signals
        # Fix 2: filter contracts under $5 premium (max $500/contract for $2K account)
        best_contract = None
        if data['options'] and total_score >= 60:
            expiry   = get_most_active_expiry(data['options'])
            # Get top 5 options for this ticker
            from options_engine import get_best_options
            options_list = get_best_options(
                data['options'],
                signals['close'],   # correct price for THIS ticker
                signal,
                expiry,
                top_n=10
            )
            # Filter by affordable premium for $2K account
            affordable = [
                o for o in options_list
                if o.get('premium', 999) <= 3.00      # max $300/contract
                and o.get('premium', 0) >= 0.30        # not too cheap/illiquid
                and o.get('volume', 0) > 50            # has volume
                and o.get('open_interest', 0) > 100    # has open interest
            ]
            best_contract = affordable[0] if affordable else None

        result.update({
            'score':         total_score,
            'signal':        trade_signal,
            'reasons':       reasons,
            'best_contract': best_contract,
            'close':         signals['close'],
            'rsi':           signals.get('rsi'),
            'vol_ratio':     signals.get('vol_ratio'),
            'tech_signal':   signal,
            'confidence':    confidence,
        })

    except Exception as e:
        result['error'] = str(e)

    return result

# ── Run Full Scan ─────────────────────────────────────────────

def run_scanner(watchlist=None, interval='1h',
                min_score=60, notify=True, verbose=True, force=False):
    """
    Scan entire watchlist and return ranked opportunities
    """
    if watchlist is None:
        watchlist = WATCHLIST

    market = get_market_conditions()

    if verbose:
        print(f"\n{'='*50}")
        print(f"SCANNER STARTING — {datetime.now().strftime('%I:%M %p CST')}")
        print(f"SPY: {market.get('spy_trend')} | "
              f"VIX: {market.get('vix')} | "
              f"Mood: {market.get('market_mood')}")
        print(f"Scanning {len(watchlist)} stocks...")
        print(f"{'='*50}\n")

    results = []

    for i, ticker in enumerate(watchlist):
        if verbose:
            print(f"[{i+1}/{len(watchlist)}] Scanning {ticker}...", end=" ")

        result = score_ticker(ticker, market, interval)

        if result['error']:
            if verbose:
                print(f"Error: {result['error']}")
            continue

        results.append(result)

        if verbose:
            score  = result['score']
            signal = result['signal']
            icon   = ("🔴" if score >= 80 else
                      "🟡" if score >= 60 else "⚪")
            print(f"{icon} Score: {score}/100 — {signal}")

        # Send notification ONLY for 80+ scores
        # App will show top 3 visually for 65+ scores
        if notify and result['score'] >= 80:
            contract = result['best_contract']
            if contract:
                contract_str = (f"${contract['strike']} "
                                f"{contract['type']} "
                                f"exp {contract['expiry']}")
                alert_scanner_found(
                    ticker   = ticker,
                    score    = result['score'],
                    contract = contract_str,
                    premium  = contract['premium']
                )

        # Small delay to avoid rate limiting
        time.sleep(2)

    # Sort by score
    results = sorted(results, key=lambda x: x['score'], reverse=True)

    # Filter to min score then keep TOP 3 only
    top_results = [r for r in results if r['score'] >= min_score][:3]

    if verbose:
        print(f"\n{'='*50}")
        print(f"SCAN COMPLETE — Top {len(top_results)} opportunities")
        print(f"{'='*50}\n")

        for i, r in enumerate(top_results):
            print(f"\n{'─'*40}")
            print(f"#{i+1} {r['ticker']} — Score: {r['score']}/100")
            print(f"Signal: {r['signal']} | Price: ${r['close']}")
            if r['best_contract']:
                c = r['best_contract']
                print(f"Contract: ${c['strike']} {c['type']} "
                      f"exp {c['expiry']} @ ${c['premium']}")
            print(f"Why: {', '.join(r['reasons'][:3])}")
            if r['score'] >= 80:
                print(f"*** STRONG SIGNAL — Phone notified ***")
            elif r['score'] >= 65:
                print(f"--- Good setup — visible in app ---")

    return results

# ── Quick Scan (top 10 only — faster) ────────────────────────

def run_quick_scan(interval='1h', force=False):
    """
    Scan only the top 10 most active stocks
    Runs in ~2 minutes vs 15 min for full scan
    """
    quick_list = [
        "SPY", "QQQ", "NVDA", "AAPL", "TSLA",
        "AMD",  "META", "AMZN", "MSFT", "COIN"
    ]
    return run_scanner(
        watchlist = quick_list,
        interval  = interval,
        min_score = 55,
        notify    = True,
        verbose   = True,
        force = False
    )


# ── Test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Running quick scan on top 10 stocks...")
    print("This will take about 2-3 minutes...\n")
    results = run_quick_scan()

    if results:
        best = results[0]
        print(f"\nBEST OPPORTUNITY:")
        print(f"Ticker:  {best['ticker']}")
        print(f"Score:   {best['score']}/100")
        print(f"Signal:  {best['signal']}")
        if best['best_contract']:
            c = best['best_contract']
            print(f"Buy:     ${c['strike']} {c['type']} "
                  f"exp {c['expiry']} @ ${c['premium']}")
        print(f"Reasons: {', '.join(best['reasons'][:3])}")
    else:
        print("No strong setups found right now.")