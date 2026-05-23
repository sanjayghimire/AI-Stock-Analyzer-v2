import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, date
import warnings
import pytz
warnings.filterwarnings('ignore')

def get_market_conditions():
    try:
        spy  = yf.Ticker("SPY")
        vix  = yf.Ticker("^VIX")
        qqq  = yf.Ticker("QQQ")

        spy_hist = spy.history(period="1y", interval="1d")
        vix_hist = vix.history(period="5d",  interval="1d")
        qqq_hist = qqq.history(period="1y", interval="1d")

        spy_close  = spy_hist['Close'].iloc[-1]
        spy_ema50  = spy_hist['Close'].ewm(span=50).mean().iloc[-1]
        spy_ema200 = spy_hist['Close'].ewm(span=200).mean().iloc[-1]
        vix_level  = vix_hist['Close'].iloc[-1]
        qqq_close  = qqq_hist['Close'].iloc[-1]
        qqq_ema50  = qqq_hist['Close'].ewm(span=50).mean().iloc[-1]

        spy_trend = ('BULLISH' if spy_close > spy_ema50 > spy_ema200
                     else 'BEARISH' if spy_close < spy_ema50 else 'NEUTRAL')

        if vix_level < 15:
            vix_status = 'Very Low — strong bull market'
            market_mood = 'Risk-ON'
        elif vix_level < 20:
            vix_status = 'Low — healthy market'
            market_mood = 'Risk-ON'
        elif vix_level < 30:
            vix_status = 'Elevated — caution'
            market_mood = 'Neutral'
        else:
            vix_status = 'HIGH — fear in market'
            market_mood = 'Risk-OFF'

        spy_1d_chg = ((spy_close - spy_hist['Close'].iloc[-2]) /
                       spy_hist['Close'].iloc[-2] * 100)

        return {
            'spy_price':    round(spy_close, 2),
            'spy_trend':    spy_trend,
            'spy_1d_chg':   round(spy_1d_chg, 2),
            'vix':          round(vix_level, 2),
            'vix_status':   vix_status,
            'market_mood':  market_mood,
            'qqq_trend':    'BULLISH' if qqq_close > qqq_ema50 else 'BEARISH',
            'good_for_calls': vix_level < 25 and spy_trend == 'BULLISH'
        }
    except Exception as e:
        print(f"Market data error: {e}")
        return {}

def get_sector_data(ticker):
    sector_etfs = {
        'Technology':           'XLK',
        'Healthcare':           'XLV',
        'Financials':           'XLF',
        'Consumer Discretionary':'XLY',
        'Industrials':          'XLI',
        'Energy':               'XLE',
        'Utilities':            'XLU',
        'Materials':            'XLB',
        'Real Estate':          'XLRE',
        'Communication':        'XLC',
        'Consumer Staples':     'XLP'
    }

    try:
        stock   = yf.Ticker(ticker)
        sector  = stock.info.get('sector', 'Technology')
        etf     = sector_etfs.get(sector, 'XLK')

        etf_hist   = yf.Ticker(etf).history(period="30d", interval="1d")
        etf_close  = etf_hist['Close'].iloc[-1]
        etf_ema20  = etf_hist['Close'].ewm(span=20).mean().iloc[-1]
        etf_1w_chg = ((etf_close - etf_hist['Close'].iloc[-5]) /
                       etf_hist['Close'].iloc[-5] * 100)
        etf_1m_chg = ((etf_close - etf_hist['Close'].iloc[0]) /
                       etf_hist['Close'].iloc[0] * 100)

        all_changes = {}
        for sec, sym in list(sector_etfs.items())[:5]:
            try:
                h = yf.Ticker(sym).history(period="5d", interval="1d")
                chg = ((h['Close'].iloc[-1] - h['Close'].iloc[-5]) /
                        h['Close'].iloc[-5] * 100)
                all_changes[sec] = round(chg, 2)
            except:
                pass

        hot_sector  = max(all_changes, key=all_changes.get) if all_changes else 'N/A'
        cold_sector = min(all_changes, key=all_changes.get) if all_changes else 'N/A'

        return {
            'sector':         sector,
            'sector_etf':     etf,
            'sector_trend':   'BULLISH' if etf_close > etf_ema20 else 'BEARISH',
            'sector_1w_chg':  round(etf_1w_chg, 2),
            'sector_1m_chg':  round(etf_1m_chg, 2),
            'hot_sector':     hot_sector,
            'cold_sector':    cold_sector,
            'sector_changes': all_changes
        }
    except Exception as e:
        print(f"Sector data error: {e}")
        return {}

