import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, date
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# ── Black-Scholes Greeks ──────────────────────────────────────

def calculate_greeks(S, K, T, r, sigma, option_type='call'):
    try:
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return {'delta': 0, 'gamma': 0, 'theta': 0,
                    'vega': 0, 'prob_itm': 50, 'bs_price': 0}

        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        if option_type == 'call':
            delta    = norm.cdf(d1)
            theta    = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                        - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
            bs_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            prob_itm = norm.cdf(d2)
        else:
            delta    = norm.cdf(d1) - 1
            theta    = (-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
                        + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
            bs_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            prob_itm = norm.cdf(-d2)

        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega  = S * norm.pdf(d1) * np.sqrt(T) / 100

        return {
            'delta':    round(delta,    3),
            'gamma':    round(gamma,    4),
            'theta':    round(theta,    3),
            'vega':     round(vega,     3),
            'prob_itm': round(prob_itm * 100, 1),
            'bs_price': round(bs_price, 2)
        }
    except Exception as e:
        print(f"Greeks error: {e}")
        return {'delta': 0, 'gamma': 0, 'theta': 0,
                'vega': 0, 'prob_itm': 50, 'bs_price': 0}

def get_risk_free_rate():
    try:
        tnx  = yf.Ticker("^TNX")
        rate = tnx.history(period="1d")['Close'].iloc[-1] / 100
        return round(rate, 4)
    except:
        return 0.05

def days_to_expiry(expiry_str):
    try:
        expiry = datetime.strptime(str(expiry_str)[:10], "%Y-%m-%d").date()
        days   = (expiry - date.today()).days
        return max(1, days)
    except:
        return 30

# ── Max Pain ──────────────────────────────────────────────────

def calculate_max_pain(options_data, expiry):
    try:
        calls       = options_data[expiry]['calls']
        puts        = options_data[expiry]['puts']
        all_strikes = sorted(set(
            calls['strike'].tolist() + puts['strike'].tolist()))
        pain = {}
        for price in all_strikes:
            call_loss = sum(max(0, price - s) * oi
                           for s, oi in zip(calls['strike'], calls['openInterest']))
            put_loss  = sum(max(0, s - price) * oi
                           for s, oi in zip(puts['strike'],  puts['openInterest']))
            pain[price] = call_loss + put_loss
        return min(pain, key=pain.get)
    except:
        return None

# ── Put/Call Ratio ────────────────────────────────────────────

def get_put_call_ratio(options_data, expiry):
    try:
        calls    = options_data[expiry]['calls']
        puts     = options_data[expiry]['puts']
        call_vol = calls['volume'].sum()
        put_vol  = puts['volume'].sum()
        return round(put_vol / call_vol, 2) if call_vol > 0 else None
    except:
        return None

# ── Most Active Expiry ────────────────────────────────────────

def get_most_active_expiry(options_data):
    try:
        today       = date.today()
        best_expiry = None
        best_score  = -1

        for expiry, chain in options_data.items():
            try:
                expiry_date  = datetime.strptime(
                    str(expiry)[:10], "%Y-%m-%d").date()
                days_away    = (expiry_date - today).days
                if days_away < 1:
                    continue
                total_volume = (chain['calls']['volume'].sum() +
                                chain['puts']['volume'].sum())
                if 7 <= days_away <= 45:
                    score = total_volume * 3
                elif days_away < 7:
                    score = total_volume * 1
                else:
                    score = total_volume * 2
                if score > best_score:
                    best_score  = score
                    best_expiry = expiry
            except:
                continue

        if best_expiry is None:
            best_expiry = list(options_data.keys())[0]

        return best_expiry
    except Exception as e:
        print(f"Expiry error: {e}")
        return list(options_data.keys())[0]

# ── Best Option With Black-Scholes Greeks ─────────────────────

def get_best_options(options_data, current_price, signal, expiry=None, top_n=5):
    try:
        if expiry is None:
            expiry = get_most_active_expiry(options_data)

        r   = get_risk_free_rate()
        dte = days_to_expiry(expiry)
        T   = dte / 365

        # Gather options filtered by signal direction
        calls = options_data[expiry]['calls'].copy()
        puts  = options_data[expiry]['puts'].copy()
        calls['type'] = 'CALL'
        puts['type']  = 'PUT'

        if 'BUY' in signal:
            all_options = calls
        elif 'SELL' in signal:
            all_options = puts
        else:
            all_options = pd.concat([calls, puts], ignore_index=True)

        all_options = all_options[all_options['volume'] > 0].copy()

        if all_options.empty:
            return []

        results = []

        for _, row in all_options.iterrows():
            try:
                premium = round((row['bid'] + row['ask']) / 2, 2)
                if premium <= 0:
                    premium = float(row.get('lastPrice', 0.5))
                if premium <= 0:
                    continue

                option_type = 'call' if row['type'] == 'CALL' else 'put'

                iv_raw = row.get('impliedVolatility', 0)
                if iv_raw and float(iv_raw) > 0.01:
                    iv = float(iv_raw)
                elif dte <= 3:
                    iv = 0.45
                elif dte <= 7:
                    iv = 0.35
                elif dte <= 30:
                    iv = 0.28
                else:
                    iv = 0.25

                greeks = calculate_greeks(
                    S           = float(current_price),
                    K           = float(row['strike']),
                    T           = float(T),
                    r           = float(r),
                    sigma       = float(iv),
                    option_type = option_type
                )

                break_even = round(
                    row['strike'] + premium if option_type == 'call'
                    else row['strike'] - premium, 2)

                # Hard filters: eliminate weak or illiquid contracts before scoring.
                strike_dist = abs(float(row['strike']) - float(current_price)) / float(current_price)
                if strike_dist > 0.05:
                    continue

                delta_val = abs(greeks['delta'])
                if delta_val < 0.25 or delta_val > 0.75:
                    continue

                if greeks['prob_itm'] < 25:
                    continue

                if iv * 100 > 60:
                    continue

                if row['volume'] < 100:
                    continue

                if row['openInterest'] < 500:
                    continue

                spread = row['ask'] - row['bid']
                if spread > 0.50:
                    continue

                # Score each option
                # Higher volume = better liquidity
                # Delta 0.35-0.65 = sweet spot
                # Not too expensive, not too cheap
                volume_score  = min(100, row['volume'] / 1000 * 100)
                oi_score      = min(100, row['openInterest'] / 5000 * 100)
                delta_score   = 100 - abs(abs(greeks['delta']) - 0.5) * 200
                premium_score = 100 if 0.50 <= premium <= 5.00 else 50
                iv_score      = 100 if iv * 100 < 40 else 60

                total_score = (
                    volume_score  * 0.35 +
                    oi_score      * 0.25 +
                    delta_score   * 0.20 +
                    premium_score * 0.10 +
                    iv_score      * 0.10
                )

                results.append({
                    'rank':              0,
                    'expiry':            expiry,
                    'type':              row['type'],
                    'strike':            float(row['strike']),
                    'premium':           premium,
                    'contract_cost':     round(premium * 100, 2),
                    'bid':               round(float(row['bid']), 2),
                    'ask':               round(float(row['ask']), 2),
                    'volume':            int(row['volume']),
                    'open_interest':     int(row['openInterest']),
                    'iv':                round(iv * 100, 1),
                    'dte':               dte,
                    'delta':             greeks['delta'],
                    'gamma':             greeks['gamma'],
                    'theta':             greeks['theta'],
                    'vega':              greeks['vega'],
                    'prob_itm':          greeks['prob_itm'],
                    'bs_price':          greeks['bs_price'],
                    'break_even':        break_even,
                    'total_theta_burn':  round(abs(greeks['theta']) * dte, 2),
                    'score':             round(total_score, 1),
                    'risk_free_rate':    r
                })

            except Exception as e:
                continue

        # Sort by score
        results = sorted(results, key=lambda x: x['score'], reverse=True)

        # Add rank
        for i, opt in enumerate(results[:top_n]):
            opt['rank'] = i + 1

        return results[:top_n]

    except Exception as e:
        print(f"Best options error: {e}")
        return []

def get_best_option(options_data, current_price, signal, expiry=None):
    """Returns single best option for backward compatibility"""
    options = get_best_options(options_data, current_price, signal, expiry, top_n=5)
    return options[0] if options else None
    
# ── Options Flow ──────────────────────────────────────────────

def get_options_flow(options_data, expiry):
    try:
        calls           = options_data[expiry]['calls']
        puts            = options_data[expiry]['puts']
        top_call        = calls.nlargest(1, 'volume').iloc[0]
        top_put         = puts.nlargest(1,  'volume').iloc[0]
        highest_oi_call = calls.nlargest(1, 'openInterest').iloc[0]

        unusual = []
        for _, row in calls.iterrows():
            if row['volume'] > row['openInterest'] * 0.5 and row['volume'] > 500:
                unusual.append(
                    f"Call sweep ${row['strike']} — {int(row['volume'])} contracts")
        for _, row in puts.iterrows():
            if row['volume'] > row['openInterest'] * 0.5 and row['volume'] > 500:
                unusual.append(
                    f"Put sweep ${row['strike']} — {int(row['volume'])} contracts")

        return {
            'top_call_strike':   float(top_call['strike']),
            'top_call_volume':   int(top_call['volume']),
            'top_put_strike':    float(top_put['strike']),
            'top_put_volume':    int(top_put['volume']),
            'highest_oi_strike': float(highest_oi_call['strike']),
            'highest_oi':        int(highest_oi_call['openInterest']),
            'unusual_activity':  unusual[:3] if unusual else ['No unusual activity']
        }
    except:
        return {}

# ── Alternative Strategy ──────────────────────────────────────

def get_alternative_strategy(best_option, options_data, signal, current_price):
    try:
        if best_option is None:
            return None
        expiry = best_option['expiry']
        iv     = best_option['iv']
        if 'BUY' in signal and iv > 35:
            calls         = options_data[expiry]['calls']
            spread_strike = best_option['strike'] + 5
            spread_row    = calls[calls['strike'] == spread_strike]
            if not spread_row.empty:
                spread_premium = round(
                    (spread_row.iloc[0]['bid'] +
                     spread_row.iloc[0]['ask']) / 2, 2)
                net_cost   = round(
                    (best_option['premium'] - spread_premium) * 100, 2)
                max_profit = round(
                    (spread_strike - best_option['strike']) * 100 - net_cost, 2)
                return {
                    'strategy':   'Bull Call Spread',
                    'buy':        f"${best_option['strike']} Call",
                    'sell':       f"${spread_strike} Call",
                    'net_cost':   net_cost,
                    'max_profit': max_profit,
                    'reason':     f"IV at {iv}% — spread reduces cost & theta risk",
                    'savings':    round(best_option['contract_cost'] - net_cost, 2)
                }
        return None
    except:
        return None

# ── Test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    from data_engine      import get_all_data
    from indicator_engine import calculate_indicators, get_signals, calculate_score

    print("Testing Black-Scholes Greeks on AAPL...")
    data    = get_all_data("AAPL", "1h")
    df      = calculate_indicators(data['df'])
    signals = get_signals(df)
    signal, confidence, _, _ = calculate_score(signals)
    price   = signals['close']

    expiry   = get_most_active_expiry(data['options'])
    best_opt = get_best_option(data['options'], price, signal, expiry)

    if best_opt:
        print(f"\n✅ Black-Scholes Greeks working!")
        print(f"Strike:           ${best_opt['strike']}")
        print(f"Expiry:           {best_opt['expiry']} ({best_opt['dte']} days)")
        print(f"Premium:          ${best_opt['premium']}")
        print(f"IV:               {best_opt['iv']}%")
        print(f"Delta:            {best_opt['delta']}")
        print(f"Gamma:            {best_opt['gamma']}")
        print(f"Theta/day:        ${best_opt['theta']}")
        print(f"Vega:             {best_opt['vega']}")
        print(f"Prob ITM:         {best_opt['prob_itm']}%")
        print(f"Break even:       ${best_opt['break_even']}")
        print(f"Total theta burn: ${best_opt['total_theta_burn']}")
        print(f"BS fair price:    ${best_opt['bs_price']}")
    else:
        print("❌ No option returned")
