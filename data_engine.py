import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import random
warnings.filterwarnings('ignore')

# ── Ticker Lookup ─────────────────────────────────────────────

COMPANY_NAMES = {
    # Tech
    'apple':       'AAPL', 'microsoft':   'MSFT', 'google':      'GOOGL',
    'alphabet':    'GOOGL', 'amazon':      'AMZN', 'meta':        'META',
    'facebook':    'META',  'netflix':     'NFLX', 'nvidia':      'NVDA',
    'tesla':       'TSLA',  'intel':       'INTC', 'amd':         'AMD',
    'salesforce':  'CRM',   'adobe':       'ADBE', 'zoom':        'ZM',
    'twitter':     'X',     'uber':        'UBER', 'lyft':        'LYFT',
    'airbnb':      'ABNB',  'snowflake':   'SNOW', 'palantir':    'PLTR',
    'coinbase':    'COIN',  'robinhood':   'HOOD', 'shopify':     'SHOP',
    'spotify':     'SPOT',  'pinterest':   'PINS', 'snap':        'SNAP',
    'oracle':      'ORCL',  'ibm':         'IBM',  'cisco':       'CSCO',
    'qualcomm':    'QCOM',  'broadcom':    'AVGO', 'micron':      'MU',
    'paypal':      'PYPL',  'square':      'SQ',   'block':       'SQ',
    'servicenow':  'NOW',   'workday':     'WDAY', 'datadog':     'DDOG',
    'crowdstrike': 'CRWD',  'okta':        'OKTA', 'twilio':      'TWLO',

    # Finance
    'jpmorgan':       'JPM',  'jp morgan':     'JPM',
    'goldman sachs':  'GS',   'goldman':        'GS',
    'morgan stanley': 'MS',   'bank of america':'BAC',
    'wells fargo':    'WFC',  'citigroup':      'C',
    'blackrock':      'BLK',  'visa':           'V',
    'mastercard':     'MA',   'american express':'AXP',
    'amex':           'AXP',

    # Healthcare
    'johnson and johnson': 'JNJ', 'johnson & johnson': 'JNJ',
    'pfizer':    'PFE',  'moderna':   'MRNA', 'merck':     'MRK',
    'abbvie':    'ABBV', 'unitedhealth': 'UNH', 'cvs':    'CVS',
    'eli lilly': 'LLY',  'lilly':     'LLY',  'novo nordisk': 'NVO',

    # Consumer
    'walmart':    'WMT',  'target':      'TGT',  'costco':    'COST',
    'mcdonalds':  'MCD',  'starbucks':   'SBUX', 'nike':      'NKE',
    'coca cola':  'KO',   'pepsi':       'PEP',  'pepsico':   'PEP',
    'disney':     'DIS',  'comcast':     'CMCSA','netflix':   'NFLX',
    'home depot': 'HD',   'lowes':       'LOW',

    # Energy
    'exxon':      'XOM',  'chevron':     'CVX',  'shell':     'SHEL',
    'bp':         'BP',   'conocophillips': 'COP',

    # ETFs
    'spy':        'SPY',  's&p 500':     'SPY',  'sp500':     'SPY',
    'qqq':        'QQQ',  'nasdaq':      'QQQ',  'dow jones': 'DIA',
    'dia':        'DIA',  'iwm':         'IWM',  'russell':   'IWM',
    'vix':        '^VIX',

    # Other
    'berkshire':  'BRK-B', 'warren buffett': 'BRK-B',
    'spacex':     'TSLA',  'elon musk':      'TSLA',
    'boeing':     'BA',    'lockheed':       'LMT',
    'caterpillar':'CAT',   'deere':          'DE',
}

def resolve_ticker(input_text):
    """
    Converts company name or symbol to proper ticker
    Examples:
      'apple'     -> 'AAPL'
      'AAPL'      -> 'AAPL'
      'Apple Inc' -> 'AAPL'
      'microsoft' -> 'MSFT'
    """
    if not input_text:
        return None

    cleaned = input_text.strip().lower()

    # Direct match in our dictionary
    if cleaned in COMPANY_NAMES:
        return COMPANY_NAMES[cleaned]

    # Partial match — check if input contains a known name
    for name, ticker in COMPANY_NAMES.items():
        if name in cleaned:
            return ticker

    # If nothing found assume it's already a valid ticker symbol
    return input_text.strip().upper()

def get_stock_data(ticker, interval='1h', period='60d'):
    try:
        if interval in ['1m', '2m', '5m', '15m', '30m']:
            period = '7d'
        elif interval in ['1h']:
            period = '60d'
        elif interval in ['4h']:
            period = '60d'
        else:
            period = '1y'

        # Random delay to avoid rate limiting
        time.sleep(random.uniform(1, 3))

        stock = yf.Ticker(ticker)
        df    = stock.history(period=period, interval=interval)

        if df.empty:
            # Fallback to daily if intraday fails
            time.sleep(2)
            df = stock.history(period='1y', interval='1d')

        if df.empty:
            return None, None

        df.index   = pd.to_datetime(df.index)
        df         = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        df         = df.dropna()

        # Get info with retry
        info = {}
        for attempt in range(3):
            try:
                info = stock.info
                if info:
                    break
            except:
                time.sleep(2)

        return df, info

    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return None, None

