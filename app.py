import re
import time
from datetime import datetime, timedelta

import feedparser
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Earnings Catalyst Scanner", layout="wide")

# ---------------------------------------------------------------------------
# Curated universe: top tech (50), healthcare (25), financials (25).
# Fixed list rather than a live index pull — update periodically if names
# feel stale or you want different sector weights.
# ---------------------------------------------------------------------------
TECH = [
    "AAPL","MSFT","GOOGL","GOOG","AMZN","META","NVDA","AVGO","ORCL","CRM",
    "ADBE","CSCO","ACN","AMD","INTC","IBM","QCOM","TXN","INTU","NOW",
    "UBER","PANW","ADI","LRCX","KLAC","SNPS","CDNS","MU","ANET","APH",
    "FTNT","CRWD","ADSK","MSI","ROP","TEL","HPQ","DELL","WDAY","TEAM",
    "DDOG","ZS","MRVL","ON","GLW","NXPI","SWKS","JNPR","HPE","NTAP",
]
HEALTH = [
    "UNH","JNJ","LLY","ABBV","MRK","TMO","ABT","PFE","DHR","BMY",
    "AMGN","ELV","CVS","MDT","ISRG","GILD","VRTX","REGN","CI","ZTS",
    "BSX","HCA","SYK","BDX","HUM",
]
FINANCE = [
    "JPM","BAC","WFC","MS","GS","C","AXP","BLK","SCHW","SPGI",
    "CB","PGR","MMC","ICE","CME","USB","PNC","TFC","AON","MET",
    "AIG","TRV","BK","COF","AFL",
]
SP100 = TECH + HEALTH + FINANCE
SECTOR_MAP = {t: "Tech" for t in TECH}
SECTOR_MAP.update({t: "Health" for t in HEALTH})
SECTOR_MAP.update({t: "Finance" for t in FINANCE})

# Company name used for matching general (non-ticker-specific) RSS feeds.
COMPANY_MATCH = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Google", "GOOG": "Google",
    "AMZN": "Amazon", "META": "Meta", "NVDA": "Nvidia", "AVGO": "Broadcom",
    "ORCL": "Oracle", "CRM": "Salesforce", "ADBE": "Adobe", "CSCO": "Cisco",
    "ACN": "Accenture", "AMD": "AMD", "INTC": "Intel", "IBM": "IBM",
    "QCOM": "Qualcomm", "TXN": "Texas Instruments", "INTU": "Intuit",
    "NOW": "ServiceNow", "UBER": "Uber", "PANW": "Palo Alto Networks",
    "ADI": "Analog Devices", "LRCX": "Lam Research", "KLAC": "KLA Corp",
    "SNPS": "Synopsys", "CDNS": "Cadence", "MU": "Micron",
    "ANET": "Arista Networks", "APH": "Amphenol", "FTNT": "Fortinet",
    "CRWD": "CrowdStrike", "ADSK": "Autodesk", "MSI": "Motorola Solutions",
    "ROP": "Roper Technologies", "TEL": "TE Connectivity", "HPQ": "HP Inc",
    "DELL": "Dell", "WDAY": "Workday", "TEAM": "Atlassian", "DDOG": "Datadog",
    "ZS": "Zscaler", "MRVL": "Marvell", "ON": "ON Semiconductor",
    "GLW": "Corning", "NXPI": "NXP Semiconductors", "SWKS": "Skyworks",
    "JNPR": "Juniper Networks", "HPE": "Hewlett Packard Enterprise",
    "NTAP": "NetApp",
    "UNH": "UnitedHealth", "JNJ": "Johnson & Johnson", "LLY": "Eli Lilly",
    "ABBV": "AbbVie", "MRK": "Merck", "TMO": "Thermo Fisher", "ABT": "Abbott",
    "PFE": "Pfizer", "DHR": "Danaher", "BMY": "Bristol-Myers Squibb",
    "AMGN": "Amgen", "ELV": "Elevance Health", "CVS": "CVS Health",
    "MDT": "Medtronic", "ISRG": "Intuitive Surgical", "GILD": "Gilead",
    "VRTX": "Vertex Pharmaceuticals", "REGN": "Regeneron", "CI": "Cigna",
    "ZTS": "Zoetis", "BSX": "Boston Scientific", "HCA": "HCA Healthcare",
    "SYK": "Stryker", "BDX": "Becton Dickinson", "HUM": "Humana",
    "JPM": "JPMorgan", "BAC": "Bank of America", "WFC": "Wells Fargo",
    "MS": "Morgan Stanley", "GS": "Goldman Sachs", "C": "Citigroup",
    "AXP": "American Express", "BLK": "BlackRock", "SCHW": "Charles Schwab",
    "SPGI": "S&P Global", "CB": "Chubb", "PGR": "Progressive",
    "MMC": "Marsh McLennan", "ICE": "Intercontinental Exchange",
    "CME": "CME Group", "USB": "U.S. Bancorp", "PNC": "PNC Financial",
    "TFC": "Truist", "AON": "Aon", "MET": "MetLife", "AIG": "AIG",
    "TRV": "Travelers", "BK": "BNY Mellon", "COF": "Capital One",
    "AFL": "Aflac",
}

