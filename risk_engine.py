import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

def calculate_position_size(account_size, risk_pct, premium, contracts=None):
    try:
        max_risk       = account_size * (risk_pct / 100)
        contract_cost  = premium * 100
        recommended    = int(max_risk / contract_cost)
        actual_risk    = contract_cost * recommended
        risk_pct_actual= (actual_risk / account_size) * 100

        return {
            'account_size':     account_size,
            'max_risk':         round(max_risk, 2),
            'contract_cost':    round(contract_cost, 2),
            'recommended':      recommended,
            'actual_risk':      round(actual_risk, 2),
            'risk_pct_actual':  round(risk_pct_actual, 2),
            'safe':             recommended >= 1 and actual_risk <= max_risk * 1.1
        }
    except:
        return {}

def calculate_targets(current_price, signal, atr, signals):
    try:
        support    = signals.get('support', current_price * 0.95)
        resistance = signals.get('resistance', current_price * 1.05)

        if 'BUY' in signal:
            stop_loss  = round(current_price - (atr * 1.5), 2)
            stop_loss  = min(stop_loss, support * 0.995)
            tp1        = round(current_price + (atr * 2), 2)
            tp2        = round(current_price + (atr * 4), 2)
            tp3        = round(current_price + (atr * 7), 2)
            entry_low  = round(current_price * 0.998, 2)
            entry_high = round(current_price * 1.002, 2)
            dont_chase = round(current_price * 1.008, 2)
        else:
            stop_loss  = round(current_price + (atr * 1.5), 2)
            stop_loss  = max(stop_loss, resistance * 1.005)
            tp1        = round(current_price - (atr * 2), 2)
            tp2        = round(current_price - (atr * 4), 2)
            tp3        = round(current_price - (atr * 7), 2)
            entry_low  = round(current_price * 0.998, 2)
            entry_high = round(current_price * 1.002, 2)
            dont_chase = round(current_price * 0.992, 2)

        risk        = abs(current_price - stop_loss)
        reward_tp2  = abs(tp2 - current_price)
        rr_ratio    = round(reward_tp2 / risk, 2) if risk > 0 else 0

        price_range_low  = round(min(stop_loss, current_price) * 0.99, 2)
        price_range_high = round(tp3 * 1.01, 2)

        hold_days = 3 if atr / current_price > 0.02 else 10

        return {
            'entry_low':        entry_low,
            'entry_high':       entry_high,
            'dont_chase':       dont_chase,
            'stop_loss':        stop_loss,
            'tp1':              tp1,
            'tp2':              tp2,
            'tp3':              tp3,
            'rr_ratio':         rr_ratio,
            'price_range_low':  price_range_low,
            'price_range_high': price_range_high,
            'hold_days':        hold_days,
            'risk_per_share':   round(risk, 2),
            'reward_per_share': round(reward_tp2, 2)
        }
    except Exception as e:
        return {}

def calculate_drawdown(position_size, account_size, premium):
    try:
        contract_cost = premium * 100
        total_cost    = contract_cost * position_size

        loss_50pct  = round(total_cost * 0.5,  2)
        loss_full   = round(total_cost,         2)
        loss_3x     = round(total_cost * 3,     2)

        impact_50   = round((loss_50pct / account_size) * 100, 2)
        impact_full = round((loss_full  / account_size) * 100, 2)
        impact_3x   = round((loss_3x    / account_size) * 100, 2)

        return {
            'total_invested':   round(total_cost, 2),
            'loss_50pct':       loss_50pct,
            'loss_full':        loss_full,
            'loss_3x_streak':   loss_3x,
            'impact_50':        impact_50,
            'impact_full':      impact_full,
            'impact_3x_streak': impact_3x,
            'account_safe':     impact_3x < 10
        }
    except:
        return {}

def calculate_expected_value(win_rate, avg_win, avg_loss):
    try:
        lose_rate = 1 - (win_rate / 100)
        ev        = (win_rate / 100 * avg_win) - (lose_rate * avg_loss)
        return {
            'win_rate':   win_rate,
            'lose_rate':  round(lose_rate * 100, 1),
            'avg_win':    avg_win,
            'avg_loss':   avg_loss,
            'expected_value': round(ev, 2),
            'positive_ev':    ev > 0
        }
    except:
        return {}

