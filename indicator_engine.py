import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

def calculate_indicators(df):
    if df is None or len(df) < 200:
        return None
    
    d = df.copy()
    
    # ── EMA & SMA ──────────────────────────────
    d['ema9']   = d['close'].ewm(span=9).mean()
    d['ema21']  = d['close'].ewm(span=21).mean()
    d['ema50']  = d['close'].ewm(span=50).mean()
    d['ema200'] = d['close'].ewm(span=200).mean()
    d['sma20']  = d['close'].rolling(20).mean()

    # ── RSI ────────────────────────────────────
    delta = d['close'].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs    = gain / loss
    d['rsi'] = 100 - (100 / (1 + rs))

    # ── MACD ───────────────────────────────────
    ema12        = d['close'].ewm(span=12).mean()
    ema26        = d['close'].ewm(span=26).mean()
    d['macd']    = ema12 - ema26
    d['macd_signal'] = d['macd'].ewm(span=9).mean()
    d['macd_hist']   = d['macd'] - d['macd_signal']

    # ── Bollinger Bands ────────────────────────
    d['bb_mid']   = d['close'].rolling(20).mean()
    bb_std        = d['close'].rolling(20).std()
    d['bb_upper'] = d['bb_mid'] + (bb_std * 2)
    d['bb_lower'] = d['bb_mid'] - (bb_std * 2)
    d['bb_width'] = (d['bb_upper'] - d['bb_lower']) / d['bb_mid']

    # ── Stochastic ─────────────────────────────
    low14        = d['low'].rolling(14).min()
    high14       = d['high'].rolling(14).max()
    denom        = (high14 - low14).replace(0, np.nan)
    d['stoch_k'] = (100 * (d['close'] - low14) / denom).fillna(50)
    d['stoch_d'] = d['stoch_k'].rolling(3).mean()

    # ── ATR ────────────────────────────────────
    tr = pd.concat([
        d['high'] - d['low'],
        (d['high'] - d['close'].shift()).abs(),
        (d['low']  - d['close'].shift()).abs()
    ], axis=1).max(axis=1)
    d['atr'] = tr.rolling(14).mean()

    # ── ADX ────────────────────────────────────
    high_diff = d['high'].diff()
    low_diff  = (-d['low'].diff())
    plus_dm   = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0.0)
    minus_dm  = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0.0)
    atr14    = tr.rolling(14).mean()
    plus_di  = 100 * plus_dm.rolling(14).mean()  / atr14
    minus_di = 100 * minus_dm.rolling(14).mean() / atr14
    dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di))
    d['adx'] = dx.rolling(14).mean()

    # ── OBV ────────────────────────────────────
    d['obv'] = (np.sign(d['close'].diff()) * d['volume']).fillna(0).cumsum()

    # ── VWAP (resets each trading day) ─────────
    typical      = (d['high'] + d['low'] + d['close']) / 3
    tp_vol       = typical * d['volume']
    day_key      = d.index.normalize()
    d['vwap']    = (tp_vol.groupby(day_key).cumsum() /
                    d['volume'].groupby(day_key).cumsum())

    # ── ROC ────────────────────────────────────
    d['roc'] = d['close'].pct_change(10) * 100

    # ── Volume average ─────────────────────────
    d['vol_avg'] = d['volume'].rolling(20).mean()
    d['vol_ratio'] = d['volume'] / d['vol_avg']

    return d