DIST_STYLE = {
    "sell": {"label": "Selling pressure", "color": "#E5484D", "glyph": "▼"},
    "buy": {"label": "Accumulation", "color": "#3DD68C", "glyph": "▲"},
    "neutral": {"label": "Neutral", "color": "#9AA4B2", "glyph": "—"},
}

# CNBC's markets RSS id — CNBC publishes many feeds under this same base URL
# with different `id` params (see cnbc.com/rss for the full list). This id
# targets "Markets." If it comes back empty, check that page for the current id.
CNBC_MARKETS_RSS = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"
MARKETWATCH_RSS = "https://feeds.marketwatch.com/marketwatch/realtimeheadlines/"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EarningsScanner/1.0)"}


# ---------------------------------------------------------------------------
# Stage 1 — cheap earnings-date check across the full ticker list
# ---------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_earnings_window(tickers, days_forward=14, days_back=7):
    """Return (window, debug_log). window is {ticker: (date, status, days_away)}
    for tickers with earnings in the (-days_back, +days_forward) window."""
    today = datetime.now().date()
    window = {}
    debug_log = []
    for t in tickers:
        try:
            edf = yf.Ticker(t).get_earnings_dates(limit=8)
            if edf is None or edf.empty:
                debug_log.append((t, "no earnings data returned", ""))
                continue
            nearest, matched = None, False
            for dt in edf.index:
                d = dt.date()
                delta = (d - today).days
                if nearest is None:
                    nearest = d
                if -days_back <= delta <= days_forward:
                    status = "upcoming" if delta >= 0 else "recent"
                    window[t] = (d.isoformat(), status, delta)
                    debug_log.append((t, "matched", d.isoformat()))
                    matched = True
                    break
            if not matched:
                debug_log.append((t, "outside window", nearest.isoformat() if nearest else "none found"))
        except Exception as e:
            debug_log.append((t, f"ERROR: {type(e).__name__}: {e}", ""))
    return window, debug_log


