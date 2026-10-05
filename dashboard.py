import time
import pandas as pd
import plotly.express as px
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from ta.trend import EMAIndicator
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="100-Stock Locked Trade Scanner", layout="wide")

# Auto-refresh every 15 seconds
st_autorefresh(interval=15000, key="stock_scanner_refresh")

st.title("⚡ 100-Stock Stateful Intraday Decision Scanner")
st.caption("Live Scan with Target/SL Trade Lock | Auto-Refreshes Every 15 Seconds")

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

# Initialize persistent active trade tracking memory
if "active_trades" not in st.session_state:
    st.session_state.active_trades = {}


@st.cache_data(ttl=10)
def fetch_all_stocks():
    """Bulk fetch live data for all tickers."""
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
        clean_ticker = ticker.replace(".NS", "")
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

            price = round(float(df["Close"].iloc[-1]), 2)
            vwap = round(float(vwap_series.iloc[-1]), 2)
            latest_ema = round(float(ema_series.iloc[-1]), 2)
            avg_vol = float(df["Volume"].mean())
            latest_vol = float(df["Volume"].iloc[-1])
            rvol = round(latest_vol / avg_vol, 2) if avg_vol > 0 else 1.0

            # --- CHECK LOCKED TRADE POSITIONS FIRST ---
            if clean_ticker in st.session_state.active_trades:
                trade = st.session_state.active_trades[clean_ticker]
                signal = trade["Signal"]
                entry = trade["Entry Point"]
                sl = trade["Stop-Loss (SL)"]
                target = trade["Target 1"]

                # Evaluation for ACTIVE BUY Trade
                if signal == "BUY":
                    if price >= target:
                        # Target Hit -> Exit position and revert back to scan
                        del st.session_state.active_trades[clean_ticker]
                        signal = "WAIT"
                        reason = f"🎯 TARGET HIT at ₹{price}! Position Closed."
                        entry, sl, target = price, price, price
                    elif price <= sl:
                        # Stop Loss Hit -> Exit position and revert back to scan
                        del st.session_state.active_trades[clean_ticker]
                        signal = "WAIT"
                        reason = f"🛑 STOP-LOSS HIT at ₹{price}! Position Closed."
                        entry, sl, target = price, price, price
                    else:
                        # Trade still active -> Lock state in BUY
                        reason = f"🔒 LOCKED IN BUY | Target: ₹{target} | SL: ₹{sl}"

                # Evaluation for ACTIVE SELL Trade
                elif signal == "SELL":
                    if price <= target:
                        # Target Hit -> Exit position
                        del st.session_state.active_trades[clean_ticker]
                        signal = "WAIT"
                        reason = f"🎯 TARGET HIT at ₹{price}! Position Closed."
                        entry, sl, target = price, price, price
                    elif price >= sl:
                        # Stop Loss Hit -> Exit position
                        del st.session_state.active_trades[clean_ticker]
                        signal = "WAIT"
                        reason = f"🛑 STOP-LOSS HIT at ₹{price}! Position Closed."
                        entry, sl, target = price, price, price
                    else:
                        # Trade still active -> Lock state in SELL
                        reason = f"🔒 LOCKED IN SELL | Target: ₹{target} | SL: ₹{sl}"

            # --- NO ACTIVE TRADE: CHECK FOR NEW BUY/SELL SIGNALS ---
            else:
                signal = "WAIT"
                reason = "Consolidating near VWAP; awaiting volume surge."
                entry, sl, target = price, price, price

                # Check BUY Trigger
                if price > vwap and price > latest_ema and rvol > 1.5:
                    signal = "BUY"
                    entry = round(price * 1.001, 2)
                    sl = round(min(vwap, price * 0.993), 2)
                    target = round(entry + (entry - sl) * 2, 2)
                    reason = f"🚀 BUY Triggered! VWAP ₹{vwap}, RVOL {rvol}x."

                    # Lock into active trades state memory
                    st.session_state.active_trades[clean_ticker] = {
                        "Signal": "BUY",
                        "Entry Point": entry,
                        "Stop-Loss (SL)": sl,
                        "Target 1": target,
                    }

                # Check SELL Trigger
                elif price < vwap and price < latest_ema and rvol > 1.5:
                    signal = "SELL"
                    entry = round(price * 0.999, 2)
                    sl = round(max(vwap, price * 1.007), 2)
                    target = round(entry - (sl - entry) * 2, 2)
                    reason = f"🔻 SELL Triggered! Break below VWAP ₹{vwap}, RVOL {rvol}x."

                    # Lock into active trades state memory
                    st.session_state.active_trades[clean_ticker] = {
                        "Signal": "SELL",
                        "Entry Point": entry,
                        "Stop-Loss (SL)": sl,
                        "Target 1": target,
                    }

            results.append(
                {
                    "Ticker": clean_ticker,
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

# --- DISPLAY STREAMLIT DASHBOARD ---
if results:
    df_res = pd.DataFrame(results)

    # Sort table: Active BUY/SELL stay at top
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
            title="Signal Breakdown",
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

    # Manual reset button to clear locked active trades if needed
    if st.button("🔄 Reset All Locked Active Trades"):
        st.session_state.active_trades = {}
        st.rerun()

else:
    st.warning("⚠️ Market data temporary delay or market closed. Retrying...")
