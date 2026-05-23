import json
import os
from datetime import datetime

TRACKER_FILE  = "trades.json"
RULES_FILE    = "learned_rules.json"
PATTERNS_FILE = "patterns.json"

# ── Data helpers ──────────────────────────────────────────────

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default
    return default

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def load_trades():   return load_json(TRACKER_FILE,  [])
def load_rules():    return load_json(RULES_FILE,    [])
def load_patterns(): return load_json(PATTERNS_FILE, {})

# ── Log a new trade ───────────────────────────────────────────

def log_trade(ticker, signal, entry_price, strike, expiry,
              premium, contracts, stop_loss, tp1, tp2, tp3,
              swing_score, confidence, setup_tags=None, notes=""):
    trades = load_trades()
    trade  = {
        'id':           max((t['id'] for t in trades), default=0) + 1,
        'date':         datetime.now().strftime("%Y-%m-%d %H:%M"),
        'ticker':       ticker,
        'signal':       signal,
        'entry_price':  entry_price,
        'strike':       strike,
        'expiry':       expiry,
        'premium':      premium,
        'contracts':    contracts,
        'cost':         round(premium * contracts * 100, 2),
        'stop_loss':    stop_loss,
        'tp1':          tp1,
        'tp2':          tp2,
        'tp3':          tp3,
        'swing_score':  swing_score,
        'confidence':   confidence,
        'setup_tags':   setup_tags or [],
        'notes':        notes,
        'status':       'OPEN',
        'exit_price':   None,
        'exit_premium': None,
        'pnl':          None,
        'result':       None,
        'exit_date':    None,
        'feedback':     None,
        'what_went_wrong': None
    }
    trades.append(trade)
    save_json(TRACKER_FILE, trades)
    print(f"✅ Trade #{trade['id']} logged: {ticker} {signal}")
    return trade['id']

# ── Close a trade + capture feedback ─────────────────────────

def close_trade(trade_id, exit_price, exit_premium,
                result, feedback="", what_went_wrong=""):
    trades = load_trades()
    for trade in trades:
        if trade['id'] == trade_id:
            pnl = round((exit_premium - trade['premium']) *
                         trade['contracts'] * 100, 2)
            trade.update({
                'status':          'CLOSED',
                'exit_price':      exit_price,
                'exit_premium':    exit_premium,
                'pnl':             pnl,
                'result':          result,
                'exit_date':       datetime.now().strftime("%Y-%m-%d %H:%M"),
                'feedback':        feedback,
                'what_went_wrong': what_went_wrong
            })
            save_json(TRACKER_FILE, trades)
            print(f"✅ Trade #{trade_id} closed | PnL: ${pnl} | {result}")
            _update_patterns(trade)
            _auto_generate_rules()
            return pnl
    print(f"Trade #{trade_id} not found")
    return None

# ── Pattern detection ─────────────────────────────────────────

def _update_patterns(trade):
    patterns = load_patterns()
    tags     = trade.get('setup_tags', [])
    ticker   = trade['ticker']
    won      = trade['pnl'] >= 0

    # Per-tag win rate
    for tag in tags:
        if tag not in patterns:
            patterns[tag] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
        patterns[tag]['trades']    += 1
        patterns[tag]['total_pnl'] += trade['pnl']
        if won:
            patterns[tag]['wins'] += 1

    # Per-ticker win rate
    tk_key = f"ticker_{ticker}"
    if tk_key not in patterns:
        patterns[tk_key] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
    patterns[tk_key]['trades']    += 1
    patterns[tk_key]['total_pnl'] += trade['pnl']
    if won:
        patterns[tk_key]['wins'] += 1

    # Swing score buckets
    score = trade.get('swing_score', 0)
    bucket = f"swing_{(score // 2) * 2}_{(score // 2) * 2 + 2}"
    if bucket not in patterns:
        patterns[bucket] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
    patterns[bucket]['trades']    += 1
    patterns[bucket]['total_pnl'] += trade['pnl']
    if won:
        patterns[bucket]['wins'] += 1

    save_json(PATTERNS_FILE, patterns)

# ── Auto-generate rules from patterns ────────────────────────

