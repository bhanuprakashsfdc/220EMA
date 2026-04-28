import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import matplotlib.pyplot as plt

# ---------------- CONFIG ----------------
DATA_FOLDER = "data"
INITIAL_CAPITAL = 100000
STOP_LOSS = 0.15
TRANSACTION_COST = 0.001
EMA_PERIOD = 220
MIN_DAYS = 250

BENCHMARK = "NIFTYBEES.NS"

# ---------------- LOAD DATA ----------------
def load_data():
    data = {}
    for file in os.listdir(DATA_FOLDER):
        if file.endswith(".csv"):
            symbol = file.replace(".csv", "")
            df = pd.read_csv(os.path.join(DATA_FOLDER, file), parse_dates=["Date"])
            df.sort_values("Date", inplace=True)

            if len(df) < MIN_DAYS:
                continue

            df["Price"] = df["Close"]

            # Indicators
            df["EMA220"] = df["Price"].ewm(span=EMA_PERIOD).mean()
            df["ATH"] = df["Price"].cummax().shift(1)

            data[symbol] = df.reset_index(drop=True)

    return data

# ---------------- BACKTEST ----------------
def backtest(data):
    capital = INITIAL_CAPITAL
    positions = {}  # symbol -> dict
    trade_log = []
    portfolio_history = []

    all_dates = sorted(set(
        date for df in data.values() for date in df["Date"]
    ))

    for current_date in all_dates:
        daily_value = capital

        # -------- CHECK EXIT --------
        for symbol in list(positions.keys()):
            df = data[symbol]
            row = df[df["Date"] == current_date]

            if row.empty:
                continue

            price = row["Price"].values[0]
            ema = row["EMA220"].values[0]

            entry_price = positions[symbol]["entry_price"]
            qty = positions[symbol]["qty"]

            stop_price = entry_price * (1 - STOP_LOSS)

            sell = False

            if price < ema:
                sell = True
            elif price <= stop_price:
                sell = True

            if sell:
                proceeds = qty * price * (1 - TRANSACTION_COST)
                capital += proceeds

                trade_log.append({
                    "Symbol": symbol,
                    "Entry Date": positions[symbol]["entry_date"],
                    "Exit Date": current_date,
                    "Entry Price": entry_price,
                    "Exit Price": price,
                    "Return %": (price / entry_price - 1) * 100
                })

                del positions[symbol]

        # -------- CHECK ENTRY --------
        candidates = []

        for symbol, df in data.items():
            if symbol in positions:
                continue

            row = df[df["Date"] == current_date]
            if row.empty:
                continue

            idx = row.index[0]

            if idx < EMA_PERIOD:
                continue

            price = row["Price"].values[0]
            ath = row["ATH"].values[0]

            if pd.notna(ath) and price > ath:
                strength = (price - ath) / ath
                candidates.append((symbol, strength, price))

        # Sort by strongest breakout
        candidates.sort(key=lambda x: x[1], reverse=True)

        if candidates:
            allocation = capital / (len(candidates) + len(positions))

            for symbol, _, price in candidates:
                if capital <= 0:
                    break

                qty = allocation // price
                if qty <= 0:
                    continue

                cost = qty * price * (1 + TRANSACTION_COST)

                if cost > capital:
                    continue

                capital -= cost

                positions[symbol] = {
                    "entry_price": price,
                    "qty": qty,
                    "entry_date": current_date
                }

        # -------- PORTFOLIO VALUE --------
        for symbol, pos in positions.items():
            df = data[symbol]
            row = df[df["Date"] == current_date]

            if not row.empty:
                price = row["Price"].values[0]
                daily_value += pos["qty"] * price

        portfolio_history.append({
            "Date": current_date,
            "Portfolio": daily_value
        })

    return pd.DataFrame(portfolio_history), pd.DataFrame(trade_log)

# ---------------- METRICS ----------------
def compute_metrics(portfolio_df):
    portfolio_df.set_index("Date", inplace=True)

    returns = portfolio_df["Portfolio"].pct_change().dropna()

    total_return = portfolio_df["Portfolio"].iloc[-1] / INITIAL_CAPITAL - 1

    years = (portfolio_df.index[-1] - portfolio_df.index[0]).days / 365
    cagr = (1 + total_return) ** (1 / years) - 1

    rolling_max = portfolio_df["Portfolio"].cummax()
    drawdown = portfolio_df["Portfolio"] / rolling_max - 1
    max_dd = drawdown.min()

    return {
        "Total Return %": total_return * 100,
        "CAGR %": cagr * 100,
        "Max Drawdown %": max_dd * 100
    }

# ---------------- BENCHMARK ----------------
def get_benchmark(start, end):
    df = yf.download(BENCHMARK, start=start, end=end, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close_col = "Adj Close" if "Adj Close" in df.columns else "Close"
    df["Returns"] = df[close_col].pct_change()
    df["Equity"] = (1 + df["Returns"]).cumprod() * INITIAL_CAPITAL
    return df

# ---------------- MAIN ----------------
def main():
    data = load_data()
    portfolio_df, trades = backtest(data)

    metrics = compute_metrics(portfolio_df)

    # restore Date as column after set_index in compute_metrics
    portfolio_df.reset_index(inplace=True)

    print("\nStrategy Metrics:")
    for k, v in metrics.items():
        print(f"{k}: {v:.2f}")

    # Benchmark
    bench = get_benchmark(portfolio_df["Date"].min(), portfolio_df["Date"].max())

    # Plot
    plt.figure(figsize=(12,6))
    plt.plot(portfolio_df["Date"], portfolio_df["Portfolio"], label="Strategy")
    plt.plot(bench.index, bench["Equity"], label="Benchmark")
    plt.legend()
    plt.title("Strategy vs Benchmark")
    plt.show()

    # Save outputs
    portfolio_df.to_csv("portfolio_equity.csv", index=False)
    trades.to_csv("trade_log.csv", index=False)

    print("\nSaved: portfolio_equity.csv & trade_log.csv")

if __name__ == "__main__":
    main()