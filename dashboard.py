import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from ta.trend import EMAIndicator
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Advanced Live Intraday Scanner", layout="wide")

# Auto-refresh app every 10 seconds (10,000 ms)
st_autorefresh(interval=10000, key="stock_scanner_refresh")

st.title("⚡ Dynamic Intraday Scanner & Decision Dashboard")
st.caption("Free Live Public Market Scan | Auto-Refreshes Every 10 Seconds")

# Broader pool to rotate stocks from
EXTENDED_UNIVERSE = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "TATAMOTORS.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "AXISBANK.NS",
    "ITC.NS",
    "LT.NS",
    "KOTAKBANK.NS",
]

# Initialize Session State memory
if "watchlist" not in st.session_state:
    st.session_state.watchlist = EXTENDED_UNIVERSE[:5]

if "wait_timers" not in st.session_state:
    st.session_state.wait_timers = {
        ticker: time.time() for ticker in st.session_state.watchlist
    }


def analyze_stock(ticker):
    try:
        df = yf.download(ticker, period="1d", interval="5m", progress=False)
        if len(df) < 10:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

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
        rvol = round(float(latest["Volume"] / df["Volume"].mean()), 2)

        signal = "WAIT"
        reason = "Price consolidating near VWAP."
        entry, sl, target = price, price, price
        vip_eligible = False

        if price > vwap and price > ema9 and rvol > 1.5:
            signal = "BUY"
            reason = f"Breakout above VWAP (₹{vwap}) with {rvol}x Volume Surge."
            entry = round(price * 1.001, 2)
            sl = round(min(vwap, price * 0.993), 2)
            target = round(entry + (entry - sl) * 2, 2)

            if rvol > 2.5:
                vip_eligible = True

        elif price < vwap and price < ema9 and rvol > 1.5:
            signal = "SELL"
            reason = f"Breakdown below VWAP (₹{vwap}) with {rvol}x Selling Surge."
            entry = round(price * 0.999, 2)
            sl = round(max(vwap, price * 1.007), 2)
            target = round(entry - (sl - entry) * 2, 2)

            if rvol > 2.5:
                vip_eligible = True

        return {
            "Ticker": ticker.replace(".NS", ""),
            "Signal": signal,
            "Price": price,
            "RVOL": rvol,
            "Reason": reason,
            "Entry": entry,
            "SL": sl,
            "Target": target,
            "VIP": vip_eligible,
        }
    except Exception:
        return None


# Execute Scan
results = []
current_time = time.time()
vip_stock = None

for i, ticker in enumerate(list(st.session_state.watchlist)):
    data = analyze_stock(ticker)

    if data:
        # Check if stock has been in "WAIT" for > 30 minutes (1800 seconds)
        if data["Signal"] == "WAIT":
            idle_time = current_time - st.session_state.wait_timers.get(
                ticker, current_time
            )

            if idle_time > 1800:
                # Find replacement stock not currently displayed
                unused_stocks = [
                    s
                    for s in EXTENDED_UNIVERSE
                    if s not in st.session_state.watchlist
                ]
                if unused_stocks:
                    new_ticker = unused_stocks[0]
                    st.session_state.watchlist[i] = new_ticker
                    st.session_state.wait_timers[new_ticker] = current_time
                    st.toast(
                        f"🔄 Replaced stagnant stock {ticker.replace('.NS','')} with"
                        f" {new_ticker.replace('.NS','')}"
                    )
                    continue
        else:
            # Lock active trade signals (reset wait timer)
            st.session_state.wait_timers[ticker] = current_time

            if data["VIP"] and not vip_stock:
                vip_stock = data

        results.append(data)

# --- 1. VIP SPOTLIGHT SECTION ---
if vip_stock:
    st.success("🔥 VIP HIGH-CONVICTION OPPORTUNITY DETECTED")
    vcol1, vcol2, vcol3, vcol4 = st.columns(4)
    vcol1.metric("Stock Ticker", vip_stock["Ticker"])
    vcol2.metric("Signal", vip_stock["Signal"])
    vcol3.metric("Entry Point", f"₹{vip_stock['Entry']}")
    vcol4.metric("Target / SL", f"₹{vip_stock['Target']} / ₹{vip_stock['SL']}")
    st.info(f"**Trigger Reason:** {vip_stock['Reason']}")
    st.write("---")

# --- 2. MAIN DASHBOARD DATA TABLE ---
if results:
    df_res = pd.DataFrame(results)

    st.subheader("📊 Top Active Stocks Monitor")
    st.dataframe(df_res, use_container_width=True)

    # --- 3. GRAPHICAL CHARTS SECTION ---
    col1, col2 = st.columns(2)

    with col1:
        st.write("##### Signal Distribution Ratio")
        fig_pie = px.pie(
            df_res,
            names="Signal",
            title="Market Sentiment Breakdown",
            color="Signal",
            color_discrete_map={
                "BUY": "#23C552",
                "SELL": "#F84960",
                "WAIT": "#FACC15",
            },
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.write("##### Price vs Target Comparison")
        fig_bar = go.Figure(
            data=[
                go.Bar(name="Current Price", x=df_res["Ticker"], y=df_res["Price"]),
                go.Bar(name="Target Price", x=df_res["Ticker"], y=df_res["Target"]),
            ]
        )
        fig_bar.update_layout(
            barmode="group", title="Live Price Target Projection"
        )
        st.plotly_chart(fig_bar, use_container_width=True)