def _auto_generate_rules():
    patterns = load_patterns()
    trades   = load_trades()
    closed   = [t for t in trades if t['status'] == 'CLOSED']
    rules    = []

    for key, data in patterns.items():
        if data['trades'] < 3:
            continue
        win_rate = data['wins'] / data['trades'] * 100

        if win_rate >= 70:
            rules.append({
                'type':      'BOOST',
                'pattern':   key,
                'win_rate':  round(win_rate, 1),
                'trades':    data['trades'],
                'rule':      f"Setup '{key}' has {round(win_rate,1)}% win rate "
                             f"over {data['trades']} trades — increase confidence by 10%",
                'confidence_adj': +10
            })
        elif win_rate <= 35:
            rules.append({
                'type':      'REDUCE',
                'pattern':   key,
                'win_rate':  round(win_rate, 1),
                'trades':    data['trades'],
                'rule':      f"Setup '{key}' has only {round(win_rate,1)}% win rate "
                             f"over {data['trades']} trades — reduce confidence by 15% or AVOID",
                'confidence_adj': -15
            })

    # Day of week patterns
    from collections import defaultdict
    day_stats = defaultdict(lambda: {'trades': 0, 'wins': 0})
    for t in closed:
        try:
            day = datetime.strptime(t['date'], "%Y-%m-%d %H:%M").strftime("%A")
            day_stats[day]['trades'] += 1
            if t['pnl'] > 0:
                day_stats[day]['wins'] += 1
        except:
            pass

    for day, stats in day_stats.items():
        if stats['trades'] >= 3:
            wr = stats['wins'] / stats['trades'] * 100
            if wr <= 30:
                rules.append({
                    'type':    'DAY_AVOID',
                    'pattern': day,
                    'win_rate': round(wr, 1),
                    'trades':  stats['trades'],
                    'rule':    f"You lose {round(100-wr,1)}% of trades on {day}s — consider avoiding",
                    'confidence_adj': -20
                })

    save_json(RULES_FILE, rules)
    return rules

# ── Get confidence adjustment for current setup ───────────────

def get_confidence_adjustment(ticker, setup_tags):
    rules     = load_rules()
    patterns  = load_patterns()
    total_adj = 0
    applied   = []
    today_name = datetime.now().strftime("%A")

    for rule in rules:
        pattern = rule['pattern']
        adj     = rule['confidence_adj']

        if pattern in setup_tags:
            total_adj += adj
            applied.append(rule['rule'])
        elif pattern == f"ticker_{ticker}":
            total_adj += adj // 2
            applied.append(f"Your {ticker} track record: {rule['win_rate']}% win rate")
        elif pattern == today_name:
            total_adj += adj
            applied.append(rule['rule'])

    return total_adj, applied

# ── Build learned rules prompt injection ─────────────────────

def get_rules_for_prompt():
    rules    = load_rules()
    patterns = load_patterns()
    trades   = load_trades()
    closed   = [t for t in trades if t['status'] == 'CLOSED']

    if not closed:
        return ""

    lines = ["\n=== YOUR PERSONAL TRADING HISTORY (learned from real trades) ==="]
    lines.append(f"Total closed trades: {len(closed)}")

    wins     = [t for t in closed if t['pnl'] > 0]
    win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0
    total_pnl= round(sum(t['pnl'] for t in closed), 2)
    lines.append(f"Personal win rate: {win_rate}% | Total PnL: ${total_pnl}")

    if rules:
        lines.append("\nLEARNED RULES FROM YOUR REAL TRADES:")
        for i, rule in enumerate(rules[:8], 1):
            lines.append(f"{i}. {rule['rule']}")

    feedbacks = [t['what_went_wrong'] for t in closed
                 if t.get('what_went_wrong') and len(t['what_went_wrong']) > 5]
    if feedbacks:
        lines.append("\nRECENT TRADER FEEDBACK:")
        for fb in feedbacks[-3:]:
            lines.append(f"- {fb}")

    lines.append("\nApply these personal patterns to adjust your final verdict and confidence.")
    return "\n".join(lines)

# ── Stats ─────────────────────────────────────────────────────