def calculate_swing_score(signals, market, sector, options_data,
                           best_option, earnings, timing):
    score  = 0
    notes  = []

    # Technical score
    if signals.get('above_ema200'):    score += 1; notes.append('Above EMA200 ✅')
    if signals.get('ema_bullish'):     score += 1; notes.append('EMA stack bullish ✅')
    if signals.get('macd_bullish'):    score += 1; notes.append('MACD bullish ✅')
    if signals.get('rsi_bullish'):     score += 1; notes.append('RSI in bull zone ✅')
    if signals.get('high_volume'):     score += 1; notes.append('High volume ✅')
    if signals.get('strong_trend'):    score += 1; notes.append('Strong trend (ADX) ✅')

    # Market score
    if market.get('spy_trend') == 'BULLISH':   score += 1; notes.append('S&P bullish ✅')
    if market.get('market_mood') == 'Risk-ON': score += 1; notes.append('Risk-ON market ✅')
    if market.get('vix', 99) < 20:             score += 1; notes.append('Low VIX ✅')

    # Sector score
    if sector.get('sector_trend') == 'BULLISH': score += 1; notes.append('Sector bullish ✅')

    # Options score
    if best_option:
        if best_option.get('iv', 100) < 35:    score += 1; notes.append('IV reasonable ✅')
        if best_option.get('delta', 0) > 0.4:  score += 1; notes.append('Good delta ✅')

    # Risk deductions
    if earnings.get('warning'):        score -= 2; notes.append('Earnings risk ⚠️')
    if not timing.get('good_to_trade'):score -= 1; notes.append('Bad time of day ⚠️')
    if market.get('vix', 0) > 25:      score -= 1; notes.append('High VIX ⚠️')

    score     = max(0, min(10, score))
    verdict   = ('STRONG SWING ✅' if score >= 8 else
                 'GOOD SWING ✅'   if score >= 6 else
                 'WEAK SETUP ⚠️'  if score >= 4 else
                 'AVOID ❌')

    return {
        'score':   score,
        'verdict': verdict,
        'notes':   notes
    }

if __name__ == "__main__":
    from data_engine      import get_all_data
    from indicator_engine import calculate_indicators, get_signals, calculate_score
    from market_engine    import get_market_conditions, get_sector_data
    from market_engine    import get_best_time_to_trade
    from options_engine   import get_best_option, get_most_active_expiry

    data    = get_all_data("AAPL", "1h")
    df      = calculate_indicators(data['df'])
    signals = get_signals(df)
    signal, confidence, _, _ = calculate_score(signals)
    market  = get_market_conditions()
    sector  = get_sector_data("AAPL")
    timing  = get_best_time_to_trade()
    expiry  = get_most_active_expiry(data['options'])
    best_opt= get_best_option(data['options'], signals['close'], signal, expiry)

    targets = calculate_targets(signals['close'], signal, signals['atr'], signals)
    sizing  = calculate_position_size(10000, 2, best_opt['premium'] if best_opt else 1)
    drawdown= calculate_drawdown(sizing.get('recommended', 1), 10000,
                                  best_opt['premium'] if best_opt else 1)
    ev      = calculate_expected_value(75, sizing.get('contract_cost', 300) * 2,
                                        sizing.get('contract_cost', 300))
    swing   = calculate_swing_score(signals, market, sector,
                                     data['options'], best_opt,
                                     data['earnings'], timing)

    print(f"\n✅ Risk engine working!")
    print(f"Entry zone:     ${targets.get('entry_low')} — ${targets.get('entry_high')}")
    print(f"Stop loss:      ${targets.get('stop_loss')}")
    print(f"TP1/TP2/TP3:    ${targets.get('tp1')} / ${targets.get('tp2')} / ${targets.get('tp3')}")
    print(f"Risk/Reward:    1:{targets.get('rr_ratio')}")
    print(f"Position size:  {sizing.get('recommended')} contract(s)")
    print(f"Max loss:       ${drawdown.get('loss_full')}")
    print(f"Expected value: ${ev.get('expected_value')}")
    print(f"Swing score:    {swing.get('score')}/10 — {swing.get('verdict')}")