# ---------------------------------------------------------------------------
# Stage 2 — heavy per-ticker data, only called for shortlisted tickers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=1800, show_spinner=False)
def get_price_volume_signal(ticker):
    """Trailing 5 sessions vs prior 5: price down + volume up = distribution."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
        if len(hist) < 10:
            return "neutral", 0.0, 0.0
        last5, prior5 = hist.tail(5), hist.iloc[-10:-5]
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
    upgrades = downgrades = 0
    pt_note = "No recent price target data"
    try:
        tk = yf.Ticker(ticker)
        ud = tk.upgrades_downgrades
        if ud is not None and not ud.empty:
            cutoff = datetime.now() - timedelta(days=7)
            recent = ud[ud.index >= cutoff] if ud.index.dtype.kind == "M" else ud
            if "Action" in recent.columns:
                upgrades = (recent["Action"].str.lower() == "up").sum()
                downgrades = (recent["Action"].str.lower() == "down").sum()
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
    try:
        tk = yf.Ticker(ticker)
        expirations = tk.options
        if not expirations:
            return "n/a", None, "no options data"
        chain = tk.option_chain(expirations[0])
        calls, puts = chain.calls, chain.puts
        last_price = tk.info.get("currentPrice") or tk.info.get("regularMarketPrice")
        if last_price:
            atm = calls[(calls["strike"] >= last_price * 0.95) & (calls["strike"] <= last_price * 1.05)]
            iv = atm["impliedVolatility"].mean() if not atm.empty else calls["impliedVolatility"].mean()
        else:
            iv = calls["impliedVolatility"].mean()
        iv_level = "elevated" if iv > 0.5 else "moderate" if iv > 0.3 else "low"
        call_vol, put_vol = calls["volume"].fillna(0).sum(), puts["volume"].fillna(0).sum()
        ratio = round(put_vol / call_vol, 2) if call_vol else None
        read = "bearish skew" if ratio and ratio > 1.1 else "bullish skew" if ratio and ratio < 0.8 else "balanced"
        return iv_level, ratio, read
    except Exception:
        return "n/a", None, "no options data"


# ---------------------------------------------------------------------------
# Multi-source news (Stage 2, shortlisted tickers only)
# ---------------------------------------------------------------------------
def _clean_title(title):
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _fetch_yahoo_rss(ticker, max_items=3):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    out = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries[:max_items]:
            out.append({"source": "Yahoo", "title": e.title, "published": e.get("published", "")})
    except Exception:
        pass
    return out


def _fetch_filtered_rss(url, ticker, company, source_label, max_items=5):
    """Fetch a general market RSS feed and keep only entries mentioning the
    ticker (word-boundary match) or company name."""
    out = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        feed = feedparser.parse(resp.content)
        ticker_re = re.compile(rf"\b{re.escape(ticker)}\b")
        company_re = re.compile(re.escape(company), re.IGNORECASE)
        for e in feed.entries:
            title = e.get("title", "")
            if ticker_re.search(title) or company_re.search(title):
                out.append({"source": source_label, "title": title, "published": e.get("published", "")})
            if len(out) >= max_items:
                break
    except Exception:
        pass
    return out


def _fetch_yfinance_news(ticker, days=7, max_items=6):
    out = []
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
                out.append({"source": "Yahoo(yf)", "title": title, "published": str(pub_dt)})
        out.sort(key=lambda x: x["published"], reverse=True)
    except Exception:
        pass
    return out[:max_items]


@st.cache_data(ttl=600, show_spinner=False)
def fetch_all_news(ticker, max_total=8):
    """Combine Yahoo RSS, CNBC, MarketWatch, and yfinance news; dedupe by
    normalized title; cap total. Cached 10 min."""
    company = COMPANY_MATCH.get(ticker, ticker)
    combined = (
        _fetch_yahoo_rss(ticker)
        + _fetch_filtered_rss(CNBC_MARKETS_RSS, ticker, company, "CNBC")
        + _fetch_filtered_rss(MARKETWATCH_RSS, ticker, company, "MarketWatch")
        + _fetch_yfinance_news(ticker)
    )
    seen, deduped = set(), []
    for item in combined:
        key = _clean_title(item["title"])[:60]
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:max_total]


# ---------------------------------------------------------------------------
# Claude interpretation (Stage 2, shortlisted tickers only)
# ---------------------------------------------------------------------------
def interpret_with_claude(ticker, sector, headlines, api_key):
    if not api_key or not headlines:
        return None
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        headline_text = "\n".join(f"[{h['source']}] {h['title']}" for h in headlines)
        prompt = (
            f"Recent headlines for {ticker} ({sector} sector), last 7 days:\n\n{headline_text}\n\n"
            "In 2-3 sentences, summarize what's actually going on and name the type of catalyst "
            "if there is one (earnings reaction, contract/deal win, product launch, guidance change, "
            "sector read-through, analyst action, or \"no clear catalyst\" if this is just routine "
            "noise). Be concrete, skip filler."
        )
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        return f"(Claude interpretation failed: {type(e).__name__}: {e})"


# ---------------------------------------------------------------------------
# Two-stage scan orchestration
# ---------------------------------------------------------------------------
def run_two_stage_scan(tickers, use_claude, api_key, progress_cb=None):
    window, debug_log = get_earnings_window(tuple(tickers))
    shortlist = list(window.items())

    results = []
    claude_calls = 0
    for i, (t, (edate, status, days_away)) in enumerate(shortlist):
        if progress_cb:
            progress_cb(i, len(shortlist), t)

        signal, price_chg, vol_chg = get_price_volume_signal(t)
        up, down, pt_note = get_analyst_signal(t)
        iv, pc_ratio, pc_read = get_options_signal(t)
        headlines = fetch_all_news(t)

        interpretation = None
        if use_claude and headlines:
            interpretation = interpret_with_claude(t, SECTOR_MAP.get(t, "Other"), headlines, api_key)
            claude_calls += 1

        try:
            name = yf.Ticker(t).info.get("shortName", t)
        except Exception:
            name = t

        results.append(dict(
            ticker=t, name=name, sector=SECTOR_MAP.get(t, "Other"),
            earnings_date=edate, status=status, days_away=days_away,
            distribution=signal, price_5d=price_chg, volume_5d=vol_chg,
            upgrades=up, downgrades=down, pt_note=pt_note,
            iv=iv, put_call=pc_ratio, put_call_read=pc_read,
            headlines=headlines, interpretation=interpretation,
        ))
        time.sleep(0.3)  # gentle pacing to avoid rate limits on heavier calls

    return results, debug_log, claude_calls


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.markdown(
    "<div style='font-size:12px;font-weight:700;letter-spacing:2px;color:#5B8DEF;'>"
    "EARNINGS CATALYST SCANNER</div>",
    unsafe_allow_html=True,
)
st.title("Tech · Health · Finance — Pre/Post Earnings")

with st.sidebar:
    st.subheader("Scan")
    st.caption(f"Universe: {len(TECH)} tech · {len(HEALTH)} health · {len(FINANCE)} finance ({len(SP100)} total)")
    n_tickers = st.slider("How many tickers to check", 10, len(SP100), 40,
                           help="Stage 1 checks earnings dates for all of these (cheap). "
                                "Stage 2 pulls detailed data only for the shortlist that matches.")

    st.divider()
    st.subheader("Claude news interpretation")
    api_key_input = st.text_input("Anthropic API key", type="password",
                                   help="Only used for this session, never stored to disk.")
    use_claude = st.checkbox("Interpret news with Claude (Haiku)", value=bool(api_key_input),
                              disabled=not api_key_input)
    if use_claude:
        st.caption("Runs one small Claude call per shortlisted stock — a few cents per scan.")

    st.divider()
    run_clicked = st.button("Run scan", type="primary", use_container_width=True)
    st.caption("Stage 1 (earnings check) covers all selected tickers. Stage 2 (price/volume, "
               "analysts, options, news) only runs on the shortlist — much fewer API calls.")

if "results" not in st.session_state:
    st.session_state.results = None
    st.session_state.debug_log = None
    st.session_state.scan_time = None
    st.session_state.claude_calls = 0

if run_clicked:
    status_area = st.empty()
    progress_bar = st.progress(0)

    status_area.info(f"Stage 1: checking earnings dates for {n_tickers} tickers...")
    window, debug_log = get_earnings_window(tuple(SP100[:n_tickers]))
    shortlist_size = len(window)
    status_area.info(f"Stage 1 done — {shortlist_size} of {n_tickers} tickers have earnings in the window. "
                      f"Stage 2: pulling detailed data for those...")

    def progress_cb(i, total, ticker):
        pct = int(((i + 1) / total) * 100) if total else 100
        progress_bar.progress(pct, text=f"Stage 2: {ticker} ({i + 1}/{total})")

    results, debug_log, claude_calls = run_two_stage_scan(
        SP100[:n_tickers], use_claude, api_key_input, progress_cb=progress_cb
    )
    progress_bar.empty()
    status_area.empty()

    st.session_state.results = results
    st.session_state.debug_log = debug_log
    st.session_state.scan_time = datetime.now().strftime("%b %d, %I:%M %p")
    st.session_state.claude_calls = claude_calls

if st.session_state.results is None:
    st.info("Set your scan size in the sidebar and click **Run scan** to pull live data.")
    st.stop()

extra = f" · {st.session_state.claude_calls} Claude interpretation calls" if st.session_state.claude_calls else ""
st.caption(f"Last scanned {st.session_state.scan_time} · {len(st.session_state.results)} tickers matched the earnings window{extra}")

with st.expander(f"🔍 Debug log ({len(st.session_state.debug_log)} tickers checked in Stage 1) — open if results look wrong"):
    error_count = sum(1 for _, status, _ in st.session_state.debug_log if status.startswith("ERROR"))
    if error_count:
        st.warning(f"{error_count} of {len(st.session_state.debug_log)} tickers errored out in Stage 1 — "
                    f"likely yfinance rate-limiting. Try a smaller scan size or wait a few minutes.")
    debug_df = pd.DataFrame(st.session_state.debug_log, columns=["Ticker", "Status", "Nearest earnings date found"])
    st.dataframe(debug_df, use_container_width=True, hide_index=True)

filter_choice = st.radio("Filter by signal", ["All", "Selling pressure", "Accumulation", "Neutral"],
                          horizontal=True, label_visibility="collapsed")
filter_map = {"All": None, "Selling pressure": "sell", "Accumulation": "buy", "Neutral": "neutral"}
active_filter = filter_map[filter_choice]

sector_choice = st.radio("Filter by sector", ["All sectors", "Tech", "Health", "Finance"],
                          horizontal=True, label_visibility="collapsed")
active_sector = None if sector_choice == "All sectors" else sector_choice

filtered = [
    s for s in st.session_state.results
    if (active_filter is None or s["distribution"] == active_filter)
    and (active_sector is None or s["sector"] == active_sector)
]
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
            st.caption(f"{s['name']} · {s['sector']} · reports {s['earnings_date']}")
        with top[1]:
            st.markdown(
                f"<span style='color:{style['color']};font-size:16px;'>{style['glyph']}</span> "
                f"<span style='color:{style['color']};font-weight:600;'>{style['label']}</span>"
                f"<br><span style='color:#7A8494;font-size:12px;'>"
                f"price {'+' if s['price_5d']>0 else ''}{s['price_5d']}% · "
                f"vol {'+' if s['volume_5d']>0 else ''}{s['volume_5d']}% (5d)</span>",
                unsafe_allow_html=True,
            )

        if s["interpretation"]:
            st.markdown(
                f"<div style='margin-top:8px;padding:10px 12px;background:#1E2530;"
                f"border-radius:6px;font-size:13px;color:#C9CFDA;'>🧠 {s['interpretation']}</div>",
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
            st.markdown("**HEADLINES (7D, all sources)**")
            if s["headlines"]:
                for h in s["headlines"]:
                    st.write(f"- [{h['source']}] {h['title']}")
            else:
                st.write("No recent headlines found.")


if upcoming:
    st.markdown("<div style='font-size:12px;font-weight:700;letter-spacing:1.5px;color:#F2B84B;"
                "margin-top:20px;'>UPCOMING · NEXT 14 DAYS</div>", unsafe_allow_html=True)
    for s in upcoming:
        render_card(s)

if recent:
    st.markdown("<div style='font-size:12px;font-weight:700;letter-spacing:1.5px;color:#5B8DEF;"
                "margin-top:24px;'>RECENTLY REPORTED · LAST 7 DAYS</div>", unsafe_allow_html=True)
    for s in recent:
        render_card(s)

if not filtered:
    st.info("No stocks match this filter right now.")

st.divider()
st.caption(
    "Research tool only — not trading advice. Distribution flag = price down + volume up over "
    "the trailing 5 sessions vs the prior 5. Options/IV thresholds are simple heuristics. "
    "News is aggregated from Yahoo, CNBC, and MarketWatch RSS feeds and may occasionally include "
    "false matches from generic name/ticker matching."
)
