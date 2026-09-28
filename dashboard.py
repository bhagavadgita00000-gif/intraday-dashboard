import time
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from ta.trend import EMAIndicator
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="100-Stock Intraday Scanner", layout="wide")

# Auto-refresh every 30 seconds cleanly
st_autorefresh(interval=30000, key="stock_scanner_refresh")

st.title("⚡ 100-Stock Automated Intraday Scanner")
st.caption("Live Bulk Scan | Auto-Refreshes Every 30 Seconds")

# Nifty 100 List
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


@st.cache_data(ttl=25)
def fetch_all_stocks():
    """Bulk download all tickers in a single yfinance request to avoid IP rate limits."""
    try:
        data = yf.download(
            tickers=WATCHLIST_100,
            period="1d",
            interval="5m",
            group_by="ticker",
            progress=False,
            threads=True,
        )
        return data
    except Exception:
        return None


data_batch = fetch_all_stocks()
results = []

if data_batch is not None and not data_batch.empty:
    for ticker in WATCHLIST_100:
        try:
            if len(WATCHLIST_100) > 1:
                if ticker in data_batch.columns.levels[0]:
                    df = data_batch[ticker].dropna(how="all")
                else:
                    continue
            else:
                df = data_batch

            if df.empty or len(df) < 5:
                continue

            vwap_series = VolumeWeightedAveragePrice(
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                volume=df["Volume"],
            ).volume_weighted_average_price()

            ema_series = EMAIndicator(close=df["Close"], window=9).ema_indicator()

            latest_close = float(df["Close"].iloc[-1])
            latest_vwap = float(vwap_series.iloc[-1])
            latest_ema = float(ema_series.iloc[-1])
            latest_vol = float(df["Volume"].iloc[-1])
            avg_vol = float(df["Volume"].mean())

            rvol = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0
            price = round(latest_close, 2)
            vwap = round(latest_vwap, 2)

            signal = "WAIT"
            reason = "Consolidating near VWAP; awaiting volume surge."
            entry, sl, target = price, price, price

            if price > vwap and price > latest_ema and rvol > 1.5:
                signal = "BUY"
                reason = f"Price above VWAP (₹{vwap}) & 9-EMA with {rvol}x volume surge."
                entry = round(price * 1.001, 2)
                sl = round(min(vwap, price * 0.993), 2)
                target = round(entry + (entry - sl) * 2, 2)

            elif price < vwap and price < latest_ema and rvol > 1.5:
                signal = "SELL"
                reason = f"Price broke below VWAP (₹{vwap}) on heavy selling ({rvol}x)."
                entry = round(price * 0.999, 2)
                sl = round(max(vwap, price * 1.007), 2)
                target = round(entry - (sl - entry) * 2, 2)

            results.append(
                {
                    "Ticker": ticker.replace(".NS", ""),
                    "Signal": signal,
                    "Price (₹)": price,
                    "RVOL": rvol,
                    "Condition / Reason": reason,
                    "Entry Point": entry,
                    "Stop-Loss (SL)": sl,
                    "Target 1": target,
                }
            )
        except Exception:
            continue

if results:
    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values(
        by="Signal", key=lambda x: x.map({"BUY": 1, "SELL": 2, "WAIT": 3})
    )

    st.subheader(f"📊 Active Watchlist Scanner ({len(df_res)} Loaded)")

    search_query = st.text_input("🔍 Filter Ticker or Signal:", "")
    if search_query:
        df_filtered = df_res[
            df_res["Ticker"].str.contains(search_query.upper(), na=False)
            | df_res["Signal"].str.contains(search_query.upper(), na=False)
        ]
        st.dataframe(df_filtered, use_container_width=True)
    else:
        st.dataframe(df_res, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        fig_pie = px.pie(
            df_res,
            names="Signal",
            title="Signal Distribution",
            color="Signal",
            color_discrete_map={
                "BUY": "#23C552",
                "SELL": "#F84960",
                "WAIT": "#FACC15",
            },
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        top_vol_df = df_res.sort_values(by="RVOL", ascending=False).head(15)
        fig_bar = px.bar(
            top_vol_df,
            x="Ticker",
            y="RVOL",
            color="Signal",
            title="Top 15 Volume Surges (RVOL)",
            color_discrete_map={
                "BUY": "#23C552",
                "SELL": "#F84960",
                "WAIT": "#FACC15",
            },
        )
        st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.warning("⚠️ Market data temporary delay or market closed. Retrying...")
