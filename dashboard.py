import concurrent.futures
import time
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from ta.trend import EMAIndicator
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="100-Stock Intraday Scanner", layout="wide")

# Auto-refresh dashboard automatically every 10 seconds
st_autorefresh(interval=10000, key="stock_scanner_refresh")

st.title("⚡ 100-Stock Automated Intraday Scanner & Decision Dashboard")
st.caption("Live Nifty 100 Parallel Scan | Auto-Refreshes Every 10 Seconds")

# Nifty 100 Stock List
WATCHLIST_100 = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "TATAMOTORS.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
    "ITC.NS",
    "BAJFINANCE.NS",
    "LT.NS",
    "KOTAKBANK.NS",
    "TATASTEEL.NS",
    "MARUTI.NS",
    "SUNPHARMA.NS",
    "ADANIENT.NS",
    "ONGC.NS",
    "AXISBANK.NS",
    "TITAN.NS",
    "NTPC.NS",
    "HCLTECH.NS",
    "WIPRO.NS",
    "ULTRACEMCO.NS",
    "POWERGRID.NS",
    "M&M.NS",
    "HINDUNILVR.NS",
    "COALINDIA.NS",
    "BAJAJFINSV.NS",
    "JSWSTEEL.NS",
    "ADANIPORTS.NS",
    "TRENT.NS",
    "GRASIM.NS",
    "BEL.NS",
    "HINDALCO.NS",
    "NESTLEIND.NS",
    "BPCL.NS",
    "SIEMENS.NS",
    "TECHM.NS",
    "LTIM.NS",
    "VBL.NS",
    "HEROMOTOCO.NS",
    "CIPLA.NS",
    "BRITANNIA.NS",
    "EICHERMOT.NS",
    "HAL.NS",
    "TATASETEL.NS",
    "IOC.NS",
    "DIVISLAB.NS",
    "DLF.NS",
    "APOLLOHOSP.NS",
    "TATACONSUM.NS",
    "CHOLAFIN.NS",
    "PIDILITIND.NS",
    "DRREDDY.NS",
    "GAIL.NS",
    "BOSCHLTD.NS",
    "ABB.NS",
    "AMBUJACEM.NS",
    "INDUSINDBK.NS",
    "SHRIRAMFIN.NS",
    "BANKBARODA.NS",
    "CANBK.NS",
    "TORNTPHARM.NS",
    "COLPAL.NS",
    "UNITDSPR.NS",
    "POLYCAB.NS",
    "PNB.NS",
    "VEDL.NS",
    "SBILIFE.NS",
    "HDFCLIFE.NS",
    "ICICIPRULI.NS",
    "LODHA.NS",
    "JINDALSTEL.NS",
    "LUPIN.NS",
    "TATAELXSI.NS",
    "ZYDUSLIFE.NS",
    "TVSMOTOR.NS",
    "SRF.NS",
    "MOTHERSON.NS",
    "AUROPHARMA.NS",
    "BERGEPAINT.NS",
    "NAUKRI.NS",
    "PERSISTENT.NS",
    "ASTRAL.NS",
    "CONCOR.NS",
    "MUTHOOTFIN.NS",
    "OFSS.NS",
    "PFC.NS",
    "RECLTD.NS",
    "MAXHEALTH.NS",
    "TIINDIA.NS",
    "IDEA.NS",
    "MRF.NS",
    "BALKRISIND.NS",
    "PIIND.NS",
    "ASHOKLEY.NS",
    "CUMMINSIND.NS",
    "IDFCFIRSTB.NS",
    "GMRINFRA.NS",
    "NMDC.NS",
]

