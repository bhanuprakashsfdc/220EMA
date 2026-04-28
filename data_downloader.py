import os
import pandas as pd
import yfinance as yf
from datetime import datetime

# -------- CONFIG --------
INPUT_FILE = "nifty500_symbols.csv"
OUTPUT_FOLDER = "data"
START_DATE = "2010-01-01"
END_DATE = datetime.today().strftime('%Y-%m-%d')

# Ensure output folder exists
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -------- LOAD SYMBOLS --------
symbols_df = pd.read_csv(INPUT_FILE)

if "Symbol" not in symbols_df.columns:
    raise ValueError("CSV must contain 'Symbol' column")

symbols = symbols_df["Symbol"].dropna().unique().tolist()

# Add .NS suffix for NSE stocks
symbols = [symbol.strip().upper() + ".NS" for symbol in symbols]

print(f"Total stocks to download: {len(symbols)}")

# -------- DOWNLOAD DATA --------
for symbol in symbols:
    try:
        print(f"Downloading: {symbol}")

        df = yf.download(
            symbol,
            start=START_DATE,
            end=END_DATE,
            interval="1d",
            progress=False,
            auto_adjust=False
        )

        if df.empty:
            print(f"⚠️ No data for {symbol}")
            continue

         # Reset index for clean CSV
         df.reset_index(inplace=True)

         # Flatten multi-level columns (yfinance returns symbol as second level)
         if isinstance(df.columns, pd.MultiIndex):
             df.columns = [col[0] for col in df.columns]

         # Save file
         filename = os.path.join(OUTPUT_FOLDER, f"{symbol.replace('.NS','')}.csv")
         df.to_csv(filename, index=False)

    except Exception as e:
        print(f"❌ Error downloading {symbol}: {e}")

print("✅ Download completed!")