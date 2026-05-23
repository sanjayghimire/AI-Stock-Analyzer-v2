import streamlit as st
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# ── Engine Imports ────────────────────────────────────────────
from data_engine      import get_all_data, resolve_ticker
from indicator_engine import calculate_indicators, get_signals, calculate_score
from market_engine    import (get_market_conditions, get_sector_data,
                               get_macro_calendar, get_best_time_to_trade)
from options_engine   import (get_best_option, get_best_options,
                               get_most_active_expiry, get_alternative_strategy,
                               get_options_flow, calculate_max_pain,
                               get_put_call_ratio)
from risk_engine      import (calculate_targets, calculate_position_size,
                               calculate_drawdown, calculate_expected_value,
                               calculate_swing_score)
from ai_engine        import get_ai_analysis
from scanner_engine   import run_quick_scan, run_scanner

def is_market_open():
    """Check if US market is currently open — CST times"""
    import pytz
    eastern = pytz.timezone('US/Eastern')
    now     = datetime.now(eastern)
    if now.weekday() >= 5:
        return False, "Market closed — weekend"
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    if now < market_open:
        return False, "Market opens at 8:30 AM CST"
    elif now > market_close:
        return False, "Market closed at 3:00 PM CST"
    else:
        return True, "Market is open"
from notifier         import (alert_take_profit, alert_stop_loss,
                               alert_exit_signal, alert_theta_warning)
from tracker          import (get_stats, get_open_trades, log_trade,
                               close_trade, get_rules_for_prompt,
                               get_confidence_adjustment)
import anthropic

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title = "AI Stock Analyzer",
    page_icon  = "📈",
    layout     = "wide"
)

# ── Styles ────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #080c14;
}

.stApp {
    background: #080c14;
    background-image:
        radial-gradient(ellipse at 20% 0%, rgba(0,255,136,0.04) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 0%, rgba(0,149,255,0.04) 0%, transparent 50%);
}

/* ── Hide streamlit branding ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #1a2535; border-radius: 2px; }

/* ── Typography ── */
h1, h2, h3 {
    font-family: 'Rajdhani', sans-serif;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

/* ── App Header ── */
.app-header {
    background: linear-gradient(135deg, #0d1117 0%, #0a1628 100%);
    border: 1px solid #1a2535;
    border-radius: 12px;
    padding: 20px 28px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
    position: relative;
    overflow: hidden;
}
.app-header::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #00ff88, #0095ff, transparent);
}
.app-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px;
    font-weight: 700;
    color: #e2e8f0;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin: 0;
}
.app-subtitle {
    font-size: 11px;
    color: #4a5568;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    font-family: 'Share Tech Mono', monospace;
}

/* ── Market Status Badge ── */
.status-open {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,255,136,0.1);
    border: 1px solid rgba(0,255,136,0.3);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 11px;
    font-family: 'Share Tech Mono', monospace;
    color: #00ff88;
    letter-spacing: 0.1em;
}
.status-open::before {
    content: '';
    width: 6px; height: 6px;
    background: #00ff88;
    border-radius: 50%;
    animation: pulse 2s infinite;
}
.status-closed {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 11px;
    font-family: 'Share Tech Mono', monospace;
    color: #ef4444;
    letter-spacing: 0.1em;
}
.status-closed::before {
    content: '';
    width: 6px; height: 6px;
    background: #ef4444;
    border-radius: 50%;
}

@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0,255,136,0.4); }
    50% { opacity: 0.8; box-shadow: 0 0 0 4px rgba(0,255,136,0); }
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #0d1117;
    border-radius: 8px;
    padding: 4px;
    gap: 2px;
    border: 1px solid #1a2535;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border-radius: 6px;
    color: #4a5568;
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 8px 16px;
    transition: all 0.2s;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #94a3b8;
    background: rgba(255,255,255,0.04);
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0a2a1a, #0a1628) !important;
    color: #00ff88 !important;
    border: 1px solid rgba(0,255,136,0.2) !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: #0d1117;
    border: 1px solid #1a2535;
    border-radius: 8px;
    padding: 12px 16px;
    transition: border-color 0.2s;
}
[data-testid="metric-container"]:hover {
    border-color: #2a3545;
}
[data-testid="stMetricLabel"] {
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: #4a5568 !important;
    letter-spacing: 0.15em;
    text-transform: uppercase;
}
[data-testid="stMetricValue"] {
    font-family: 'Rajdhani', sans-serif;
    font-size: 22px;
    font-weight: 700;
    color: #e2e8f0 !important;
}
[data-testid="stMetricDelta"] {
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #0a2a1a, #0a1628);
    border: 1px solid rgba(0,255,136,0.3);
    border-radius: 6px;
    color: #00ff88;
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 8px 20px;
    transition: all 0.2s;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #0d3a22, #0d1f3d);
    border-color: rgba(0,255,136,0.6);
    box-shadow: 0 0 20px rgba(0,255,136,0.15);
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #00ff88, #0095ff);
    color: #080c14;
    border: none;
    font-weight: 700;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 0 30px rgba(0,255,136,0.3);
    transform: translateY(-1px);
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    background: #0d1117 !important;
    border: 1px solid #1a2535 !important;
    border-radius: 6px !important;
    color: #e2e8f0 !important;
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: rgba(0,255,136,0.4) !important;
    box-shadow: 0 0 0 2px rgba(0,255,136,0.1) !important;
}