def get_stats():
    trades = load_trades()
    closed = [t for t in trades if t['status'] == 'CLOSED']

    if not closed:
        return {
            'total_trades':  0, 'wins': 0, 'losses': 0,
            'win_rate': 0, 'total_pnl': 0, 'avg_win': 0,
            'avg_loss': 0, 'profit_factor': 0,
            'best_trade': 0, 'worst_trade': 0,
            'open_trades': len([t for t in trades if t['status'] == 'OPEN'])
        }

    wins         = [t for t in closed if t['pnl'] > 0]
    losses       = [t for t in closed if t['pnl'] <= 0]
    total_pnl    = round(sum(t['pnl'] for t in closed), 2)
    avg_win      = round(sum(t['pnl'] for t in wins)   / len(wins)   if wins   else 0, 2)
    avg_loss     = round(sum(t['pnl'] for t in losses) / len(losses) if losses else 0, 2)
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss   = abs(sum(t['pnl'] for t in losses))
    profit_factor= round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999.99
    best         = max(closed, key=lambda x: x['pnl'])
    worst        = min(closed, key=lambda x: x['pnl'])

    return {
        'total_trades':  len(closed),
        'open_trades':   len([t for t in trades if t['status'] == 'OPEN']),
        'wins':          len(wins),
        'losses':        len(losses),
        'win_rate':      round(len(wins) / len(closed) * 100, 1),
        'total_pnl':     total_pnl,
        'avg_win':       avg_win,
        'avg_loss':      avg_loss,
        'profit_factor': profit_factor,
        'best_trade':    round(best['pnl'], 2),
        'worst_trade':   round(worst['pnl'], 2),
        'best_ticker':   best['ticker'],
        'worst_ticker':  worst['ticker'],
        'learned_rules': len(load_rules())
    }

def get_open_trades():
    return [t for t in load_trades() if t['status'] == 'OPEN']

# ── Test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulate 3 trades with feedback
    id1 = log_trade("AAPL", "BUY CALL", 262.48, 265.0, "2026-04-17",
                    0.94, 2, 246.16, 266.55, 270.41, 276.20, 7, 90,
                    setup_tags=["ema_cross", "high_volume"],
                    notes="Strong technicals")
    close_trade(id1, 270.0, 1.88, "WIN",
                feedback="Worked perfectly",
                what_went_wrong="Nothing — clean trade")

    id2 = log_trade("AAPL", "BUY CALL", 263.0, 265.0, "2026-04-17",
                    1.10, 1, 246.16, 266.55, 270.41, 276.20, 6, 78,
                    setup_tags=["low_volume", "earnings_risk"],
                    notes="Risky near earnings")
    close_trade(id2, 258.0, 0.40, "LOSS",
                feedback="Should have waited",
                what_went_wrong="Low volume breakout failed — volume ratio was 0.32x, "
                                "distribution not accumulation. Never buy low volume breakouts.")

    id3 = log_trade("TSLA", "BUY CALL", 245.0, 250.0, "2026-04-25",
                    2.50, 1, 235.0, 252.0, 258.0, 265.0, 8, 85,
                    setup_tags=["ema_cross", "low_volume"],
                    notes="Good setup but low volume concern")
    close_trade(id3, 240.0, 0.80, "LOSS",
                feedback="Low volume again — need to stop trading low volume setups",
                what_went_wrong="Low volume breakout failed again. This is a pattern — "
                                "volume ratio below 0.5x means institutions aren't buying.")

    stats = get_stats()
    rules = load_rules()

    print(f"\n📊 YOUR TRADING STATS")
    print(f"Total trades:    {stats['total_trades']}")
    print(f"Win rate:        {stats['win_rate']}%")
    print(f"Total PnL:       ${stats['total_pnl']}")
    print(f"Avg win:         ${stats['avg_win']}")
    print(f"Avg loss:        ${stats['avg_loss']}")
    print(f"Learned rules:   {stats['learned_rules']}")

    print(f"\n🧠 LEARNED RULES:")
    for rule in rules:
        print(f"  {rule['type']}: {rule['rule']}")

    print(f"\n💬 PROMPT INJECTION PREVIEW:")
    print(get_rules_for_prompt())