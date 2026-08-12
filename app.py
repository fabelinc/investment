import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Earnings Catalyst Scanner", layout="wide")

# ---------------------------------------------------------------------------
# S&P 100 constituents (as of mid-2026). This list drifts over time as index
# membership changes — update periodically if tickers feel stale.
# ---------------------------------------------------------------------------
SP100 = [
    "AAPL","ABBV","ABT","ACN","ADBE","AIG","AMD","AMGN","AMT","AMZN","AVGO",
    "AXP","BA","BAC","BK","BKNG","BLK","BMY","BRK-B","C","CAT","CHTR","CL",
    "CMCSA","COF","COP","COST","CRM","CSCO","CVS","CVX","DE","DHR","DIS",
    "DOW","DUK","EMR","F","FDX","GD","GE","GILD","GM","GOOG","GOOGL","GS",
    "HD","HON","IBM","INTC","INTU","JNJ","JPM","KHC","KO","LIN","LLY","LMT",
    "LOW","MA","MCD","MDLZ","MDT","MET","META","MMM","MO","MRK","MS","MSFT",
    "NEE","NFLX","NKE","NVDA","ORCL","PEP","PFE","PG","PM","PYPL","QCOM",
    "RTX","SBUX","SO","SPG","T","TGT","TMO","TMUS","TXN","UNH","UNP","UPS",
    "USB","V","VZ","WBA","WFC","WMT","XOM",
]

DIST_STYLE = {
    "sell": {"label": "Selling pressure", "color": "#E5484D", "glyph": "▼"},
    "buy": {"label": "Accumulation", "color": "#3DD68C", "glyph": "▲"},
    "neutral": {"label": "Neutral", "color": "#9AA4B2", "glyph": "—"},
}


# ---------------------------------------------------------------------------
# Data fetching (cached so repeat filtering doesn't re-hit the network)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_earnings_window(tickers, days_forward=14, days_back=7):
    """Return {ticker: (earnings_date, status, days_away)} for tickers with
    earnings in the (-days_back, +days_forward) window."""
    today = datetime.now().date()
    window = {}
    for t in tickers:
        try:
            edf = yf.Ticker(t).get_earnings_dates(limit=8)
            if edf is None or edf.empty:
                continue
            for dt in edf.index:
                d = dt.date()
                delta = (d - today).days
                if -days_back <= delta <= days_forward:
                    status = "upcoming" if delta >= 0 else "recent"
                    window[t] = (d.isoformat(), status, delta)
                    break
        except Exception:
            continue
    return window