def get_premarket_data(ticker):
    try:
        time.sleep(random.uniform(0.5, 1.5))
        stock    = yf.Ticker(ticker)
        info     = stock.fast_info

        try:
            pre_market_price = getattr(info, 'pre_market_price', None)
            regular_price    = getattr(info, 'last_price', None)
            previous_close   = getattr(info, 'previous_close', None)
        except:
            pre_market_price = None
            regular_price    = None
            previous_close   = None

        if pre_market_price and previous_close:
            gap     = pre_market_price - previous_close
            gap_pct = (gap / previous_close) * 100
            gap_dir = 'GAP UP' if gap > 0 else 'GAP DOWN' if gap < 0 else 'FLAT'
        else:
            gap     = 0
            gap_pct = 0
            gap_dir = 'No gap data'

        return {
            'pre_market_price': pre_market_price,
            'regular_price':    regular_price,
            'previous_close':   previous_close,
            'gap':              round(gap, 2),
            'gap_pct':          round(gap_pct, 2),
            'gap_direction':    gap_dir
        }
    except Exception as e:
        print(f"Error fetching premarket data: {e}")
        return {
            'pre_market_price': None, 'regular_price': None,
            'previous_close': None, 'gap': 0,
            'gap_pct': 0, 'gap_direction': 'No gap data'
        }

def get_options_data(ticker):
    try:
        time.sleep(random.uniform(0.5, 1.5))
        stock       = yf.Ticker(ticker)
        expirations = stock.options

        if not expirations:
            return None, None

        options_data = {}
        for exp in expirations[:6]:
            try:
                opt_chain          = stock.option_chain(exp)
                options_data[exp]  = {
                    'calls': opt_chain.calls,
                    'puts':  opt_chain.puts
                }
                time.sleep(0.5)
            except:
                continue

        return (options_data if options_data else None), expirations
    except Exception as e:
        print(f"Error fetching options data: {e}")
        return None, None

def get_analyst_data(ticker):
    try:
        time.sleep(random.uniform(0.5, 1))
        stock = yf.Ticker(ticker)
        info  = stock.info

        return {
            'target_mean':    info.get('targetMeanPrice',          None),
            'target_high':    info.get('targetHighPrice',          None),
            'target_low':     info.get('targetLowPrice',           None),
            'recommendation': info.get('recommendationKey',        None),
            'num_analysts':   info.get('numberOfAnalystOpinions',  None)
        }
    except Exception as e:
        print(f"Error fetching analyst data: {e}")
        return {
            'target_mean': None, 'target_high': None,
            'target_low': None, 'recommendation': None,
            'num_analysts': None
        }

def get_earnings_date(ticker):
    try:
        stock    = yf.Ticker(ticker)
        calendar = stock.calendar

        earnings_date = None
        if isinstance(calendar, dict):
            earnings_date = calendar.get('Earnings Date')
            if isinstance(earnings_date, list):
                earnings_date = earnings_date[0]
        elif isinstance(calendar, pd.DataFrame) and not calendar.empty:
            earnings_date = calendar.iloc[0].get('Earnings Date', None)

        if earnings_date:
            days_until = (pd.Timestamp(earnings_date) -
                          pd.Timestamp.now()).days
            return {
                'earnings_date': str(earnings_date),
                'days_until':    days_until,
                'warning':       days_until <= 14
            }
        return {'earnings_date': 'Unknown', 'days_until': 999, 'warning': False}
    except:
        return {'earnings_date': 'Unknown', 'days_until': 999, 'warning': False}

def get_all_data(ticker, interval='1h'):
    print(f"Fetching data for {ticker}...")

    df, info = get_stock_data(ticker, interval)

    if df is None:
        print(f"Primary fetch failed — retrying {ticker}...")
        time.sleep(3)
        df, info = get_stock_data(ticker, '1d')

    premarket  = get_premarket_data(ticker)
    time.sleep(1)
    options, expirations = get_options_data(ticker)
    time.sleep(1)
    analyst    = get_analyst_data(ticker)
    earnings   = get_earnings_date(ticker)

    return {
        'df':          df,
        'info':        info,
        'premarket':   premarket,
        'options':     options,
        'expirations': expirations,
        'analyst':     analyst,
        'earnings':    earnings,
        'ticker':      ticker,
        'interval':    interval
    }

if __name__ == "__main__":
    data = get_all_data("AAPL", "1d")

    if data['df'] is not None:
        print(f"✅ Stock data fetched!")
        print(f"Rows: {len(data['df'])}")
        print(f"Latest price: ${data['df']['close'].iloc[-1]:.2f}")
    else:
        print("❌ Failed to fetch data")