# Initialize Session State timers for tracking idle "WAIT" stocks
if "wait_timers" not in st.session_state:
    st.session_state.wait_timers = {ticker: time.time() for ticker in WATCHLIST_100}


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
        avg_vol = df["Volume"].mean()
        rvol = round(float(latest["Volume"] / avg_vol), 2)

        signal = "WAIT"
        reason = "Consolidating near VWAP; awaiting volume surge."
        entry, sl, target = price, price, price
        vip_eligible = False

        if price > vwap and price > ema9 and rvol > 1.5:
            signal = "BUY"
            reason = f"Price above VWAP (₹{vwap}) & 9-EMA with {rvol}x volume surge."
            entry = round(price * 1.001, 2)
            sl = round(min(vwap, price * 0.993), 2)
            target = round(entry + (entry - sl) * 2, 2)
            if rvol > 2.5:
                vip_eligible = True

        elif price < vwap and price < ema9 and rvol > 1.5:
            signal = "SELL"
            reason = f"Price broke below VWAP (₹{vwap}) on heavy selling ({rvol}x)."
            entry = round(price * 0.999, 2)
            sl = round(max(vwap, price * 1.007), 2)
            target = round(entry - (sl - entry) * 2, 2)
            if rvol > 2.5:
                vip_eligible = True

        return {
            "Ticker": ticker.replace(".NS", ""),
            "Signal": signal,
            "Price (₹)": price,
            "RVOL": rvol,
            "Condition / Reason": reason,
            "Entry Point": entry,
            "Stop-Loss (SL)": sl,
            "Target 1": target,
            "VIP": vip_eligible,
        }
    except Exception:
        return None


# Execute Parallel Multithreaded Scan across 100 stocks
results = []
current_time = time.time()
vip_stock = None

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    scanned_data = list(executor.map(analyze_stock, WATCHLIST_100))

for data in scanned_data:
    if data:
        ticker_full = data["Ticker"] + ".NS"
        if data["Signal"] == "WAIT":
            idle_time = current_time - st.session_state.wait_timers.get(
                ticker_full, current_time
            )
            if idle_time > 1800:
                data["Condition / Reason"] = (
                    "⚠️ Stagnant >30 mins. Awaiting fresh breakout signal."
                )
        else:
            st.session_state.wait_timers[ticker_full] = current_time
            if data["VIP"] and not vip_stock:
                vip_stock = data

        results.append(data)

# --- 1. VIP SPOTLIGHT SECTION ---
if vip_stock:
    st.success("🔥 VIP HIGH-CONVICTION TRADE DETECTED")
    vcol1, vcol2, vcol3, vcol4 = st.columns(4)
    vcol1.metric("Stock Ticker", vip_stock["Ticker"])
    vcol2.metric("Signal", vip_stock["Signal"])
    vcol3.metric("Entry Point", f"₹{vip_stock['Entry Point']}")
    vcol4.metric(
        "Target / SL",
        f"₹{vip_stock['Target 1']} / ₹{vip_stock['Stop-Loss (SL)']}",
    )
    st.info(f"**Trigger Reason:** {vip_stock['Condition / Reason']}")
    st.write("---")

# --- 2. MAIN 100-STOCK TABLE WITH SEARCH FILTER ---
if results:
    df_res = pd.DataFrame(results)

    # Sort table so actionable BUY and SELL signals float to the top
    df_res = df_res.sort_values(
        by="Signal", key=lambda x: x.map({"BUY": 1, "SELL": 2, "WAIT": 3})
    )

    st.subheader(f"📊 Active 100-Stock Watchlist Monitor ({len(df_res)} Loaded)")

    # Live Search Filter
    search_query = st.text_input(
        "🔍 Search Ticker or Signal (e.g., RELIANCE or BUY):", ""
    )
    if search_query:
        df_filtered = df_res[
            df_res["Ticker"].str.contains(search_query.upper(), na=False)
            | df_res["Signal"].str.contains(search_query.upper(), na=False)
        ]
        st.dataframe(df_filtered, use_container_width=True)
    else:
        st.dataframe(df_res, use_container_width=True)

    # --- 3. GRAPHICAL CHARTS SECTION ---
    col1, col2 = st.columns(2)

    with col1:
        st.write("##### 100-Stock Market Sentiment Breakdown")
        fig_pie = px.pie(
            df_res,
            names="Signal",
            title="Signal Distribution Across 100 Stocks",
            color="Signal",
            color_discrete_map={
                "BUY": "#23C552",
                "SELL": "#F84960",
                "WAIT": "#FACC15",
            },
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.write("##### Top 15 Volume Surges (RVOL)")
        top_vol_df = df_res.sort_values(by="RVOL", ascending=False).head(15)
        fig_bar = px.bar(
            top_vol_df,
            x="Ticker",
            y="RVOL",
            color="Signal",
            title="Highest Volume Activity (>1.5x)",
            color_discrete_map={
                "BUY": "#23C552",
                "SELL": "#F84960",
                "WAIT": "#FACC15",
            },
        )
        st.plotly_chart(fig_bar, use_container_width=True)