@st.cache_data(ttl=1800, show_spinner=False)
def get_price_volume_signal(ticker):
    """Compare trailing 5 sessions vs prior 5 sessions to flag distribution
    (price down + volume up) vs accumulation (price up + volume up)."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
        if len(hist) < 10:
            return "neutral", 0.0, 0.0
        last5 = hist.tail(5)
        prior5 = hist.iloc[-10:-5]
        price_chg = (last5["Close"].mean() - prior5["Close"].mean()) / prior5["Close"].mean() * 100
        vol_chg = (last5["Volume"].mean() - prior5["Volume"].mean()) / prior5["Volume"].mean() * 100
        if price_chg < -0.5 and vol_chg > 15:
            signal = "sell"
        elif price_chg > 0.5 and vol_chg > 15:
            signal = "buy"
        else:
            signal = "neutral"
        return signal, round(price_chg, 1), round(vol_chg, 1)
    except Exception:
        return "neutral", 0.0, 0.0


@st.cache_data(ttl=1800, show_spinner=False)
def get_analyst_signal(ticker):
    """Recent rating changes (7d) + current price target vs price."""
    upgrades = downgrades = 0
    pt_note = "No recent price target data"
    try:
        tk = yf.Ticker(ticker)
        ud = tk.upgrades_downgrades
        if ud is not None and not ud.empty:
            cutoff = datetime.now() - timedelta(days=7)
            recent = ud[ud.index >= cutoff] if ud.index.dtype.kind == "M" else ud
            action_col = "Action" if "Action" in recent.columns else None
            if action_col:
                upgrades = (recent[action_col].str.lower() == "up").sum()
                downgrades = (recent[action_col].str.lower() == "down").sum()
        info = tk.info
        target = info.get("targetMeanPrice")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if target and price:
            pct = (target - price) / price * 100
            pt_note = f"Mean target ${target:.2f} vs price ${price:.2f} ({pct:+.1f}%)"
    except Exception:
        pass
    return upgrades, downgrades, pt_note


@st.cache_data(ttl=1800, show_spinner=False)
def get_options_signal(ticker):
    """Rough IV level + put/call volume ratio from the nearest expiry."""
    try:
        tk = yf.Ticker(ticker)
        expirations = tk.options
        if not expirations:
            return "n/a", None, "no options data"
        chain = tk.option_chain(expirations[0])
        calls, puts = chain.calls, chain.puts
        last_price = tk.info.get("currentPrice") or tk.info.get("regularMarketPrice")
        if last_price:
            atm_calls = calls[(calls["strike"] >= last_price * 0.95) & (calls["strike"] <= last_price * 1.05)]
            iv = atm_calls["impliedVolatility"].mean() if not atm_calls.empty else calls["impliedVolatility"].mean()
        else:
            iv = calls["impliedVolatility"].mean()
        iv_level = "elevated" if iv > 0.5 else "moderate" if iv > 0.3 else "low"
        call_vol = calls["volume"].fillna(0).sum()
        put_vol = puts["volume"].fillna(0).sum()
        ratio = round(put_vol / call_vol, 2) if call_vol else None
        read = "bearish skew" if ratio and ratio > 1.1 else "bullish skew" if ratio and ratio < 0.8 else "balanced"
        return iv_level, ratio, read
    except Exception:
        return "n/a", None, "no options data"


@st.cache_data(ttl=1800, show_spinner=False)
def get_recent_news(ticker, days=7):
    """Raw headlines from the trailing N days — not summarized. Paste these
    to Claude if you want a qualitative read."""
    items = []
    try:
        news = yf.Ticker(ticker).news or []
        cutoff = datetime.now() - timedelta(days=days)
        for n in news:
            content = n.get("content", n)
            ts = content.get("pubDate") or content.get("providerPublishTime")
            title = content.get("title")
            if not title:
                continue
            try:
                pub_dt = pd.to_datetime(ts)
                if pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.tz_localize(None)
            except Exception:
                pub_dt = datetime.now()
            if pub_dt >= cutoff:
                items.append((pub_dt, title))
        items.sort(key=lambda x: x[0], reverse=True)
    except Exception:
        pass
    return [title for _, title in items[:6]]


@st.cache_data(ttl=1800, show_spinner=False)
def run_full_scan(tickers):
    window = get_earnings_window(tuple(tickers))
    results = []
    for t, (edate, status, days_away) in window.items():
        signal, price_chg, vol_chg = get_price_volume_signal(t)
        up, down, pt_note = get_analyst_signal(t)
        iv, pc_ratio, pc_read = get_options_signal(t)
        headlines = get_recent_news(t)
        try:
            name = yf.Ticker(t).info.get("shortName", t)
        except Exception:
            name = t
        results.append(dict(
            ticker=t, name=name, earnings_date=edate, status=status, days_away=days_away,
            distribution=signal, price_5d=price_chg, volume_5d=vol_chg,
            upgrades=up, downgrades=down, pt_note=pt_note,
            iv=iv, put_call=pc_ratio, put_call_read=pc_read, headlines=headlines,
        ))
    return results


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.markdown(
    "<div style='font-size:12px;font-weight:700;letter-spacing:2px;color:#5B8DEF;'>"
    "EARNINGS CATALYST SCANNER</div>",
    unsafe_allow_html=True,
)
st.title("S&P 100 · Pre/Post Earnings")

with st.sidebar:
    st.subheader("Scan")
    n_tickers = st.slider("How many S&P 100 tickers to check", 10, len(SP100), 30,
                           help="Checking earnings dates for more tickers takes longer.")
    run_clicked = st.button("Run scan", type="primary", use_container_width=True)
    st.caption("First scan takes a minute or two — results are cached for 30 min.")

if "results" not in st.session_state:
    st.session_state.results = None
    st.session_state.scan_time = None

if run_clicked:
    with st.spinner(f"Scanning {n_tickers} tickers for earnings, price/volume, analysts, options, news..."):
        st.session_state.results = run_full_scan(SP100[:n_tickers])
        st.session_state.scan_time = datetime.now().strftime("%b %d, %I:%M %p")

if st.session_state.results is None:
    st.info("Set your scan size in the sidebar and click **Run scan** to pull live data.")
    st.stop()

st.caption(f"Last scanned {st.session_state.scan_time} · {len(st.session_state.results)} tickers matched the earnings window")

filter_choice = st.radio(
    "Filter by signal", ["All", "Selling pressure", "Accumulation", "Neutral"],
    horizontal=True, label_visibility="collapsed",
)
filter_map = {"All": None, "Selling pressure": "sell", "Accumulation": "buy", "Neutral": "neutral"}
active_filter = filter_map[filter_choice]

filtered = [s for s in st.session_state.results if active_filter is None or s["distribution"] == active_filter]
upcoming = sorted([s for s in filtered if s["status"] == "upcoming"], key=lambda s: s["days_away"])
recent = sorted([s for s in filtered if s["status"] == "recent"], key=lambda s: s["days_away"], reverse=True)


def render_card(s):
    style = DIST_STYLE[s["distribution"]]
    badge_text = f"In {s['days_away']}d" if s["status"] == "upcoming" else f"{abs(s['days_away'])}d ago"
    badge_color = "#F2B84B" if s["status"] == "upcoming" else "#5B8DEF"

    with st.container(border=True):
        top = st.columns([3, 3, 2])
        with top[0]:
            st.markdown(
                f"**{s['ticker']}** &nbsp; "
                f"<span style='font-size:11px;font-weight:600;padding:2px 8px;"
                f"border-radius:20px;background:{badge_color}22;color:{badge_color};'>{badge_text}</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"{s['name']} · reports {s['earnings_date']}")
        with top[1]:
            st.markdown(
                f"<span style='color:{style['color']};font-size:16px;'>{style['glyph']}</span> "
                f"<span style='color:{style['color']};font-weight:600;'>{style['label']}</span>"
                f"<br><span style='color:#7A8494;font-size:12px;'>"
                f"price {'+' if s['price_5d']>0 else ''}{s['price_5d']}% · "
                f"vol {'+' if s['volume_5d']>0 else ''}{s['volume_5d']}% (5d)</span>",
                unsafe_allow_html=True,
            )

        with st.expander("Details"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**ANALYSTS**")
                st.write(f"{s['upgrades']} upgrade(s), {s['downgrades']} downgrade(s) (7d)\n\n{s['pt_note']}")
            with col2:
                st.markdown("**OPTIONS**")
                pc = s["put_call"] if s["put_call"] is not None else "n/a"
                st.write(f"IV: {s['iv'].capitalize() if s['iv'] != 'n/a' else 'n/a'}\n\nPut/Call: {pc} ({s['put_call_read']})")
            st.markdown("**RECENT HEADLINES (7D)**")
            if s["headlines"]:
                for h in s["headlines"]:
                    st.write(f"- {h}")
                st.caption("Raw headlines — paste these to Claude for a qualitative catalyst read.")
            else:
                st.write("No recent headlines found.")


if upcoming:
    st.markdown(
        "<div style='font-size:12px;font-weight:700;letter-spacing:1.5px;color:#F2B84B;"
        "margin-top:20px;'>UPCOMING · NEXT 14 DAYS</div>", unsafe_allow_html=True,
    )
    for s in upcoming:
        render_card(s)

if recent:
    st.markdown(
        "<div style='font-size:12px;font-weight:700;letter-spacing:1.5px;color:#5B8DEF;"
        "margin-top:24px;'>RECENTLY REPORTED · LAST 7 DAYS</div>", unsafe_allow_html=True,
    )
    for s in recent:
        render_card(s)

if not filtered:
    st.info("No stocks match this filter right now.")

st.divider()
st.caption(
    "Research tool only — not trading advice. Distribution flag = price down + volume up "
    "over the trailing 5 sessions vs the prior 5, a rough proxy for selling pressure into a "
    "print. Options/IV thresholds are simple heuristics, not modeled probabilities."
)