def get_macro_calendar():
    today        = date.today()
    today_str    = today.strftime("%b %d")
    current_year = today.year

    events = [
        {'date': 'Apr 16', 'event': 'Retail Sales',           'impact': 'HIGH'},
        {'date': 'Apr 17', 'event': 'Jobless Claims',          'impact': 'MEDIUM'},
        {'date': 'Apr 23', 'event': 'PMI Flash',               'impact': 'MEDIUM'},
        {'date': 'Apr 30', 'event': 'Fed Meeting — FOMC',      'impact': 'VERY HIGH'},
        {'date': 'May 2',  'event': 'Jobs Report (NFP)',        'impact': 'VERY HIGH'},
        {'date': 'May 13', 'event': 'CPI Inflation Report',    'impact': 'VERY HIGH'},
    ]

    upcoming = []
    for e in events:
        try:
            event_date = datetime.strptime(
                f"{e['date']} {current_year}", "%b %d %Y").date()
            if event_date < today:
                event_date = datetime.strptime(
                    f"{e['date']} {current_year + 1}", "%b %d %Y").date()
        except Exception:
            event_date = today

        upcoming.append({
            'date':    event_date.strftime("%b %d, %Y"),
            'event':   e['event'],
            'impact':  e['impact'],
            'warning': e['impact'] in ['HIGH', 'VERY HIGH']
        })

    upcoming.sort(key=lambda x: datetime.strptime(x['date'], "%b %d, %Y"))
    next_high = next((e for e in upcoming if e['warning']), None)

    return {
        'events':     upcoming,
        'next_major': next_high,
        'today':      today_str
    }

def get_best_time_to_trade():
    eastern  = pytz.timezone('US/Eastern')
    now      = datetime.now(eastern)
    hour     = now.hour
    mins     = now.minute
    time_str = now.strftime("%I:%M %p ET")

    if hour < 9 or hour >= 16:
        window = 'CLOSED'; reason = 'Market is closed'
    elif hour == 9 and mins < 30:
        window = 'AVOID';  reason = 'Pre-open — market not yet open'
    elif (hour == 9 and mins >= 30) or (hour == 10 and mins < 30):
        window = 'AVOID';  reason = 'First 60 min — too volatile'
    elif (hour == 10 and mins >= 30) or hour == 11:
        window = 'BEST';   reason = 'Trend established — best entries'
    elif hour == 12 or hour == 13:
        window = 'AVOID';  reason = 'Lunch hours — low volume, choppy'
    elif hour == 14:
        window = 'GOOD';   reason = 'Institutions repositioning'
    elif hour == 15 and mins < 30:
        window = 'RISKY';  reason = 'End of day volatility building'
    else:
        window = 'AVOID';  reason = 'Closing manipulation — stay out'

    return {
        'current_time': time_str,
        'window':       window,
        'reason':       reason,
        'good_to_trade': window in ['BEST', 'GOOD']
    }

if __name__ == "__main__":
    print("Fetching market data...")

    market  = get_market_conditions()
    sector  = get_sector_data("AAPL")
    macro   = get_macro_calendar()
    timing  = get_best_time_to_trade()

    print(f"\n✅ Market engine working!")
    print(f"S&P 500:        {market.get('spy_trend')} | ${market.get('spy_price')}")
    print(f"VIX:            {market.get('vix')} — {market.get('vix_status')}")
    print(f"Market mood:    {market.get('market_mood')}")
    print(f"Good for calls: {market.get('good_for_calls')}")
    print(f"\nSector:         {sector.get('sector')} — {sector.get('sector_trend')}")
    print(f"Sector 1W:      {sector.get('sector_1w_chg')}%")
    print(f"Hot sector:     {sector.get('hot_sector')}")
    print(f"\nNext major event: {macro.get('next_major', {}).get('event')} on {macro.get('next_major', {}).get('date')}")
    print(f"\nCurrent time:   {timing.get('current_time')}")
    print(f"Trade window:   {timing.get('window')} — {timing.get('reason')}")