import time
import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from ta.trend import EMAIndicator
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Intraday Scanner Dashboard", layout="wide")

# ⚡ AUTO-REFRESH TRIGGER: Refreshes page automatically every 10 seconds (10000 ms)
count = st_autorefresh(interval=10000, limit=None, key="stock_scanner_refresh")

st.title("⚡ Automated Intraday Stock Scanner & Decision Dashboard")
st.caption(
    f"Live scanning active | Auto-refreshed count: {count} | Updates every 10"
    " seconds"
)

# Watchlist of high-volume liquid stocks
WATCHLIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "TATAMOTORS.NS",
    "SBIN.NS",
]


def analyze_stock(ticker):
    try:
        # Fetch 5-minute intraday data
        df = yf.download(ticker, period="1d", interval="5m", progress=False)
        if len(df) < 10:
            return None

        # Flatten multi-index columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Calculate Technical Indicators
        df["VWAP"] = VolumeWeightedAveragePrice(
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            volume=df["Volume"],
        ).volume_weighted_average_price()
        df["EMA_9"] = EMAIndicator(close=df["Close"], window=9).ema_indicator()

        latest = df.iloc[-1]

        price = round(float(latest["Close"]), 2)
        vwap = round(float(latest["VWAP"]), 2)
        ema9 = round(float(latest["EMA_9"]), 2)
        avg_vol = df["Volume"].mean()
        rvol = round(float(latest["Volume"] / avg_vol), 2)

        # Logic Engine for Signal & Reason Generation
        signal = "WAIT"
        reason = "Consolidating; awaiting volume breakout."
        entry = price
        sl = price
        target = price
        next_step = "MONITORING: Order imbalance neutral. Keep on watchlist."

        if price > vwap and price > ema9 and rvol > 1.5:
            signal = "BUY"
            reason = (
                f"Price (₹{price}) above VWAP (₹{vwap}) & 9-EMA on strong RVOL"
                f" ({rvol}x)."
            )
            entry = round(price * 1.001, 2)
            sl = round(min(vwap, price * 0.993), 2)
            target = round(entry + (entry - sl) * 2, 2)
            next_step = (
                f"HOLD: Momentum bullish. If price hits"
                f" ₹{round(entry + (target-entry)*0.5, 2)}, trail SL to"
                f" ₹{entry} (Break-even)."
            )

        elif price < vwap and price < ema9 and rvol > 1.5:
            signal = "SELL"
            reason = (
                f"Price (₹{price}) broke below VWAP (₹{vwap}) with selling"
                f" volume surge ({rvol}x)."
            )
            entry = round(price * 0.999, 2)
            sl = round(max(vwap, price * 1.007), 2)
            target = round(entry - (sl - entry) * 2, 2)
            next_step = (
                "HOLD: Downward trend intact. Exit immediately if price"
                f" recovers above VWAP (₹{vwap})."
            )

        return {
            "Stock Ticker": ticker.replace(".NS", ""),
            "Signal": signal,
            "Price (₹)": price,
            "RVOL": rvol,
            "Condition / Technical Reason": reason,
            "Entry Point": entry,
            "Stop-Loss (SL)": sl,
            "Target 1": target,
            "Active Position Management / Next Step": next_step,
        }
    except Exception:
        return None


# Run Scan Loop
results = []
for ticker in WATCHLIST:
    data = analyze_stock(ticker)
    if data:
        results.append(data)

# Output Table
if results:
    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(
        by="Signal", key=lambda x: x.map({"BUY": 1, "SELL": 2, "WAIT": 3})
    ).head(5)
    st.dataframe(res_df, use_container_width=True)

st.write("---")
st.info(
    "💡 Auto-refresh active: Screen updates automatically every 10 seconds with"
    " live tick prices."
)
