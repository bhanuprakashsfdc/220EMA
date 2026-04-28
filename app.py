import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import glob

# -----------------------------
# CONFIG
# -----------------------------
st.set_page_config(page_title="220EMA Momentum Dashboard", layout="wide")

DATA_DIR = "data"

# Get available symbols from local CSV files
def get_available_symbols():
    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    symbols = [os.path.basename(f).replace(".csv", "") for f in csv_files]
    return sorted(symbols)

NIFTY50_SYMBOLS = get_available_symbols()

# -----------------------------
# UTIL FUNCTIONS
# -----------------------------
def get_prev_month_end():
    today = datetime.today()
    first_day = today.replace(day=1)
    return first_day - timedelta(days=1)

def load_stock_data(symbol):
    filepath = os.path.join(DATA_DIR, f"{symbol}.csv")
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath, parse_dates=["Date"])
    df = df.set_index("Date").sort_index()
    return df

def calculate_ema(prices, period):
    return prices.ewm(span=period, adjust=False).mean()

def analyze_ath_strategy(symbol):
    df = load_stock_data(symbol)
    if df is None or df.empty or "Close" not in df.columns:
        return None
    
    df = df.dropna(subset=["Close"])
    if len(df) < 220:
        return None
    
    close = df["Close"]
    ath = close.expanding().max().iloc[-1]
    current_close = close.iloc[-1]
    ema_220 = calculate_ema(close, 220).iloc[-1]
    
    is_new_ath = current_close >= ath
    above_ema = current_close > ema_220
    
    return {
        "Symbol": symbol,
        "Close": current_close,
        "ATH": ath,
        "EMA220": ema_220,
        "New ATH": is_new_ath,
        "Above EMA220": above_ema,
        "BUY Signal": is_new_ath and above_ema
    }

@st.cache_data(ttl=300)
def fetch_ath_signals(symbols):
    results = []
    for symbol in symbols:
        signal = analyze_ath_strategy(symbol)
        if signal:
            results.append(signal)
    return pd.DataFrame(results)

@st.cache_data(ttl=300)
def fetch_data(symbols):
    data = {}
    for symbol in symbols:
        df = load_stock_data(symbol)
        if df is not None:
            data[symbol] = df
    return data

def build_dashboard():
    data = fetch_data(NIFTY50_SYMBOLS)
    prev_month_end = get_prev_month_end()

    results = []

    # Calculate average benchmark return from available data
    bench_returns = []
    for symbol in ["NIFTYBEES.NS", "NIFTY50", "NIFTY"]:
        if symbol in data:
            df = data[symbol]
            if len(df) > 0:
                try:
                    prev_prices = df.loc[:prev_month_end]
                    if len(prev_prices) > 0:
                        bench_prev = prev_prices.iloc[-1]["Close"]
                        bench_current = df.iloc[-1]["Close"]
                        bench_return = (bench_current - bench_prev) / bench_prev
                        bench_returns.append(bench_return)
                except:
                    pass

    bench_return = sum(bench_returns) / len(bench_returns) if bench_returns else 0

    # Stocks
    for symbol in NIFTY50_SYMBOLS:
        if symbol not in data:
            continue
        try:
            df = data[symbol]
            df = df.dropna()

            if df.empty:
                continue

            prev_prices = df.loc[:prev_month_end]
            if prev_prices.empty:
                continue

            prev_price = prev_prices.iloc[-1]["Close"]
            current_price = df.iloc[-1]["Close"]

            stock_return = (current_price - prev_price) / prev_price
            rs = stock_return - bench_return

            results.append({
                "Symbol": symbol,
                "Prev Price": prev_price,
                "Current Price": current_price,
                "Return %": stock_return * 100,
                "RS %": rs * 100
            })

        except Exception:
            continue

    df = pd.DataFrame(results)
    df = df.sort_values(by="RS %", ascending=False)
    df["Rank"] = range(1, len(df) + 1)

    return df, bench_return * 100

@st.cache_data(ttl=300)
def load_summary():
    try:
        df = pd.read_csv('backtest_results/portfolio_equity.csv')
        if len(df) > 0:
            initial = df['Portfolio'].iloc[0]
            final = df['Portfolio'].iloc[-1]
            total_pnl = final - initial
            total_return = (final - initial) / initial * 100 if initial > 0 else 0
            
            # Calculate CAGR (simplified)
            dates = pd.to_datetime(df['Date'])
            years = (dates.iloc[-1] - dates.iloc[0]).days / 365.25
            cagr = ((final / initial) ** (1/years) - 1) * 100 if years > 0 and initial > 0 else 0
            
            return {
                'Initial Capital': initial,
                'Final Capital': final,
                'Total PnL': total_pnl,
                'Total Return %': total_return,
                'CAGR': cagr
            }
    except FileNotFoundError:
        return None