def get_signals(df):
    if df is None or len(df) < 2:
        return {}

    latest = df.iloc[-1]
    prev   = df.iloc[-2]
    close  = latest['close']

    signals = {}

    # Trend signals
    signals['above_ema9']   = close > latest['ema9']
    signals['above_ema21']  = close > latest['ema21']
    signals['above_ema50']  = close > latest['ema50']
    signals['above_ema200'] = close > latest['ema200']
    signals['above_vwap']   = close > latest['vwap']
    signals['ema9_cross']   = (latest['ema9'] > latest['ema21']) and (prev['ema9'] <= prev['ema21'])
    signals['ema_bullish']  = latest['ema9'] > latest['ema21'] > latest['ema50']

    # Momentum signals
    signals['rsi']             = round(latest['rsi'], 1)
    signals['rsi_oversold']    = latest['rsi'] < 35
    signals['rsi_overbought']  = latest['rsi'] > 70
    signals['rsi_bullish']     = 40 < latest['rsi'] < 65
    signals['macd_bullish']    = latest['macd'] > latest['macd_signal']
    signals['macd_cross']      = (latest['macd'] > latest['macd_signal']) and (prev['macd'] <= prev['macd_signal'])
    signals['stoch_oversold']  = latest['stoch_k'] < 25
    signals['stoch_overbought']= latest['stoch_k'] > 80

    # Volatility signals
    signals['bb_squeeze']      = latest['bb_width'] < df['bb_width'].quantile(0.2)
    signals['near_bb_lower']   = close <= latest['bb_lower'] * 1.01
    signals['near_bb_upper']   = close >= latest['bb_upper'] * 0.99
    signals['adx']             = round(latest['adx'], 1)
    signals['strong_trend']    = latest['adx'] > 25
    signals['atr']             = round(latest['atr'], 2)

    # Volume signals
    signals['high_volume']     = latest['vol_ratio'] > 1.5
    signals['vol_ratio']       = round(latest['vol_ratio'], 2)
    signals['obv_rising']      = latest['obv'] > prev['obv']

    # Price action signals
    body       = abs(latest['close'] - latest['open'])
    upper_wick = latest['high'] - max(latest['close'], latest['open'])
    lower_wick = min(latest['close'], latest['open']) - latest['low']
    candle_range = latest['high'] - latest['low']

    signals['pin_bar_bull']    = lower_wick > body * 2 and lower_wick > upper_wick * 2
    signals['pin_bar_bear']    = upper_wick > body * 2 and upper_wick > lower_wick * 2
    signals['bull_engulf']     = (latest['close'] > latest['open'] and
                                   prev['close'] < prev['open'] and
                                   latest['close'] > prev['open'] and
                                   latest['open'] < prev['close'])
    signals['bear_engulf']     = (latest['close'] < latest['open'] and
                                   prev['close'] > prev['open'] and
                                   latest['close'] < prev['open'] and
                                   latest['open'] > prev['close'])
    signals['doji']            = body < candle_range * 0.1

    # Support & Resistance
    recent = df.tail(50)
    signals['resistance']  = round(recent['high'].max(), 2)
    signals['support']     = round(recent['low'].min(), 2)
    signals['pivot']       = round((latest['high'] + latest['low'] + latest['close']) / 3, 2)

    # Key prices
    signals['close']  = round(close, 2)
    signals['open']   = round(latest['open'], 2)
    signals['high']   = round(latest['high'], 2)
    signals['low']    = round(latest['low'], 2)
    signals['volume'] = int(latest['volume'])
    signals['vwap']   = round(latest['vwap'], 2)
    signals['atr']    = round(latest['atr'], 2)

    return signals

def calculate_score(signals):
    bull_points = 0
    bear_points = 0
    total       = 0

    checks = [
        ('above_ema9',    1), ('above_ema21',  2), ('above_ema50',  2),
        ('above_ema200',  3), ('ema_bullish',  2), ('ema9_cross',   3),
        ('above_vwap',    2), ('rsi_bullish',  2), ('rsi_oversold', 2),
        ('macd_bullish',  2), ('macd_cross',   3), ('high_volume',  1),
        ('obv_rising',    1), ('pin_bar_bull',  2), ('bull_engulf',  3),
        ('strong_trend',  1),
    ]

    bear_checks = [
        ('rsi_overbought', 2), ('near_bb_upper', 1), ('pin_bar_bear', 2),
        ('bear_engulf', 3),
    ]

    for key, weight in checks:
        if signals.get(key):
            bull_points += weight
        total += weight

    for key, weight in bear_checks:
        if signals.get(key):
            bear_points += weight

    net_score = bull_points - bear_points

    if net_score >= 10:
        signal = 'STRONG BUY'
        confidence = min(95, 60 + net_score * 2)
    elif net_score >= 5:
        signal = 'BUY'
        confidence = min(80, 50 + net_score * 2)
    elif net_score <= -5:
        signal = 'STRONG SELL'
        confidence = min(95, 60 + abs(net_score) * 2)
    elif net_score <= -2:
        signal = 'SELL'
        confidence = min(80, 50 + abs(net_score) * 2)
    else:
        signal = 'HOLD'
        confidence = 50

    return signal, confidence, bull_points, bear_points

if __name__ == "__main__":
    from data_engine import get_stock_data
    df, info = get_stock_data("AAPL", "1h")
    df = calculate_indicators(df)
    signals = get_signals(df)
    signal, confidence, bull, bear = calculate_score(signals)

    print(f"\n✅ Indicators calculated!")
    print(f"Signal:     {signal}")
    print(f"Confidence: {confidence}%")
    print(f"RSI:        {signals.get('rsi')}")
    print(f"ADX:        {signals.get('adx')}")
    print(f"MACD Bull:  {signals.get('macd_bullish')}")
    print(f"Above EMA200: {signals.get('above_ema200')}")
    print(f"Support:    ${signals.get('support')}")
    print(f"Resistance: ${signals.get('resistance')}")