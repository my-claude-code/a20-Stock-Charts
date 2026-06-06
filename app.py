import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.figure_factory as ff
from plotly.subplots import make_subplots
from datetime import datetime

st.set_page_config(page_title="Stock Charts", layout="wide")
st.title("Stock Price Comparison")

# ── Shortcut button styling ───────────────────────────────────────────────────
st.markdown("""
<style>
div[data-testid="column"] button {
    width: 100%;
    border-radius: 20px;
    font-weight: bold;
    font-size: 0.8em;
}
</style>
""", unsafe_allow_html=True)

# ── Shortcut toggles (session state) ─────────────────────────────────────────
SHORTCUTS = {
    "KO":   ("KO",   "Coca-Cola"),
    "SPY":  ("SPY",  "S&P 500"),
    "QQQ":  ("QQQ",  "Nasdaq"),
    "MSFT": ("MSFT", "Microsoft"),
    "PG":   ("PG",   "P&G"),
}

for key in SHORTCUTS:
    if f"active_{key}" not in st.session_state:
        st.session_state[f"active_{key}"] = False

st.markdown("**Quick add:**")
cols = st.columns(len(SHORTCUTS))
for col, (key, (ticker, label)) in zip(cols, SHORTCUTS.items()):
    active = st.session_state[f"active_{key}"]
    icon   = "🟢" if active else "🔴"
    if col.button(f"{icon} {label}", key=f"btn_{key}"):
        st.session_state[f"active_{key}"] = not active
        st.rerun()

st.markdown("---")

# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")

    # Merge active shortcuts into the ticker list
    active_shortcuts = [t for key, (t, _) in SHORTCUTS.items()
                        if st.session_state[f"active_{key}"]]

    tickers_input = st.text_input(
        "Stocks (comma separated)",
        value="",
        help="e.g. AAPL, MSFT, TSLA, AMZN"
    )

    period_options = {
        "1 Month":  "1mo",
        "3 Months": "3mo",
        "6 Months": "6mo",
        "1 Year":   "1y",
        "2 Years":  "2y",
        "5 Years":  "5y",
        "Max":      "max",
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
    show_volume = st.checkbox("Volume",  value=True)
    show_rsi    = st.checkbox("RSI (14)", value=True)
    show_macd   = st.checkbox("MACD",    value=False)


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
    return macd, signal, macd - signal


def compute_bb(series, window=20):
    ma  = series.rolling(window).mean()
    std = series.rolling(window).std()
    return ma + 2 * std, ma, ma - 2 * std


# ── Fetch data ────────────────────────────────────────────────────────────────
typed   = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
tickers = typed + [t for t in active_shortcuts if t not in typed]

if not tickers:
    st.warning("Enter at least one ticker.")
    st.stop()

data = {}
with st.spinner("Fetching data..."):
    for ticker in tickers:
        try:
            df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
            if df.empty:
                st.warning(f"{ticker}: no data found.")
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                data[ticker] = df
        except Exception as e:
            st.error(f"{ticker}: {e}")

if not data:
    st.error("No data loaded.")
    st.stop()

colors = ["#2196F3", "#FF5722", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4"]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Combined comparison chart (all stocks together)
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Combined View")

tab_pct, tab_abs = st.tabs(["% Change (normalized)", "Absolute prices"])

with tab_pct:
    fig_combined = go.Figure()
    for i, (ticker, df) in enumerate(data.items()):
        pct = (df["Close"] / df["Close"].iloc[0] - 1) * 100
        fig_combined.add_trace(go.Scatter(
            x=df.index, y=pct,
            name=ticker,
            line=dict(color=colors[i % len(colors)], width=2),
            hovertemplate=f"<b>{ticker}</b><br>Date: %{{x|%Y-%m-%d}}<br>Change: %{{y:.2f}}%<extra></extra>",
        ))
    fig_combined.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.5)
    fig_combined.update_layout(
        height=400,
        hovermode="x unified",
        yaxis_title="% Change from start",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_combined, use_container_width=True)

with tab_abs:
    n = len(data)
    fig_abs = make_subplots(
        rows=n, cols=1,
        shared_xaxes=True,
        subplot_titles=list(data.keys()),
        vertical_spacing=0.06,
    )
    for i, (ticker, df) in enumerate(data.items()):
        fig_abs.add_trace(go.Scatter(
            x=df.index, y=df["Close"],
            name=ticker,
            line=dict(color=colors[i % len(colors)], width=2),
            showlegend=True,
        ), row=i + 1, col=1)
    fig_abs.update_layout(
        height=max(300, 200 * n),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig_abs.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
    fig_abs.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
    st.plotly_chart(fig_abs, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Correlation heatmap (only if 2+ stocks)
# ══════════════════════════════════════════════════════════════════════════════
if len(data) >= 2:
    st.subheader("Correlation")

    col_corr, col_stats = st.columns([1, 1])

    with col_corr:
        # Align all closing prices on the same dates
        closes = pd.DataFrame({t: df["Close"] for t, df in data.items()}).dropna()
        corr   = closes.corr()

        labels = list(corr.columns)
        z      = corr.values.tolist()
        text   = [[f"{v:.2f}" for v in row] for row in corr.values]

        fig_heatmap = go.Figure(go.Heatmap(
            z=z, x=labels, y=labels, text=text,
            texttemplate="%{text}",
            colorscale="RdYlGn",
            zmin=-1, zmax=1,
            showscale=True,
        ))
        fig_heatmap.update_layout(
            title="Price Correlation",
            height=300,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

    with col_stats:
        st.markdown("**Period Summary**")
        summary_rows = []
        for ticker, df in data.items():
            close = df["Close"]
            pct   = (close.iloc[-1] / close.iloc[0] - 1) * 100
            summary_rows.append({
                "Ticker": ticker,
                "Last":   f"${close.iloc[-1]:.2f}",
                "High":   f"${df['High'].max():.2f}",
                "Low":    f"${df['Low'].min():.2f}",
                "Return": f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%",
            })
        st.dataframe(pd.DataFrame(summary_rows).set_index("Ticker"), use_container_width=True)

        st.markdown("**Daily return correlation**")
        daily_ret  = closes.pct_change().dropna()
        ret_corr   = daily_ret.corr()
        st.dataframe(ret_corr.style.format("{:.2f}"), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Individual detailed charts
# ══════════════════════════════════════════════════════════════════════════════
st.subheader("Individual Charts")

for idx, (ticker, df) in enumerate(data.items()):
    color = colors[idx % len(colors)]
    close = df["Close"]

    last_close  = close.iloc[-1]
    first_close = close.iloc[0]
    pct_change  = (last_close / first_close - 1) * 100
    pct_str     = f"+{pct_change:.1f}%" if pct_change >= 0 else f"{pct_change:.1f}%"
    pct_color   = "green" if pct_change >= 0 else "red"

    with st.expander(
        f"{ticker}  ·  ${last_close:.2f}  ·  {pct_str}  ({period_label})",
        expanded=(idx == 0),
    ):
        rows, row_heights = [1], [0.6]
        if show_volume: rows.append(len(rows) + 1); row_heights.append(0.2)
        if show_macd:   rows.append(len(rows) + 1); row_heights.append(0.2)
        total_rows = len(rows)

        subplot_titles = [ticker]
        if show_volume: subplot_titles.append("Volume")
        if show_macd:   subplot_titles.append("MACD")

        # Row 1 has a secondary Y axis for RSI
        specs = [[{"secondary_y": True}]] + [[{"secondary_y": False}]] * (total_rows - 1)

        fig = make_subplots(
            rows=total_rows, cols=1,
            shared_xaxes=True,
            row_heights=row_heights,
            subplot_titles=subplot_titles,
            vertical_spacing=0.04,
            specs=specs,
        )

        if chart_type == "Candlestick":
            fig.add_trace(go.Candlestick(
                x=df.index,
                open=df["Open"], high=df["High"],
                low=df["Low"],   close=df["Close"],
                name=ticker, showlegend=False,
            ), row=1, col=1, secondary_y=False)
        else:
            fig.add_trace(go.Scatter(
                x=df.index, y=close, name=ticker,
                line=dict(color=color, width=1.5), showlegend=False,
            ), row=1, col=1, secondary_y=False)

        for show, window, ma_color, label in [
            (show_ma20,  20,  "#FFC107", "MA20"),
            (show_ma50,  50,  "#FF5722", "MA50"),
            (show_ma200, 200, "#9C27B0", "MA200"),
        ]:
            if show and len(close) >= window:
                fig.add_trace(go.Scatter(
                    x=df.index, y=close.rolling(window).mean(),
                    name=label, line=dict(color=ma_color, width=1),
                ), row=1, col=1, secondary_y=False)

        if show_ema:
            fig.add_trace(go.Scatter(
                x=df.index, y=close.ewm(span=20, adjust=False).mean(),
                name="EMA20", line=dict(color="#00BCD4", width=1, dash="dot"),
            ), row=1, col=1, secondary_y=False)

        if show_bb:
            upper, mid, lower = compute_bb(close)
            fig.add_trace(go.Scatter(
                x=df.index, y=upper, name="BB Upper",
                line=dict(color="rgba(150,150,150,0.5)", width=1),
            ), row=1, col=1, secondary_y=False)
            fig.add_trace(go.Scatter(
                x=df.index, y=lower, name="BB Lower",
                fill="tonexty", fillcolor="rgba(150,150,150,0.1)",
                line=dict(color="rgba(150,150,150,0.5)", width=1),
            ), row=1, col=1, secondary_y=False)

        # ── RSI on secondary Y axis (right side, 0-100) ────────────────────
        if show_rsi:
            rsi = compute_rsi(close)
            fig.add_trace(go.Scatter(
                x=df.index, y=rsi, name="RSI (14)",
                line=dict(color="#FF9800", width=1.5, dash="dot"),
                opacity=0.8,
            ), row=1, col=1, secondary_y=True)
            # Overbought / oversold reference lines
            fig.add_hline(y=70, line_dash="dash", line_color="red",
                          opacity=0.4, row=1, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green",
                          opacity=0.4, row=1, col=1)
            fig.update_yaxes(
                range=[0, 100],
                title_text="RSI",
                secondary_y=True,
                row=1, col=1,
                showgrid=False,
                tickfont=dict(color="#FF9800"),
                title_font=dict(color="#FF9800"),
            )

        current_row = 2

        if show_volume:
            vol_colors = ["#EF5350" if df["Close"].iloc[i] < df["Open"].iloc[i]
                          else "#26A69A" for i in range(len(df))]
            fig.add_trace(go.Bar(
                x=df.index, y=df["Volume"],
                marker_color=vol_colors, name="Volume", showlegend=False,
            ), row=current_row, col=1)
            current_row += 1

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

        fig.update_layout(
            height=300 + total_rows * 120,
            hovermode="x unified",
            xaxis_rangeslider_visible=False,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)")
        fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.1)",
                         secondary_y=False)

        st.plotly_chart(fig, use_container_width=True)