/* ── Signal Cards ── */
.signal-card-green {
    background: linear-gradient(135deg, #061a10, #061428);
    border: 1px solid rgba(0,255,136,0.3);
    border-radius: 12px;
    padding: 20px;
    margin: 8px 0;
    position: relative;
    overflow: hidden;
}
.signal-card-green::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #00ff88, transparent);
}
.signal-card-amber {
    background: linear-gradient(135deg, #1a1200, #141000);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 12px;
    padding: 20px;
    margin: 8px 0;
    position: relative;
    overflow: hidden;
}
.signal-card-amber::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #f59e0b, transparent);
}
.signal-card-red {
    background: linear-gradient(135deg, #1a0606, #140606);
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 12px;
    padding: 20px;
    margin: 8px 0;
}

/* ── Alert Boxes ── */
.exit-alert {
    background: linear-gradient(135deg, #1a0606, #0d0606);
    border: 2px solid #ef4444;
    border-radius: 12px;
    padding: 24px;
    margin: 12px 0;
    text-align: center;
    box-shadow: 0 0 40px rgba(239,68,68,0.2);
    animation: alertPulse 2s infinite;
}
@keyframes alertPulse {
    0%, 100% { box-shadow: 0 0 40px rgba(239,68,68,0.2); }
    50% { box-shadow: 0 0 60px rgba(239,68,68,0.4); }
}
.exit-alert h2 {
    color: #ef4444;
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px;
    letter-spacing: 0.1em;
    margin: 0 0 8px;
}
.exit-alert p { color: #fca5a5; margin: 0; }

.hold-alert {
    background: linear-gradient(135deg, #061a10, #061010);
    border: 2px solid #00ff88;
    border-radius: 12px;
    padding: 24px;
    margin: 12px 0;
    text-align: center;
    box-shadow: 0 0 40px rgba(0,255,136,0.1);
}
.hold-alert h2 {
    color: #00ff88;
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px;
    letter-spacing: 0.1em;
    margin: 0 0 8px;
}
.hold-alert p { color: #86efac; margin: 0; }

.watch-alert {
    background: linear-gradient(135deg, #1a1200, #141000);
    border: 2px solid #f59e0b;
    border-radius: 12px;
    padding: 24px;
    margin: 12px 0;
    text-align: center;
}
.watch-alert h2 {
    color: #f59e0b;
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px;
    letter-spacing: 0.1em;
    margin: 0 0 8px;
}
.watch-alert p { color: #fcd34d; margin: 0; }

/* ── Warning Box ── */
.warning-box {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.3);
    border-left: 3px solid #f59e0b;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 8px 0;
    color: #fcd34d;
    font-size: 13px;
    font-family: 'Share Tech Mono', monospace;
}

/* ── AI Box ── */
.ai-box {
    background: linear-gradient(135deg, #060c1a, #060e14);
    border: 1px solid rgba(0,149,255,0.2);
    border-left: 3px solid #0095ff;
    border-radius: 12px;
    padding: 24px;
    margin: 12px 0;
    color: #bfdbfe;
    line-height: 1.8;
    font-size: 14px;
    font-family: 'Inter', sans-serif;
}

/* ── Chat Messages ── */
.chat-user {
    background: linear-gradient(135deg, #0a1628, #0a1f3d);
    border: 1px solid rgba(0,149,255,0.2);
    border-radius: 12px 12px 2px 12px;
    padding: 12px 16px;
    margin: 8px 0 8px 40px;
    color: #bfdbfe;
    font-size: 14px;
}
.chat-bot {
    background: #0d1117;
    border: 1px solid #1a2535;
    border-radius: 12px 12px 12px 2px;
    padding: 12px 16px;
    margin: 8px 40px 8px 0;
    color: #94a3b8;
    font-size: 14px;
    line-height: 1.7;
}

/* ── Data Tables ── */
.stDataFrame {
    border: 1px solid #1a2535 !important;
    border-radius: 8px !important;
    overflow: hidden;
}
.stDataFrame thead th {
    background: #0d1117 !important;
    color: #4a5568 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 10px !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
    border-bottom: 1px solid #1a2535 !important;
}
.stDataFrame tbody tr:hover {
    background: rgba(255,255,255,0.02) !important;
}

/* ── Expander ── */
.streamlit-expanderHeader {
    background: #0d1117 !important;
    border: 1px solid #1a2535 !important;
    border-radius: 8px !important;
    color: #94a3b8 !important;
    font-family: 'Rajdhani', sans-serif !important;
    font-size: 14px !important;
    letter-spacing: 0.05em !important;
}
.streamlit-expanderContent {
    background: #0a0f1a !important;
    border: 1px solid #1a2535 !important;
    border-top: none !important;
}

/* ── Progress Bar ── */
.stProgress > div > div {
    background: linear-gradient(90deg, #00ff88, #0095ff) !important;
    border-radius: 4px !important;
}
.stProgress > div {
    background: #1a2535 !important;
    border-radius: 4px !important;
}

/* ── Divider ── */
hr {
    border: none;
    border-top: 1px solid #1a2535;
    margin: 16px 0;
}

/* ── Section Headers ── */
.section-header {
    font-family: 'Rajdhani', sans-serif;
    font-size: 13px;
    font-weight: 600;
    color: #4a5568;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    border-bottom: 1px solid #1a2535;
    padding-bottom: 8px;
    margin-bottom: 16px;
}

/* ── Contract Badge ── */
.contract-badge {
    background: linear-gradient(135deg, #0a2a1a, #0a1628);
    border: 1px solid rgba(0,255,136,0.4);
    border-radius: 8px;
    padding: 14px 20px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 15px;
    color: #00ff88;
    letter-spacing: 0.08em;
    text-align: center;
    margin: 12px 0;
    box-shadow: 0 0 20px rgba(0,255,136,0.1);
}

/* ── Score Bar ── */
.score-container {
    background: #0d1117;
    border: 1px solid #1a2535;
    border-radius: 8px;
    padding: 16px;
    margin: 8px 0;
}
.score-bar-bg {
    background: #1a2535;
    border-radius: 4px;
    height: 6px;
    margin: 6px 0;
    overflow: hidden;
}
.score-bar-fill-green {
    background: linear-gradient(90deg, #00ff88, #00cc6a);
    height: 100%;
    border-radius: 4px;
    transition: width 0.5s ease;
}
.score-bar-fill-amber {
    background: linear-gradient(90deg, #f59e0b, #d97706);
    height: 100%;
    border-radius: 4px;
}
.score-bar-fill-red {
    background: linear-gradient(90deg, #ef4444, #dc2626);
    height: 100%;
    border-radius: 4px;
}

/* ── Toggle ── */
.stToggle label {
    color: #94a3b8 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 12px !important;
}

/* ── Selectbox ── */
.stSelectbox label, .stTextInput label,
.stNumberInput label, .stSlider label {
    color: #4a5568 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 10px !important;
    letter-spacing: 0.15em !important;
    text-transform: uppercase !important;
}

/* ── Slider ── */
.stSlider > div > div > div {
    background: linear-gradient(90deg, #00ff88, #0095ff) !important;
}

/* ── Success/Error/Warning/Info ── */
.stSuccess {
    background: rgba(0,255,136,0.08) !important;
    border: 1px solid rgba(0,255,136,0.3) !important;
    border-radius: 8px !important;
    color: #00ff88 !important;
}
.stError {
    background: rgba(239,68,68,0.08) !important;
    border: 1px solid rgba(239,68,68,0.3) !important;
    border-radius: 8px !important;
}
.stWarning {
    background: rgba(245,158,11,0.08) !important;
    border: 1px solid rgba(245,158,11,0.3) !important;
    border-radius: 8px !important;
}
.stInfo {
    background: rgba(0,149,255,0.08) !important;
    border: 1px solid rgba(0,149,255,0.3) !important;
    border-radius: 8px !important;
}

/* ── Form ── */
[data-testid="stForm"] {
    background: #0d1117;
    border: 1px solid #1a2535;
    border-radius: 12px;
    padding: 20px;
}

/* ── Caption ── */
.stCaption {
    color: #2d3748 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.1em !important;
}

/* ── Ticker Label ── */
.ticker-label {
    font-family: 'Rajdhani', sans-serif;
    font-size: 32px;
    font-weight: 700;
    color: #e2e8f0;
    letter-spacing: 0.1em;
}
.price-label {
    font-family: 'Share Tech Mono', monospace;
    font-size: 24px;
    color: #00ff88;
}
.green  { color: #00ff88 !important; font-weight: 600; }
.red    { color: #ef4444 !important; font-weight: 600; }
.amber  { color: #f59e0b !important; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────
open_status, open_msg = is_market_open()
status_html = (
    f'<span class="status-open">MARKET OPEN</span>'
    if open_status else
    f'<span class="status-closed">MARKET CLOSED</span>'
)

stats = get_stats()
win_rate_display = f"{stats['win_rate']}% WIN RATE" if stats['total_trades'] > 0 else "NO TRADES YET"
pnl_display      = f"${stats['total_pnl']} PNL" if stats['total_trades'] > 0 else "$0 PNL"

st.markdown(f"""
<div class="app-header">
    <div style="flex:1">
        <div class="app-title">📈 AI Stock Analyzer</div>
        <div class="app-subtitle">Professional Trading System · Powered by Claude AI</div>
    </div>
    <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
        {status_html}
        <div style="background:#0d1117; border:1px solid #1a2535; border-radius:8px;
                    padding:6px 14px; font-family:'Share Tech Mono',monospace;
                    font-size:11px; color:#00ff88; letter-spacing:0.1em;">
            {win_rate_display}
        </div>
        <div style="background:#0d1117; border:1px solid #1a2535; border-radius:8px;
                    padding:6px 14px; font-family:'Share Tech Mono',monospace;
                    font-size:11px; color:#e2e8f0; letter-spacing:0.1em;">
            {pnl_display}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Main Tabs ─────────────────────────────────────────────────
tabs = st.tabs([
    "🔍 Scanner",
    "🚨 Trade Monitor",
    "🤖 Trading Coach",
    "📊 Deep Analyze",
    "📈 Backtest"
])

# ════════════════════════════════════════════════════════════
# TAB 1 — SCANNER
# ════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("🔍 Market Scanner")
    st.caption("Scans top 10 stocks and ranks by opportunity score")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        scan_interval = st.selectbox(
            "Timeframe", ["1h", "4h", "1d", "15m"], index=0,
            key="scan_interval"
        )
    with col2:
        min_score = st.slider("Min Score", 50, 90, 60, key="min_score")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        scan_btn = st.button("🔍 Run Scanner", type="primary",
                              use_container_width=True)

    # Auto-refresh toggle
    auto_refresh = st.toggle("Auto-refresh every 5 minutes", value=False)

    if scan_btn or (auto_refresh and 'last_scan' not in st.session_state):
        with st.spinner("Scanning top 10 stocks... ~2-3 minutes"):
            results = run_quick_scan(interval=scan_interval, force=True)
            st.session_state['scan_results'] = results
            st.session_state['last_scan']    = datetime.now()

    # Show results
    if 'scan_results' in st.session_state:
        results   = st.session_state['scan_results']
        last_scan = st.session_state.get('last_scan')

        if last_scan:
            st.caption(f"Last scan: {last_scan.strftime('%I:%M %p CST')}")

        top3 = [r for r in results if r['score'] >= min_score][:3]

        if not top3:
            st.info("No opportunities above your minimum score. "
                    "Lower the min score or wait for better setups.")
        else:
            for i, r in enumerate(top3):
                score   = r['score']
                ticker  = r['ticker']
                signal  = r['signal']
                reasons = r['reasons'][:3]
                contract= r['best_contract']

                # Card color by score
                if score >= 80:
                    card_class = "signal-card-green"
                    icon       = "🔴"
                    label      = "STRONG SIGNAL"
                elif score >= 65:
                    card_class = "signal-card-amber"
                    icon       = "🟡"
                    label      = "GOOD SETUP"
                else:
                    card_class = "signal-card-amber"
                    icon       = "👀"
                    label      = "WATCH"

                with st.expander(
                    f"{icon} #{i+1} {ticker} — Score {score}/100 — {label}",
                    expanded = (i == 0)
                ):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Score",  f"{score}/100")
                    c2.metric("Signal", signal)
                    c3.metric("Price",  f"${r.get('close', 'N/A')}")
                    c4.metric("RSI",    r.get('rsi', 'N/A'))

                    # Contract recommendation
                    if contract:
                        st.markdown("---")
                        st.markdown("**📋 Recommended Contract:**")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Type",    contract['type'])
                        c2.metric("Strike",  f"${contract['strike']}")
                        c3.metric("Expiry",  contract['expiry'])
                        c4.metric("Premium", f"${contract['premium']}")

                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Cost",     f"${contract['contract_cost']}")
                        c2.metric("Delta",    contract['delta'])
                        c3.metric("IV",       f"{contract['iv']}%")
                        c4.metric("Prob ITM", f"{contract['prob_itm']}%")

                        # Discord-style signal
                        st.markdown(
                            f'<div class="contract-badge">'
                            f'⚡ BUY {ticker} ${contract["strike"]} '
                            f'{contract["type"]} {contract["expiry"]} '
                            f'@ ${contract["premium"]}'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.warning(
                            "No contract found under $3 — "
                            "stock may be too expensive for $2K account"
                        )

                    # Why this stock
                    st.markdown("**Why this setup:**")
                    for reason in reasons:
                        st.markdown(f"• {reason}")

                    # Unusual flow
                    if r.get('unusual_flow'):
                        st.markdown("**🐋 Unusual Flow Detected:**")
                        for flow in r['unusual_flow']:
                            st.markdown(f"🔥 {flow}")

                    # Send to monitor button
                    if contract:
                        if st.button(
                            f"📲 Send to Trade Monitor",
                            key=f"monitor_{ticker}_{i}"
                        ):
                            st.session_state['monitor_ticker']  = ticker
                            st.session_state['monitor_type']    = contract['type']
                            st.session_state['monitor_strike']  = contract['strike']
                            st.session_state['monitor_expiry']  = contract['expiry']
                            st.session_state['monitor_premium'] = contract['premium']
                            st.success(
                                "Sent to Trade Monitor! "
                                "Go to 🚨 Trade Monitor tab."
                            )

        # Show all scores summary
        st.divider()
        st.markdown("**All Stocks Scanned:**")
        summary_data = []
        for r in results:
            icon = ("🔴" if r['score'] >= 80 else
                    "🟡" if r['score'] >= 60 else "⚪")
            summary_data.append({
                'Stock':  r['ticker'],
                'Score':  f"{icon} {r['score']}/100",
                'Signal': r['signal'],
                'Price':  f"${r.get('close', 'N/A')}",
                'RSI':    r.get('rsi', 'N/A'),
            })
        if summary_data:
            st.dataframe(
                pd.DataFrame(summary_data),
                use_container_width=True,
                hide_index=True
            )

    # Auto-refresh logic
    if auto_refresh and 'last_scan' in st.session_state:
        elapsed = (datetime.now() -
                   st.session_state['last_scan']).seconds
        remaining = max(0, 300 - elapsed)
        st.caption(f"Next scan in {remaining} seconds...")
        if remaining == 0:
            st.rerun()


# ════════════════════════════════════════════════════════════
# TAB 2 — TRADE MONITOR
# ════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("🚨 Trade Monitor")
    st.caption("Enter your open trade — app watches it every 1 min and alerts you when to exit")

    # ── Trade Input ───────────────────────────────────────────
    with st.form("trade_monitor_form"):
        st.markdown("**Enter your trade details:**")
        c1, c2, c3 = st.columns(3)
        with c1:
            mon_ticker  = st.text_input(
                "Ticker",
                value = st.session_state.get('monitor_ticker', 'AAPL')
            )
            mon_type    = st.selectbox(
                "Option Type",
                ["CALL", "PUT"],
                index = 0 if st.session_state.get(
                    'monitor_type', 'CALL') == 'CALL' else 1
            )
        with c2:
            mon_strike  = st.number_input(
                "Strike Price",
                value = float(st.session_state.get('monitor_strike', 200)),
                step  = 1.0
            )
            mon_expiry  = st.text_input(
                "Expiry (YYYY-MM-DD)",
                value = st.session_state.get('monitor_expiry', '2026-06-20')
            )
        with c3:
            mon_premium = st.number_input(
                "Your Entry Premium ($)",
                value = float(st.session_state.get('monitor_premium', 1.30)),
                step  = 0.01,
                format = "%.2f"
            )
            mon_contracts = st.number_input(
                "Number of Contracts",
                value = 1, min_value = 1, max_value = 10
            )

        start_monitor = st.form_submit_button(
            "🚨 Start Monitoring", type="primary",
            use_container_width=True
        )

    if start_monitor:
        st.session_state['active_trade'] = {
            'ticker':    mon_ticker.upper(),
            'type':      mon_type,
            'strike':    mon_strike,
            'expiry':    mon_expiry,
            'premium':   mon_premium,
            'contracts': mon_contracts,
            'cost':      round(mon_premium * 100 * mon_contracts, 2),
            'start':     datetime.now().strftime("%I:%M %p")
        }
        st.success(f"Now monitoring {mon_ticker.upper()} "
                   f"${mon_strike} {mon_type} — "
                   f"phone will buzz on exit signals!")

    # ── Live Monitor ──────────────────────────────────────────
    if 'active_trade' in st.session_state:
        trade = st.session_state['active_trade']
        ticker  = trade['ticker']
        premium = trade['premium']

        st.divider()
        st.markdown(f"### Monitoring: {ticker} ${trade['strike']} "
                    f"{trade['type']} | Entry: ${premium}")

        # Fetch current data
        with st.spinner(f"Fetching live data for {ticker}..."):
            data = get_all_data(ticker, '5m')

        if data['df'] is not None:
            df      = calculate_indicators(data['df'])
            signals = get_signals(df)
            signal, confidence, bull, bear = calculate_score(signals)

            current_price = signals['close']

            # Try to get current option price from chain
            current_premium = None
            if data['options']:
                try:
                    expiry = trade['expiry']
                    if expiry in data['options']:
                        chain = data['options'][expiry]
                        side  = chain['calls'] if trade['type'] == 'CALL' else chain['puts']
                        row   = side[side['strike'] == trade['strike']]
                        if not row.empty:
                            bid = row.iloc[0]['bid']
                            ask = row.iloc[0]['ask']
                            current_premium = round((bid + ask) / 2, 2)
                except:
                    pass

            # Fallback — estimate from price movement
            if not current_premium:
                price_change_pct = ((current_price - trade['strike']) /
                                     trade['strike'])
                if trade['type'] == 'CALL':
                    current_premium = round(
                        premium * (1 + price_change_pct * 5), 2)
                else:
                    current_premium = round(
                        premium * (1 - price_change_pct * 5), 2)
                current_premium = max(0.01, current_premium)

            # Calculate P&L
            pnl_per_contract = round(
                (current_premium - premium) * 100, 2)
            total_pnl  = round(pnl_per_contract * trade['contracts'], 2)
            pnl_pct    = round(
                (current_premium - premium) / premium * 100, 1)

            # Days to expiry
            try:
                exp_date  = datetime.strptime(trade['expiry'], "%Y-%m-%d")
                days_left = (exp_date - datetime.now()).days
            except:
                days_left = 30

            # ── Exit Condition Checks ─────────────────────────
            exit_action  = "HOLD"
            exit_reason  = ""
            exit_class   = "hold-alert"

            # STOP LOSS — down 30%
            if pnl_pct <= -30:
                exit_action = "EXIT NOW — STOP LOSS"
                exit_reason = f"Down {abs(pnl_pct)}% — hard stop hit. No exceptions."
                exit_class  = "exit-alert"
                alert_stop_loss(ticker, premium, current_premium, abs(pnl_pct))

            # TAKE PROFIT — up 100%
            elif pnl_pct >= 100:
                exit_action = "EXIT — DOUBLED YOUR MONEY"
                exit_reason = f"Up {pnl_pct}% — take everything off. Don't give it back."
                exit_class  = "exit-alert"
                alert_take_profit(ticker, premium, current_premium, pnl_pct)

            # PARTIAL EXIT — up 50%
            elif pnl_pct >= 50:
                exit_action = "TAKE HALF OFF"
                exit_reason = f"Up {pnl_pct}% — sell 50% now, let rest ride."
                exit_class  = "watch-alert"
                alert_exit_signal(ticker, f"Up {pnl_pct}% - take partial profit",
                                   current_premium)

            # RSI DIVERGENCE — momentum dying
            elif (signals.get('rsi', 50) > 70 and
                  signal in ['SELL', 'STRONG SELL']):
                exit_action = "EXIT — MOMENTUM DYING"
                exit_reason = (f"RSI {signals.get('rsi')} overbought + "
                                f"bearish signal. Top may be in.")
                exit_class  = "exit-alert"
                alert_exit_signal(ticker, "RSI overbought + bearish signal",
                                   current_premium)

            # THETA WARNING — 7 days left
            elif days_left <= 7:
                exit_action = "EXIT — THETA DANGER"
                exit_reason = (f"Only {days_left} days to expiry. "
                                f"Time decay accelerating fast.")
                exit_class  = "exit-alert"
                alert_theta_warning(ticker, days_left, current_premium)

            # THETA WARNING — 3 days left
            elif days_left <= 3:
                exit_action = "EXIT NOW — EXPIRES SOON"
                exit_reason = f"{days_left} days left — exit immediately."
                exit_class  = "exit-alert"

            # ── Display Metrics ───────────────────────────────
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Stock Price",     f"${current_price}")
            c2.metric("Entry Premium",   f"${premium}")
            c3.metric("Current Premium", f"${current_premium}")
            pnl_delta = f"+{pnl_pct}%" if pnl_pct >= 0 else f"{pnl_pct}%"
            c4.metric("P&L",
                       f"${total_pnl}",
                       delta = pnl_delta)
            c5.metric("Days Left", days_left)

            # ── Exit Signal Box ───────────────────────────────
            st.markdown(
                f'<div class="{exit_class}">'
                f'<h2>{exit_action}</h2>'
                f'<p>{exit_reason}</p>'
                f'</div>',
                unsafe_allow_html=True
            )

            # ── Indicators ────────────────────────────────────
            st.divider()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("RSI",       signals.get('rsi'))
            c2.metric("Signal",    signal)
            c3.metric("Above VWAP",
                       "Yes" if signals.get('above_vwap') else "No")
            c4.metric("Vol Ratio", f"{signals.get('vol_ratio')}x")

            # ── Trade Rules ───────────────────────────────────
            st.divider()
            st.markdown("**📋 Your Trade Rules:**")
            col1, col2 = st.columns(2)
            with col1:
                tp50  = round(premium * 1.5, 2)
                tp100 = round(premium * 2.0, 2)
                st.markdown(f"• Take 50% off at: **${tp50}** (50% gain)")
                st.markdown(f"• Take all off at: **${tp100}** (100% gain)")
                st.markdown(f"• Stop loss at: "
                             f"**${round(premium * 0.70, 2)}** (30% loss)")
            with col2:
                st.markdown(f"• Max hold: **{days_left} days** left")
                st.markdown(f"• Exit if expiry < 7 days")
                st.markdown(f"• Never average down on a loss")

            # ── Auto Refresh ──────────────────────────────────
            auto_mon = st.toggle("Auto-refresh every 1 minute", value=False,
                                  key="auto_monitor")
            if auto_mon:
                st.caption("Monitoring live — refreshes every 60 seconds")
                time.sleep(60)
                st.rerun()

            # ── Close Trade ───────────────────────────────────
            st.divider()
            with st.expander("Close This Trade"):
                with st.form("close_monitor_trade"):
                    c1, c2 = st.columns(2)
                    with c1:
                        exit_prem = st.number_input(
                            "Exit Premium", value=current_premium,
                            step=0.01, format="%.2f"
                        )
                        result_sel = st.selectbox(
                            "Result", ["WIN", "LOSS", "BREAKEVEN"])
                    with c2:
                        feedback   = st.text_input("What happened?")
                        learned    = st.text_area(
                            "What did you learn?", height=60)
                    if st.form_submit_button("Close Trade"):
                        close_trade(
                            trade_id     = 1,
                            exit_price   = current_price,
                            exit_premium = exit_prem,
                            result       = result_sel,
                            feedback     = feedback,
                            what_wrong   = learned
                        )
                        del st.session_state['active_trade']
                        st.success("Trade closed and logged!")
                        st.rerun()
        else:
            st.error(f"Could not fetch data for {ticker}")


# ════════════════════════════════════════════════════════════
# TAB 3 — TRADING COACH (CHATBOT)
# ════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("🤖 Trading Coach")
    st.caption("Ask anything about your trades, setups, or strategy. "
               "Learns from your trade history automatically.")

    # Load trade history for context
    trade_history = ""
    try:
        if os.path.exists("trades.json"):
            with open("trades.json", "r") as f:
                trades = json.load(f)
            if trades:
                trade_history = json.dumps(trades[-20:], indent=2)
    except:
        trade_history = ""

    # Initialize chat history
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []

    # System prompt — knows your trades
    system_prompt = f"""You are an expert options trading coach with 20+ years experience.
You are analyzing the user's personal trading history and helping them improve.

The user has a $2,000 account and trades options — primarily calls and puts on 
high-volume US stocks like AAPL, NVDA, TSLA, AMD, etc.

Their core strategy:
- Buy calls/puts when scanner score is 80+
- Max $3 premium per contract ($300/contract)
- Stop loss at -30% of premium
- Take 50% profit at +50%, exit rest at +100%
- Never hold through earnings
- Never hold with less than 7 days to expiry

Here is their recent trade history (last 20 trades):
{trade_history if trade_history else "No trades logged yet."}

Key rules for your coaching:
- Be direct and specific — no fluff
- Reference their actual trade history when relevant
- Point out patterns in their wins and losses
- Help them identify when NOT to trade
- Always emphasize risk management
- Give specific actionable advice

If they ask about a current setup, analyze it properly.
If they ask about their performance, use their actual trade data."""

    # Display chat history
    for msg in st.session_state['chat_history']:
        if msg['role'] == 'user':
            st.markdown(
                f'<div class="chat-user">👤 {msg["content"]}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="chat-bot">🤖 {msg["content"]}</div>',
                unsafe_allow_html=True
            )

    # Quick question buttons
    st.markdown("**Quick questions:**")
    qcol1, qcol2, qcol3, qcol4 = st.columns(4)
    quick_q = None
    with qcol1:
        if st.button("📊 How am I doing?"):
            quick_q = "How am I doing overall? Analyze my win rate and patterns."
    with qcol2:
        if st.button("🚫 What's my worst habit?"):
            quick_q = "What is my worst trading habit based on my history?"
    with qcol3:
        if st.button("💡 Best setup for today?"):
            quick_q = ("Market is open. What type of setup should "
                       "I be looking for today?")
    with qcol4:
        if st.button("🔴 Should I exit my trade?"):
            if 'active_trade' in st.session_state:
                t = st.session_state['active_trade']
                quick_q = (f"I have an open {t['ticker']} "
                            f"${t['strike']} {t['type']} "
                            f"entered at ${t['premium']}. "
                            f"Should I exit?")
            else:
                quick_q = "What are the top 3 signs I should exit a trade immediately?"

    # Chat input
    user_input = st.chat_input("Ask your trading coach anything...")

    # Handle input
    if quick_q:
        user_input = quick_q

    if user_input:
        # Add to history
        st.session_state['chat_history'].append({
            'role': 'user', 'content': user_input
        })

        # Build messages for API
        messages = []
        for msg in st.session_state['chat_history']:
            messages.append({
                'role':    msg['role'],
                'content': msg['content']
            })

        # Call Claude
        with st.spinner("Coach is thinking..."):
            try:
                try:
                    api_key = st.secrets["ANTHROPIC_API_KEY"]
                except:
                    import os
                    api_key = os.getenv("ANTHROPIC_API_KEY")

                client   = anthropic.Anthropic(api_key=api_key)
                response = client.messages.create(
                    model      = "claude-opus-4-5",
                    max_tokens = 1000,
                    system     = system_prompt,
                    messages   = messages
                )
                reply = response.content[0].text

            except Exception as e:
                reply = f"Coach unavailable: {e}"

        # Add reply to history
        st.session_state['chat_history'].append({
            'role': 'assistant', 'content': reply
        })

        st.rerun()

    # Clear chat button
    if st.session_state['chat_history']:
        if st.button("🗑️ Clear Chat"):
            st.session_state['chat_history'] = []
            st.rerun()


# ════════════════════════════════════════════════════════════
# TAB 4 — DEEP ANALYZE
# ════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("📊 Deep Analysis")
    st.caption("Full analysis on a single stock")

    # Input
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        raw_input    = st.text_input(
            "Stock Ticker or Company Name",
            value       = "AAPL",
            placeholder = "AAPL, Apple, Tesla...",
            key         = "analyze_ticker"
        )
        ticker       = resolve_ticker(raw_input)
        if raw_input and ticker != raw_input.upper().strip():
            st.caption(f"→ {ticker}")
    with c2:
        interval = st.selectbox(
            "Timeframe", ["1h", "4h", "1d", "15m"], index=0,
            key="analyze_interval"
        )
    with c3:
        account_size = st.number_input(
            "Account ($)", value=2000, step=500, min_value=500,
            key="analyze_account"
        )
    with c4:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button(
            "🔍 Analyze", type="primary",
            use_container_width=True, key="analyze_btn"
        )

    if analyze_btn and ticker:
        with st.spinner(f"Fetching data for {ticker}..."):
            data = get_all_data(ticker, interval)

        if data['df'] is None:
            st.error(f"Could not fetch data for {ticker}")
            st.stop()

        with st.spinner("Running analysis..."):
            df      = calculate_indicators(data['df'])
            signals = get_signals(df)
            signal, confidence, bull, bear = calculate_score(signals)
            market  = get_market_conditions()
            sector  = get_sector_data(ticker)
            timing  = get_best_time_to_trade()
            macro   = get_macro_calendar()
            expiry  = get_most_active_expiry(data['options']) if data['options'] else None
            best_opt= get_best_option(
                data['options'], signals['close'], signal, expiry
            ) if data['options'] else None
            alt_strat = get_alternative_strategy(
                best_opt, data['options'], signal, signals['close']
            ) if data['options'] else None
            targets = calculate_targets(
                signals['close'], signal, signals['atr'], signals)
            sizing  = calculate_position_size(account_size, 2,
                        best_opt['premium'] if best_opt else 1)
            drawdown= calculate_drawdown(
                sizing.get('recommended', 1), account_size,
                best_opt['premium'] if best_opt else 1)
            ev      = calculate_expected_value(
                75, sizing.get('contract_cost', 300) * 2,
                sizing.get('contract_cost', 300))
            swing   = calculate_swing_score(
                signals, market, sector, data['options'],
                best_opt, data['earnings'], timing)

        # Warnings
        if data['earnings'].get('warning'):
            st.markdown(
                f'<div class="warning-box">⚠️ <b>EARNINGS WARNING</b> — '
                f'{data["earnings"].get("earnings_date")} '
                f'({data["earnings"].get("days_until")} days) — '
                f'High IV crush risk</div>',
                unsafe_allow_html=True
            )

        # Top metrics
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Price",       f"${signals['close']}")
        c2.metric("Signal",      signal,
                   delta=f"{confidence}% confidence")
        c3.metric("Swing Score", f"{swing['score']}/10",
                   delta=swing['verdict'])
        c4.metric("RSI",         signals.get('rsi'))
        c5.metric("Vol Ratio",   f"{signals.get('vol_ratio')}x")

        st.divider()

        # Analysis sections
        a1, a2 = st.columns(2)

        with a1:
            st.markdown("**📍 Price Targets**")
            rows = [
                ("Entry zone",  f"${targets.get('entry_low')} — ${targets.get('entry_high')}"),
                ("Stop loss",   f"${targets.get('stop_loss')}"),
                ("TP1 (30%)",   f"${targets.get('tp1')}"),
                ("TP2 (40%)",   f"${targets.get('tp2')}"),
                ("TP3 (30%)",   f"${targets.get('tp3')}"),
                ("Risk/Reward", f"1:{targets.get('rr_ratio')}"),
                ("Support",     f"${signals.get('support')}"),
                ("Resistance",  f"${signals.get('resistance')}"),
            ]
            for label, val in rows:
                c1, c2 = st.columns([1, 1])
                c1.markdown(
                    f"<span style='color:#888;font-size:13px'>{label}</span>",
                    unsafe_allow_html=True)
                c2.markdown(
                    f"<span style='font-size:13px;font-weight:600'>{val}</span>",
                    unsafe_allow_html=True)

        with a2:
            st.markdown("**📊 Indicators**")
            ind_rows = [
                ("RSI",        signals.get('rsi'),
                 "green" if signals.get('rsi_bullish') else "red"),
                ("MACD",
                 "Bullish ✅" if signals.get('macd_bullish') else "Bearish ❌",
                 "green" if signals.get('macd_bullish') else "red"),
                ("EMA Stack",
                 "Bullish ✅" if signals.get('ema_bullish') else "Bearish ❌",
                 "green" if signals.get('ema_bullish') else "red"),
                ("Above EMA200",
                 "Yes ✅" if signals.get('above_ema200') else "No ❌",
                 "green" if signals.get('above_ema200') else "red"),
                ("Above VWAP",
                 "Yes ✅" if signals.get('above_vwap') else "No ❌",
                 "green" if signals.get('above_vwap') else "red"),
                ("ADX",        signals.get('adx'),
                 "green" if signals.get('strong_trend') else "amber"),
                ("Vol Ratio",  f"{signals.get('vol_ratio')}x",
                 "green" if signals.get('high_volume') else "amber"),
            ]
            for label, val, color in ind_rows:
                c1, c2 = st.columns([1, 1])
                c1.markdown(
                    f"<span style='color:#888;font-size:13px'>{label}</span>",
                    unsafe_allow_html=True)
                c2.markdown(
                    f"<span class='{color}' style='font-size:13px;"
                    f"font-weight:600'>{val}</span>",
                    unsafe_allow_html=True)

        # Best option
        if best_opt:
            st.divider()
            st.markdown("**📋 Best Option**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Strike",   f"${best_opt['strike']}")
            c2.metric("Expiry",   best_opt['expiry'])
            c3.metric("Premium",  f"${best_opt['premium']}")
            c4.metric("Prob ITM", f"{best_opt['prob_itm']}%")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Delta",    best_opt['delta'])
            c2.metric("IV",       f"{best_opt['iv']}%")
            c3.metric("Theta/day",f"${best_opt['theta']}")
            c4.metric("Break even",f"${best_opt['break_even']}")

            st.markdown(
                f'<div class="contract-badge">'
                f'⚡ BUY {ticker} ${best_opt["strike"]} '
                f'{best_opt["type"]} {best_opt["expiry"]} '
                f'@ ${best_opt["premium"]}'
                f'</div>',
                unsafe_allow_html=True
            )

        # Market
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("SPY",          market.get('spy_trend'),
                   delta=f"${market.get('spy_price')}")
        c2.metric("VIX",          market.get('vix'),
                   delta=market.get('vix_status'))
        c3.metric("Sector",       sector.get('sector_trend'),
                   delta=f"{sector.get('sector_1w_chg')}% 1W")

        # AI Verdict
        st.divider()
        st.markdown("**🏆 AI Veteran Verdict**")
        if st.button("Get AI Analysis", key="get_ai"):
            with st.spinner("Claude AI analyzing..."):
                analysis = get_ai_analysis(
                    ticker, interval, signals, signal, confidence,
                    targets, sizing, drawdown, ev, swing,
                    market, sector, timing, macro,
                    data['options'], best_opt, alt_strat,
                    data['analyst'], data['premarket'], data['earnings']
                )
            st.markdown(
                f'<div class="ai-box">{analysis}</div>',
                unsafe_allow_html=True
            )

        # Log trade
        st.divider()
        st.markdown("**📝 Log This Trade**")
        with st.form("log_trade_analyze"):
            c1, c2 = st.columns(2)
            with c1:
                log_notes = st.text_area("Notes", height=60)
            with c2:
                setup_tags = st.multiselect(
                    "Tags",
                    ["breakout", "pullback", "vwap_bounce", "oversold",
                     "high_volume", "gap_up", "gap_down", "earnings_risk"]
                )
            if st.form_submit_button("📝 Log Trade"):
                if best_opt:
                    log_trade(
                        ticker      = ticker,
                        signal      = signal,
                        entry_price = signals['close'],
                        strike      = best_opt.get('strike'),
                        expiry      = best_opt.get('expiry'),
                        premium     = best_opt.get('premium'),
                        contracts   = sizing.get('recommended', 1),
                        stop_loss   = targets.get('stop_loss'),
                        tp1         = targets.get('tp1'),
                        tp2         = targets.get('tp2'),
                        tp3         = targets.get('tp3'),
                        swing_score = swing['score'],
                        confidence  = confidence,
                        setup_tags  = setup_tags,
                        notes       = log_notes
                    )
                    st.success("Trade logged!")


# ════════════════════════════════════════════════════════════
# TAB 5 — BACKTEST
# ════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("📈 Backtest")
    st.caption("Run your scoring system on historical data — "
               "proves the strategy works before risking real money")

    c1, c2, c3 = st.columns(3)
    with c1:
        bt_ticker   = st.text_input("Ticker", value="AAPL", key="bt_ticker")
    with c2:
        bt_days     = st.selectbox("Lookback Period",
                                    ["30 days", "60 days", "90 days"],
                                    index=1)
        days_map    = {"30 days": 30, "60 days": 60, "90 days": 90}
        n_days      = days_map[bt_days]
    with c3:
        bt_account  = st.number_input("Account ($)", value=2000,
                                       step=500, key="bt_account")

    st.markdown("<br>", unsafe_allow_html=True)
    bt_btn = st.button("▶️ Run Backtest", type="primary",
                        use_container_width=True)

    if bt_btn and bt_ticker:
        with st.spinner(f"Running backtest on {bt_ticker} "
                         f"for last {n_days} days..."):
            try:
                import yfinance as yf
                from indicator_engine import calculate_indicators, get_signals, calculate_score

                stock    = yf.Ticker(bt_ticker.upper())

                # Fetch 1h candles — max 60 days free on yfinance
                hist_1h  = stock.history(period="60d", interval="1h")
                hist_1h.columns = [c.lower() for c in hist_1h.columns]

                # Daily data for indicator warmup
                hist_1d  = stock.history(period="1y",  interval="1d")
                hist_1d.columns = [c.lower() for c in hist_1d.columns]

                if len(hist_1h) < 50 or len(hist_1d) < 200:
                    st.error("Not enough data. Try a major stock like AAPL.")
                    st.stop()

                trades_bt    = []
                wins         = 0
                losses       = 0
                total_pnl_bt = 0
                option_lev   = 15.0  # ATM option moves ~15x stock % intraday

                progress       = st.progress(0)
                processed_dates= set()
                total_bars     = len(hist_1h)

                for idx in range(len(hist_1h) - 5):
                    progress.progress(int((idx / total_bars) * 100))

                    bar_time = hist_1h.index[idx]
                    bar_date = bar_time.date()
                    bar_hour = bar_time.hour

                    # Only trade first 2 hours — 9:30-11:30 ET
                    if bar_hour < 9 or bar_hour > 11:
                        continue

                    # One trade per day only
                    if bar_date in processed_dates:
                        continue

                    # Get daily signal for this date
                    daily_window = hist_1d[hist_1d.index.normalize().date <= bar_date]
                    if len(daily_window) < 200:
                        continue

                    df_bt = calculate_indicators(daily_window)
                    if df_bt is None:
                        continue

                    sig_bt = get_signals(df_bt)
                    signal_bt, conf_bt, bull_bt, bear_bt = calculate_score(sig_bt)

                    if signal_bt not in ['STRONG BUY', 'BUY']:
                        continue
                    if conf_bt < 55:
                        continue

                    processed_dates.add(bar_date)

                    # Entry
                    entry_price = hist_1h['open'].iloc[idx]

                    # Estimate realistic ATM option premium
                    # Based on stock price — scales naturally
                    # Under $50  → ~$0.50-0.80
                    # $50-150    → ~$0.80-1.50
                    # $150-300   → ~$1.50-2.50
                    # Over $300  → ~$2.00-3.00
                    # Formula: ~0.5-1% of stock price, capped at $3
                    raw_premium   = entry_price * 0.007  # ~0.7% of stock price
                    entry_premium = round(min(3.00, max(0.30, raw_premium)), 2)

                    peak_premium  = entry_premium
                    trailing_high = entry_premium
                    exit_premium  = entry_premium
                    outcome       = "BREAKEVEN"
                    exit_reason   = "Small move"
                    hit_target    = False

                    # Walk forward up to 4 hours same day
                    for j in range(idx+1, min(idx+5, len(hist_1h))):
                        next_time = hist_1h.index[j]
                        if next_time.date() != bar_date:
                            break
                        if next_time.hour >= 15:
                            break

                        cur_price   = hist_1h['close'].iloc[j]
                        stk_move    = (cur_price - entry_price) / entry_price * 100
                        cur_premium = round(
                            entry_premium * (1 + stk_move * option_lev / 100), 2)
                        cur_premium = max(0.05, cur_premium)

                        pnl_pct = (cur_premium - entry_premium) / entry_premium * 100

                        if cur_premium > peak_premium:
                            peak_premium  = cur_premium
                            trailing_high = cur_premium

                        # Stop loss -30%
                        if pnl_pct <= -30:
                            exit_premium = cur_premium
                            outcome      = "LOSS"
                            exit_reason  = f"Stop loss in {j-idx}h"
                            losses      += 1
                            break

                        # Hit 20% — start trailing
                        if pnl_pct >= 20:
                            hit_target = True

                        # Trailing — drop 10% from peak
                        if hit_target:
                            drop = (cur_premium - trailing_high) / trailing_high * 100
                            if drop <= -10:
                                exit_premium = cur_premium
                                outcome      = "WIN"
                                exit_reason  = (
                                    f"Peaked ${round(peak_premium,2)} "
                                    f"sold on reversal"
                                )
                                wins += 1
                                break
                    else:
                        # End of session exit
                        exit_premium = cur_premium if 'cur_premium' in dir() else entry_premium
                        final_pnl    = (exit_premium - entry_premium) / entry_premium * 100
                        if final_pnl >= 20:
                            outcome     = "WIN"
                            exit_reason = "Up at close"
                            wins       += 1
                        elif final_pnl <= -30:
                            outcome     = "LOSS"
                            exit_reason = "Down at close"
                            losses     += 1
                        else:
                            outcome     = "BREAKEVEN"
                            exit_reason = "Small move"

                    opt_pnl      = round((exit_premium - entry_premium) * 100, 2)
                    opt_pnl_pct  = round(
                        (exit_premium - entry_premium) / entry_premium * 100, 1)

                    # Reclassify outcome based on actual return
                    # Reset counters for this trade first
                    if outcome == "WIN":
                        pass  # already counted
                    elif outcome == "LOSS":
                        pass  # already counted
                    elif opt_pnl_pct >= 10:
                        # Up 10-19% — small win, take it in real life
                        outcome  = "SMALL WIN"
                        wins    += 1
                    # else stays BREAKEVEN

                    total_pnl_bt += opt_pnl

                    import pytz
                    et_tz  = pytz.timezone('US/Eastern')
                    cst_tz = pytz.timezone('US/Central')

                    # Convert bar time to CST for display
                    try:
                        if bar_time.tzinfo is None:
                            bar_time_et  = et_tz.localize(bar_time.to_pydatetime())
                        else:
                            bar_time_et  = bar_time.to_pydatetime()
                        bar_time_cst = bar_time_et.astimezone(cst_tz)
                        display_time = bar_time_cst.strftime("%I:%M %p CST")
                    except:
                        display_time = bar_time.strftime("%I:%M %p")

                    trades_bt.append({
                        'Date':        bar_date.strftime("%Y-%m-%d"),
                        'Time (CST)':  display_time,
                        'Signal':      signal_bt,
                        'Conf':        f"{conf_bt}%",
                        'Stock':       f"${round(entry_price,2)}",
                        'Prem In':     f"${entry_premium}",
                        'Peak':        f"${round(peak_premium,2)}",
                        'Prem Out':    f"${round(exit_premium,2)}",
                        'Return':      f"{opt_pnl_pct}%",
                        'PnL':         f"${opt_pnl}",
                        'Result':      outcome,
                        'Why':         exit_reason
                    })

                progress.progress(100)

                # Results
                total_trades  = len(trades_bt)
                small_wins    = sum(1 for t in trades_bt if t['Result'] == 'SMALL WIN')
                breakevens    = sum(1 for t in trades_bt if t['Result'] == 'BREAKEVEN')
                total_wins    = wins  # wins + small wins
                win_rate      = round(total_wins / total_trades * 100, 1) if total_trades > 0 else 0
                win_rate_excl = round(total_wins / (total_wins + losses) * 100, 1) if (total_wins + losses) > 0 else 0

                st.divider()
                st.markdown("### Backtest Results")
                st.caption("Based on your strategy: buy at market price (est. 0.7% of stock), "
                           "trail after +20%, stop loss at -30%")

                c1, c2, c3, c4, c5, c6 = st.columns(6)
                c1.metric("Total Signals", total_trades)
                c2.metric("Wins 20%+",     wins - small_wins)
                c3.metric("Small Wins",    small_wins,
                           delta="10-19% gains")
                c4.metric("Losses",        losses,
                           delta="Stop loss hit")
                c5.metric("Breakeven",     breakevens,
                           delta="Flat trades")
                c6.metric("Win Rate",      f"{win_rate}%",
                           delta=f"{win_rate_excl}% excl. flat")

                c1, c2 = st.columns(2)
                c1.metric("Total PnL",
                           f"${round(total_pnl_bt, 2)}",
                           delta="Profitable ✅" if total_pnl_bt > 0 else "Losing ❌")
                c2.metric("Per Trade Avg",
                           f"${round(total_pnl_bt / total_trades, 2) if total_trades > 0 else 0}")

                # Verdict based on PROFITABILITY not just win rate
                if total_pnl_bt > 0 and win_rate >= 35:
                    st.success(
                        f"✅ SYSTEM WORKS — Profitable over last {n_days} days. "
                        f"{win_rate}% win rate with ${round(total_pnl_bt,0)} total profit. "
                        f"Ready for paper trading."
                    )
                elif total_pnl_bt > 0 and win_rate < 35:
                    st.warning(
                        f"⚠️ MARGINAL — Profitable (${round(total_pnl_bt,0)}) "
                        f"but low win rate ({win_rate}%). "
                        f"Needs more testing before real money."
                    )
                elif total_pnl_bt <= 0 and win_rate >= 40:
                    st.warning(
                        f"⚠️ MIXED — Good win rate ({win_rate}%) "
                        f"but not profitable yet. "
                        f"Adjust stop loss and targets."
                    )
                else:
                    st.error(
                        f"❌ NOT READY — {win_rate}% win rate and "
                        f"${round(total_pnl_bt,0)} PnL. "
                        f"Do NOT trade real money yet."
                    )

                # Trade log
                if trades_bt:
                    st.divider()
                    st.markdown("**Signal History:**")
                    df_results = pd.DataFrame(trades_bt)
                    st.dataframe(df_results, use_container_width=True,
                                  hide_index=True)

            except Exception as e:
                st.error(f"Backtest error: {e}")