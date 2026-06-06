import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="Stock Charts", layout="wide")
st.title("Stock Price Comparison")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    tickers_input = st.text_input(
        "Stocks (comma separated)",
        value="AAPL, MSFT, GOOGL",
        help="e.g. AAPL, MSFT, TSLA, AMZN"
    )

    period_options = {
        "1 Month":   "1mo",
        "3 Months":  "3mo",
        "6 Months":  "6mo",
        "1 Year":    "1y",
        "2 Years":   "2y",
        "5 Years":   "5y",
        "Max":       "max",
    }
    period_label = st.selectbox("Period", list(period_options.keys()), index=3)
    period = period_options[period_label]

    chart_type = st.radio("Chart type", ["Line", "Candlestick"], index=0)

    st.subheader("Overlays")
    show_ma20  = st.checkbox("MA 20",           value=True)
    show_ma50  = st.checkbox("MA 50",           value=True)
    show_ma200 = st.checkbox("MA 200",          value=False)
    show_bb    = st.checkbox("Bollinger Bands", value=False)
    show_ema   = st.checkbox("EMA 20",          value=False)

    st.subheader("Panels")
    show_volume = st.checkbox("Volume",          value=True)
    show_rsi    = st.checkbox("RSI (14)",        value=True)
    show_macd   = st.checkbox("MACD",            value=False)
    show_pct    = st.checkbox("% Change comparison", value=False)


# ── Helpers ───────────────────────────────────────────────────────────────────
def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def compute_macd(series):
    ema12  = series.ewm(span=12, adjust=False).mean()
    ema26  = series.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal
    return macd, signal, hist


def compute_bb(series, window=20):
    ma    = series.rolling(window).mean()
    std   = series.rolling(window).std()
    upper = ma + 2 * std
    lower = ma - 2 * std
    return upper, ma, lower


# ── Fetch data ────────────────────────────────────────────────────────────────
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

if not tickers:
    st.warning("Enter at least one ticker.")
    st.stop()

data = {}
with st.spinner("Fetching data..."):
    for ticker in tickers:
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if df.empty:
                st.warning(f"{ticker}: no data found — check the symbol.")
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[ticker] = df
        except Exception as e:
            st.error(f"{ticker}: {e}")

if not data:
    st.error("No data loaded.")
    st.stop()


# ── % Change comparison ───────────────────────────────────────────────────────
if show_pct and len(data) > 1:
    st.subheader("% Change from start")
    fig_pct = go.Figure()
    for ticker, df in data.items():
        pct = (df["Close"] / df["Close"].iloc[0] - 1) * 100
        fig_pct.add_trace(go.Scatter(x=df.index, y=pct, name=ticker, mode="lines"))
    fig_pct.update_layout(
        yaxis_title="% Change",
        hovermode="x unified",
        height=350,
        margin=dict(l=0, r=0, t=20, b=0),
    )
    fig_pct.add_hline(y=0, line_dash="dash", line_color="grey")
    st.plotly_chart(fig_pct, use_container_width=True)