@st.cache_data(ttl=300)
def load_trades():
    try:
        df = pd.read_csv('backtest_results/trade_log.csv')
        return df
    except FileNotFoundError:
        return pd.DataFrame()

# -----------------------------
# UI
# -----------------------------
st.title("📊 220EMA Momentum Dashboard")

st.caption("Strategy: Current Price vs Previous Month-End | Ranked by Relative Strength")

# Refresh button
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

# Create tabs
tab1, tab2, tab3 = st.tabs(["📈 Momentum Dashboard", "🎯 ATH Strategy", "📑 Trades"])

with tab1:
    # Load data
    df, bench_ret = build_dashboard()

    # METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric("Benchmark Return", f"{bench_ret:.2f}%")
    col2.metric("Top Stock", df.iloc[0]["Symbol"])
    col3.metric("Top RS", f"{df.iloc[0]['RS %']:.2f}%")

    # TOP 5
    st.subheader("🔥 Top 5 Momentum Stocks")
    st.dataframe(df.head(5), width='stretch')

    # FULL TABLE
    st.subheader("📋 Full Ranking")
    st.dataframe(df.style.format({
        "Prev Price": "{:.2f}",
        "Current Price": "{:.2f}",
        "Return %": "{:.2f}",
        "RS %": "{:.2f}"
        }).background_gradient(subset=["RS %"], cmap="RdYlGn"), width='stretch')

    # DOWNLOAD
    st.download_button(
        "📥 Download CSV",
        df.to_csv(index=False),
        file_name="momentum_dashboard.csv"
    )

    st.caption("⚠️ Uses same-time close logic (lookahead bias). For research only.")

with tab2:
    st.subheader("🎯 All-Time High (ATH) Strategy")
    st.caption("BUY Signal: Stock closes at new ATH AND price > 220 EMA")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        show_only_signals = st.toggle("Show only BUY signals", value=False)
    with col2:
        show_new_ath = st.toggle("Show only New ATH", value=False)
    
    signals_df = fetch_ath_signals(NIFTY50_SYMBOLS)
    
    # Apply filters
    if show_only_signals:
        signals_df = signals_df[signals_df["BUY Signal"] == True]
    elif show_new_ath:
        signals_df = signals_df[signals_df["New ATH"] == True]
    
    # Count signals
    buy_signals = signals_df[signals_df["BUY Signal"] == True]
    new_aths = signals_df[signals_df["New ATH"] == True]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Stocks", len(signals_df))
    col2.metric("New ATH", len(new_aths))
    col3.metric("BUY Signals", len(buy_signals))
    
    # Display BUY signals first
    st.subheader("📊 Signals")
    st.dataframe(signals_df.sort_values(by="BUY Signal", ascending=False).style.format({
        "Close": "{:.2f}",
        "ATH": "{:.2f}",
        "EMA220": "{:.2f}"
        }).background_gradient(subset=["Close", "ATH"], cmap="Greens"), width='stretch')
    
    st.download_button(
        "📥 Download Signals CSV",
        signals_df.to_csv(index=False),
        file_name="ath_signals.csv"
    )

with tab2:
    trades_df = load_trades()
    summary_data = load_summary()
    
    if summary_data is None:
        st.warning("No summary data found. Please run the backtest first.")
    else:
        # Display summary metrics from portfolio performance
        st.subheader("📊 Trading Summary")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Invested", f"₹{summary_data['Initial Capital']:,.2f}")
        col2.metric("Current Worth", f"₹{summary_data['Final Capital']:,.2f}")
        col3.metric("Total Profit", f"₹{summary_data['Total PnL']:,.2f}")
        col4.metric("Profit %", f"{summary_data['Total Return %']:.2f}%")
        col5.metric("CAGR", f"{summary_data['CAGR']:.2f}%")
    
    if trades_df.empty:
        st.warning("No trades data found.")
    else:
        st.subheader("📑 All Trades")
        styled_trades = trades_df.style.format({
            "Entry Price": "{:.2f}",
            "Exit Price": "{:.2f}",
            "Return %": "{:.2f}%"
        }).background_gradient(subset=["Return %"], cmap="RdYlGn")
        st.dataframe(styled_trades, width='stretch')

        st.download_button(
            "📥 Download Trades CSV",
            trades_df.to_csv(index=False),
            file_name="trades.csv"
        )