# ── Per-stock charts ──────────────────────────────────────────────────────────
colors = ["#2196F3", "#FF5722", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4"]

for idx, (ticker, df) in enumerate(data.items()):
    color = colors[idx % len(colors)]
    close = df["Close"]

    # Decide subplot rows
    rows, row_heights = [1], [0.55]
    if show_volume: rows.append(len(rows) + 1); row_heights.append(0.15)
    if show_rsi:    rows.append(len(rows) + 1); row_heights.append(0.15)
    if show_macd:   rows.append(len(rows) + 1); row_heights.append(0.15)
    total_rows = len(rows)

    subplot_titles = [ticker]
    if show_volume: subplot_titles.append("Volume")
    if show_rsi:    subplot_titles.append("RSI (14)")
    if show_macd:   subplot_titles.append("MACD")

    fig = make_subplots(
        rows=total_rows, cols=1,
        shared_xaxes=True,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
        vertical_spacing=0.04,
    )

    # ── Price ──────────────────────────────────────────────────────────────
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"],   close=df["Close"],
            name=ticker, showlegend=False,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=close, name=ticker,
            line=dict(color=color, width=1.5), showlegend=False,
        ), row=1, col=1)

    # ── Moving averages ────────────────────────────────────────────────────
    ma_configs = [
        (show_ma20,  20,  "#FFC107", "MA20"),
        (show_ma50,  50,  "#FF5722", "MA50"),
        (show_ma200, 200, "#9C27B0", "MA200"),
    ]
    for show, window, ma_color, label in ma_configs:
        if show and len(close) >= window:
            fig.add_trace(go.Scatter(
                x=df.index, y=close.rolling(window).mean(),
                name=label, line=dict(color=ma_color, width=1),
            ), row=1, col=1)

    if show_ema:
        fig.add_trace(go.Scatter(
            x=df.index, y=close.ewm(span=20, adjust=False).mean(),
            name="EMA20", line=dict(color="#00BCD4", width=1, dash="dot"),
        ), row=1, col=1)

    if show_bb:
        upper, mid, lower = compute_bb(close)
        fig.add_trace(go.Scatter(
            x=df.index, y=upper, name="BB Upper",
            line=dict(color="rgba(150,150,150,0.5)", width=1),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=lower, name="BB Lower",
            fill="tonexty", fillcolor="rgba(150,150,150,0.1)",
            line=dict(color="rgba(150,150,150,0.5)", width=1),
        ), row=1, col=1)

    current_row = 2

    # ── Volume ─────────────────────────────────────────────────────────────
    if show_volume:
        vol_colors = ["#EF5350" if df["Close"].iloc[i] < df["Open"].iloc[i]
                      else "#26A69A" for i in range(len(df))]
        fig.add_trace(go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=vol_colors, name="Volume", showlegend=False,
        ), row=current_row, col=1)
        current_row += 1

    # ── RSI ────────────────────────────────────────────────────────────────
    if show_rsi:
        rsi = compute_rsi(close)
        fig.add_trace(go.Scatter(
            x=df.index, y=rsi, name="RSI",
            line=dict(color="#FF9800", width=1.5), showlegend=False,
        ), row=current_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red",   row=current_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
        fig.update_yaxes(range=[0, 100], row=current_row, col=1)
        current_row += 1

    # ── MACD ───────────────────────────────────────────────────────────────
    if show_macd:
        macd, signal, hist = compute_macd(close)
        hist_colors = ["#EF5350" if v < 0 else "#26A69A" for v in hist]
        fig.add_trace(go.Bar(
            x=df.index, y=hist, marker_color=hist_colors,
            name="MACD Hist", showlegend=False,
        ), row=current_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=macd, name="MACD",
            line=dict(color="#2196F3", width=1.5),
        ), row=current_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=signal, name="Signal",
            line=dict(color="#FF5722", width=1.5),
        ), row=current_row, col=1)

    # ── Layout ─────────────────────────────────────────────────────────────
    last_close = close.iloc[-1]
    first_close = close.iloc[0]
    pct_change = (last_close / first_close - 1) * 100
    pct_str = f"+{pct_change:.1f}%" if pct_change >= 0 else f"{pct_change:.1f}%"
    pct_color = "green" if pct_change >= 0 else "red"

    st.markdown(
        f"### {ticker} &nbsp; <span style='color:{pct_color}'>{pct_str}</span> &nbsp;"
        f"<span style='font-size:0.9em;color:grey'>Last: ${last_close:.2f}</span>",
        unsafe_allow_html=True,
    )

    fig.update_layout(
        height=250 + total_rows * 120,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")

    st.plotly_chart(fig, use_container_width=True)

    # ── Stats table ────────────────────────────────────────────────────────
    with st.expander(f"{ticker} — Key stats"):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Last Close",   f"${last_close:.2f}")
        col2.metric("Period High",  f"${df['High'].max():.2f}")
        col3.metric("Period Low",   f"${df['Low'].min():.2f}")
        col4.metric("Period Return", pct_str)
