import streamlit as st
import requests
import yfinance as yf
import anthropic
import json
import pandas as pd
from datetime import datetime, timedelta

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Tech Signal Scanner", page_icon="📡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'JetBrains Mono',monospace}
.stApp{background:#03060d;color:#c8dff0}
.block-container{padding:1.2rem 1.8rem}
[data-testid="stSidebar"]{background:#080f1a;border-right:1px solid #0e1e35}
[data-testid="stSidebar"] label{color:#2a4560!important;font-size:11px;letter-spacing:1px}
[data-testid="metric-container"]{background:#080f1a;border:1px solid #0e1e35;border-radius:10px;padding:10px 14px}
[data-testid="stMetricValue"]{color:#c8dff0!important;font-family:'JetBrains Mono',monospace!important}
[data-testid="stMetricLabel"]{color:#2a4560!important;font-size:10px!important;letter-spacing:2px;text-transform:uppercase}
.stButton>button{background:#0e1e35;color:#38bdf8;border:1px solid #38bdf844;border-radius:8px;font-family:'JetBrains Mono',monospace;font-weight:700;letter-spacing:1px;width:100%}
.stButton>button:hover{background:#38bdf818;border-color:#38bdf8}
.stTabs [data-baseweb="tab-list"]{background:#080f1a;border-bottom:1px solid #0e1e35}
.stTabs [data-baseweb="tab"]{color:#2a4560;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px}
.stTabs [aria-selected="true"]{color:#38bdf8!important;border-bottom:2px solid #38bdf8!important}
.streamlit-expanderHeader{background:#080f1a!important;color:#2a4560!important;border:1px solid #0e1e35!important;border-radius:8px!important}
hr{border-color:#0e1e35}
</style>
""", unsafe_allow_html=True)

# ── Universe definition ──────────────────────────────────────────────────────

# TIER 1 — Fixed anchors, always scanned, safest (mega cap, highest liquidity)
TIER1_FIXED = [
    "AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","ORCL","NFLX","ADBE",
]

# TIER 2 — Established tech, S&P 500 members, strong fundamentals
TIER2_FIXED = [
    # AI & Chips
    "AMD","AVGO","QCOM","ARM","TSM","MU","AMAT","LRCX","KLAC","MRVL","SMCI",
    # Cloud & SaaS
    "CRM","NOW","SNOW","DDOG","NET","MDB","GTLB","WDAY","VEEV",
    # Cybersecurity
    "PANW","CRWD","FTNT","ZS","OKTA","S",
    # Big Tech adjacent
    "UBER","SHOP","PLTR","APP","RBLX","ABNB",
    # Infra & Hardware
    "ANET","CSCO","DELL","HPE","JNPR",
    # Semiconductors extended
    "INTC","TXN","ADI","MCHP","ON",
]

# TIER 3 — Higher growth, higher risk, smaller cap but promising
TIER3_FIXED = [
    "AI","BBAI","SOUN","IONQ","RXRX","GFAI",   # AI pure plays
    "WOLF","LAZR","OUST",                         # emerging tech
    "HPQ","WDC","STX","NTAP",                    # storage / hardware
    "TENB","QLYS","SAIL","SCWX",                 # cyber extended
    "CFLT","ESTC","DOMO","JAMF",                 # SaaS extended
]

# Theme map — for signal categorisation
UNIVERSE = {
    "AI_CHIPS":    {"label":"AI & Semiconductors","icon":"🤖","color":"#a78bfa",
                    "leaders":["NVDA","AMD","MSFT"],
                    "tier1":["NVDA","MSFT","GOOGL","AMZN","META"],
                    "tier2":["AMD","AVGO","QCOM","ARM","TSM","MU","AMAT","SMCI","MRVL"],
                    "tier3":["AI","BBAI","SOUN","IONQ","LRCX","KLAC"]},
    "CLOUD_SAAS":  {"label":"Cloud & SaaS",       "icon":"☁️","color":"#38bdf8",
                    "leaders":["MSFT","AMZN","GOOGL"],
                    "tier1":["MSFT","AMZN","GOOGL","ORCL","ADBE"],
                    "tier2":["CRM","NOW","SNOW","DDOG","NET","WDAY","VEEV","GTLB"],
                    "tier3":["MDB","CFLT","ESTC","DOMO","JAMF"]},
    "CYBER":       {"label":"Cybersecurity",       "icon":"🔒","color":"#e879f9",
                    "leaders":["PANW","CRWD"],
                    "tier1":["PANW","MSFT"],
                    "tier2":["CRWD","ZS","FTNT","OKTA","S"],
                    "tier3":["TENB","QLYS","SAIL","SCWX"]},
    "BIG_TECH":    {"label":"Big Tech",            "icon":"💻","color":"#4ade80",
                    "leaders":["AAPL","MSFT","GOOGL"],
                    "tier1":["AAPL","MSFT","GOOGL","AMZN","META","NFLX","TSLA"],
                    "tier2":["UBER","SHOP","PLTR","APP","RBLX","ABNB","ORCL"],
                    "tier3":["DELL","HPQ","HPE","INTC","CSCO","ANET","JNPR"]},
    "SEMIS":       {"label":"Semiconductors",      "icon":"⚡","color":"#fbbf24",
                    "leaders":["NVDA","TSM","AVGO"],
                    "tier1":["NVDA","TSM","AVGO","QCOM","ARM"],
                    "tier2":["MU","AMAT","LRCX","KLAC","TXN","ADI","MCHP","ON","MRVL"],
                    "tier3":["SMCI","WDC","STX","NTAP","WOLF"]},
}

# Combined fixed universe (deduped, ordered by tier)
_seen = set()
ALL_TICKERS_FIXED = []
for t in TIER1_FIXED + TIER2_FIXED + TIER3_FIXED:
    if t not in _seen:
        _seen.add(t)
        ALL_TICKERS_FIXED.append(t)

RISK = {
    1: {"stop":3,  "target":5,  "size":"$500",  "label":"🟢 TIER 1 · ANCHOR"},
    2: {"stop":4,  "target":8,  "size":"$375",  "label":"🟡 TIER 2 · GROWTH"},
    3: {"stop":5,  "target":12, "size":"$250",  "label":"🔴 TIER 3 · DYNAMIC"},
    4: {"stop":6,  "target":15, "size":"$150",  "label":"⚡ MOMENTUM · SPECULATIVE"},
}

def get_tier(ticker):
    if ticker in TIER1_FIXED: return 1
    if ticker in TIER2_FIXED: return 2
    if ticker in TIER3_FIXED: return 3
    return 4  # momentum / dynamic addition

def get_theme(ticker):
    for k, v in UNIVERSE.items():
        if ticker in v["tier1"]+v["tier2"]+v["tier3"]:
            return k, v
    return "BIG_TECH", UNIVERSE["BIG_TECH"]

# ── Dynamic universe builder ───────────────────────────────────────────────────
@st.cache_data(ttl=3600)  # refresh every hour
def build_dynamic_universe():
    """
    Fetches momentum movers to expand beyond fixed list.
    Returns dict with momentum picks and their rationale.
    """
    momentum = []

    # Candidate pool — broader Nasdaq tech names worth monitoring
    candidates = [
        # Recent AI/tech momentum names
        "PLTR","APP","RDDT","HOOD","COIN","MSTR","LUNR","RKLB",
        "ACHR","JOBY","LILM","BLDE","EVTL",
        # Semis & hardware candidates
        "ONTO","FORM","AMKR","COHU","ACLS","CAMT","AMBA",
        # SaaS candidates
        "BILL","FRSH","PCTY","PAYC","HUBS","ZI","BOX","DBX",
        # Cyber candidates
        "CYBR","VRNS","QLYS","SAIL","DEEP","RPD",
        # Storage / data
        "PSTG","NCNO","CLBT",
    ]
    # Remove any already in fixed universe
    candidates = [c for c in candidates if c not in set(ALL_TICKERS_FIXED)]

    try:
        data = yf.download(
            " ".join(candidates), period="30d",
            interval="1d", progress=False, auto_adjust=True
        )
        closes  = data["Close"]
        volumes = data["Volume"]

        for t in candidates:
            try:
                c_series = closes[t].dropna()
                v_series = volumes[t].dropna()
                if len(c_series) < 10:
                    continue

                price     = float(c_series.iloc[-1])
                price_30d = float(c_series.iloc[0])
                mom_30d   = round((price - price_30d) / price_30d * 100, 1)

                avg_vol   = float(v_series.iloc[:-5].mean())
                rec_vol   = float(v_series.iloc[-5:].mean())
                vol_ratio = round(rec_vol / avg_vol, 1) if avg_vol else 1.0

                # Safety filters
                if price < 3:        continue   # no penny stocks
                if mom_30d < 8:      continue   # must have momentum
                if vol_ratio < 1.2:  continue   # must have volume pickup

                momentum.append({
                    "ticker":    t,
                    "price":     round(price, 2),
                    "mom_30d":   mom_30d,
                    "vol_ratio": vol_ratio,
                    "reason":    f"+{mom_30d}% in 30 days, volume {vol_ratio}x avg",
                })
            except:
                pass
    except:
        pass

    # Sort by momentum score (momentum * volume)
    momentum.sort(key=lambda x: x["mom_30d"] * x["vol_ratio"], reverse=True)
    return momentum[:15]  # top 15 momentum picks

# ── Live prices via yfinance ───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(tickers):
    prices = {}
    if not tickers:
        return prices
    try:
        batch = list(dict.fromkeys(tickers))  # dedup preserve order
        data  = yf.download(" ".join(batch), period="5d", interval="1d",
                            progress=False, auto_adjust=True)
        # Handle single vs multi ticker response
        closes  = data["Close"]  if "Close"  in data.columns else data
        volumes = data["Volume"] if "Volume" in data.columns else None
        for t in batch:
            try:
                c = (closes[t] if t in closes.columns else closes).dropna()
                v = (volumes[t] if volumes is not None and t in volumes.columns
                     else None)
                if len(c) >= 2:
                    today_p = float(c.iloc[-1])
                    prev_p  = float(c.iloc[-2])
                    chg     = round((today_p - prev_p) / prev_p * 100, 2)
                    vol_r   = 1.0
                    if v is not None and len(v) >= 5:
                        avg_v = float(v.iloc[:-1].mean())
                        tod_v = float(v.iloc[-1])
                        vol_r = round(tod_v / avg_v, 1) if avg_v else 1.0
                    prices[t] = {
                        "price":     round(today_p, 2),
                        "change":    chg,
                        "prev":      round(prev_p, 2),
                        "vol_ratio": vol_r,
                    }
            except:
                pass
    except:
        pass
    return prices

# ── Claude: search news + generate signals in one call ────────────────────────
def scan_with_claude(prices, client, max_signals=12, momentum_tickers=None, news_articles=None):
    today = datetime.now().strftime("%B %d, %Y")
    momentum_tickers = momentum_tickers or []

    # Build full watchlist = fixed + today's momentum picks
    all_tickers = list(dict.fromkeys(ALL_TICKERS_FIXED + momentum_tickers))

    # Price context — leaders for brevity
    leaders = ["NVDA","AAPL","MSFT","GOOGL","AMZN","META","AMD","TSLA","PANW","CRWD","PLTR","APP"]
    price_lines = [
        f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}% vol{p['vol_ratio']}x)"
        for t in leaders if (p := prices.get(t))
    ]
    all_prices = [
        f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}%)"
        for t in all_tickers if (p := prices.get(t))
    ]
    momentum_note = (
        f"\nMOMENTUM ADDITIONS THIS WEEK (high volume movers, may spike): {', '.join(momentum_tickers)}"
        if momentum_tickers else ""
    )

    # Format pre-fetched RSS news for Claude
    # Build ticker → articles mapping for extra context
    news_by_ticker = {}
    for a in (news_articles or []):
        t = a["ticker"]
        if t not in news_by_ticker:
            news_by_ticker[t] = []
        news_by_ticker[t].append(a)

    news_lines = ""
    if news_articles:
        news_lines = "\nREAL NEWS HEADLINES (from RSS feeds, fetched now):\n"
        news_lines += "\n".join(
            f"- [{a['ticker']}] {a['headline']} ({a['source']})"
            for a in news_articles[:20]
        )

    prompt = f"""You are a senior tech equity analyst. Today is {today}.

TASK: Analyse the news headlines below and identify the {max_signals} strongest trade signals.
Do NOT search the web — use only the headlines provided plus your market knowledge.

WATCHLIST — fixed quality stocks:
{', '.join(ALL_TICKERS_FIXED[:40])}
{momentum_note}
{news_lines}

LEADER PRICES:
{' | '.join(price_lines)}

ALL PRICES:
{' '.join(all_prices[:60])}

INSTRUCTIONS:
1. Use the news headlines above to find DIRECT signals (own catalyst)
2. Find LAGGARD signals — stocks in same theme not yet moved
3. If no strong news, use price momentum and volume as signals
4. ONE signal per ticker maximum — no duplicates
5. Only BULLISH signals unless very strong bearish catalyst
6. Prefer impact_score >= 7

Return ONLY raw JSON object, start with {{ immediately:
{{
  "marketSummary": "one sentence on what is driving tech today",
  "activeThemes": ["AI_CHIPS"],
  "signals": [
    {{
      "ticker": "NVDA",
      "tier": 1,
      "theme": "AI_CHIPS",
      "type": "DIRECT",
      "direction": "bullish",
      "impact_score": 8,
      "headline": "real headline under 90 chars",
      "source": "Reuters",
      "reasoning": "why this moves under 100 chars",
      "entry_price": 219.50,
      "target_price": 230.00,
      "stop_loss": 213.00,
      "hold_days": 3,
      "confidence": "High",
      "risk": "specific risk under 70 chars",
      "articleUrl": "https://..."
    }}
  ]
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = "".join(b.text for b in message.content if hasattr(b, "text")).strip()
    raw = raw.replace("```json","").replace("```","").strip()
    s2, e2 = raw.find("{"), raw.rfind("}")
    if s2 == -1 or e2 == -1:
        raise ValueError("No JSON in response: " + raw[:150])

    result = json.loads(raw[s2:e2+1])

    # Enrich + dedup
    seen_tickers = set()
    enriched = []
    for sig in result.get("signals", []):
        t = sig.get("ticker","")
        if t in seen_tickers or t not in prices:
            continue
        seen_tickers.add(t)
        lp   = prices[t]
        tier = sig.get("tier") or get_tier(t)
        # Momentum picks use tier 4
        if t in momentum_tickers and tier > 2:
            tier = 4
        risk = RISK[tier]
        tk, tv = get_theme(t)
        entry  = lp["price"]
        # Pick up to 2 extra headlines for this ticker
        extra_news = news_by_ticker.get(t, [])
        extra_headlines = [
            f"{a['headline']} — {a['source']}"
            for a in extra_news[1:3]   # skip first (already used as main headline)
        ]
        enriched.append({
            **sig,
            "tier":           tier,
            "themeKey":       sig.get("theme", tk),
            "themeLabel":     UNIVERSE.get(sig.get("theme",tk), tv)["label"],
            "themeIcon":      UNIVERSE.get(sig.get("theme",tk), tv)["icon"],
            "themeColor":     UNIVERSE.get(sig.get("theme",tk), tv)["color"],
            "livePrice":      entry,
            "priceChange":    lp["change"],
            "volRatio":       lp["vol_ratio"],
            "entry_price":    entry,
            "target_price":   round(entry*(1+risk["target"]/100), 2),
            "stop_loss":      round(entry*(1-risk["stop"]/100),   2),
            "suggestedSize":  risk["size"],
            "isMomentum":     t in momentum_tickers,
            "extraHeadlines": extra_headlines,
        })

    result["signals"] = sorted(enriched, key=lambda x: x["impact_score"], reverse=True)
    return result

# ── Pre-earnings via Claude ────────────────────────────────────────────────────
def fetch_earnings_calendar(tickers, finnhub_key=None):
    """
    Fetch REAL upcoming earnings dates from Finnhub earnings calendar.
    Falls back to a curated quarterly schedule if no key available.
    yfinance earnings data is unreliable — do not use it.
    """
    upcoming = []
    today    = datetime.now().date()
    end_date = today + timedelta(days=14)

    # ── Primary: Finnhub earnings calendar (reliable, real dates) ────────────
    if finnhub_key:
        try:
            url = (f"https://finnhub.io/api/v1/calendar/earnings"
                   f"?from={today}&to={end_date}&token={finnhub_key}")
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                ticker_set = set(tickers)
                for e in data.get("earningsCalendar", []):
                    sym = e.get("symbol","")
                    if sym not in ticker_set:
                        continue
                    try:
                        earn_dt  = datetime.strptime(e["date"], "%Y-%m-%d").date()
                        days_away = (earn_dt - today).days
                        if 0 <= days_away <= 14:
                            upcoming.append({
                                "ticker":       sym,
                                "earningsDate": e["date"],
                                "daysAway":     days_away,
                                "epsEstimate":  e.get("epsEstimate"),
                                "revenueEstimate": e.get("revenueEstimate"),
                            })
                    except:
                        pass
            if upcoming:
                return sorted(upcoming, key=lambda x: x["daysAway"])
        except Exception as ex:
            st.warning(f"Finnhub earnings calendar error: {ex}")

    # ── No results or no key — return empty, don't hallucinate dates ─────────
    return []


def scan_earnings_with_claude(prices, client, finnhub_key=None):
    """
    Step 1: fetch REAL earnings dates from Finnhub (reliable)
    Step 2: score setups with Claude — no web search (cheap)
    """
    today_dt = datetime.now()

    # Step 1 — real dates from Finnhub
    with_dates = fetch_earnings_calendar(ALL_TICKERS, finnhub_key)

    if not with_dates:
        raise ValueError(
            f"No upcoming earnings found in the next 14 days for watched tech stocks "
            f"(checked via Finnhub from {today_dt.strftime('%b %d')} to "
            f"{(today_dt + timedelta(days=14)).strftime('%b %d, %Y')}). "
            f"Try again closer to earnings season or check your Finnhub key."
        )

    # Step 2 — score with Claude (no web search)
    today_str = today_dt.strftime("%B %d, %Y")
    price_ref = " ".join(
        f"{u['ticker']}=${prices[u['ticker']]['price']}"
        f"({'+' if prices[u['ticker']]['change']>=0 else ''}{prices[u['ticker']]['change']}%)"
        for u in with_dates[:6] if u["ticker"] in prices
    )
    dates_str = " | ".join(
        f"{u['ticker']} on {u['earningsDate']} ({u['daysAway']}d)"
        + (f" EPS est ${u['epsEstimate']:.2f}" if u.get("epsEstimate") else "")
        for u in with_dates[:6]
    )

    score_prompt = f"""You are a pre-earnings analyst. Today is exactly {today_str}.

These tech stocks have CONFIRMED upcoming earnings (from Finnhub calendar):
{dates_str}

Live prices today: {price_ref}

Score each setup based on:
- Sector peer read-through (did related companies already report strong results?)
- Price action (has stock already moved up = priced in = bad opportunity)
- Recent analyst activity
- Macro tailwinds for that sector
- Any known supply chain signals

Return ONLY a raw JSON array. Start your response with [ immediately, no preamble:
[{{"ticker":"NVDA","earningsDate":"2026-06-15","daysAway":8,"tier":1,"theme":"AI_CHIPS",
"beatProbability":75,"priceNotMoved":true,"overallScore":8,"strategy":"BUY_NOW",
"signals":{{"sectorReadthrough":{{"score":8,"detail":"AMD beat estimates last week"}},
"priceAction":{{"score":9,"detail":"Stock flat — not priced in"}},
"analystActivity":{{"score":7,"detail":"2 upgrades this month"}},
"supplyChain":{{"score":7,"detail":"TSMC reported strong orders"}},
"silence":{{"score":9,"detail":"No profit warnings issued"}}}},"reasoning":"Strong peer read-through, price flat",
"risk":"Guidance cut would override any beat"}}]

Rules:
- BUY_NOW if overallScore>=7, WAIT if 5-6, AVOID if below 5
- Keep all strings under 80 chars
- Start with [ immediately, end with ], no other text"""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": score_prompt}],
    )

    raw = "".join(b.text for b in msg.content if hasattr(b, "text")).strip()
    raw = raw.replace("```json","").replace("```","").strip()
    s, e = raw.find("["), raw.rfind("]")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("Scoring returned no JSON. Response: " + raw[:200])

    try:
        scored = json.loads(raw[s:e+1])
    except Exception as ex:
        raise ValueError(f"JSON parse error: {ex} | {raw[s:s+200]}")

    # Enrich with live prices and computed trade levels
    enriched = []
    for item in scored:
        t = item.get("ticker","")
        if t not in prices:
            continue
        # Verify date matches what Finnhub told us
        real = next((u for u in with_dates if u["ticker"]==t), {})
        lp    = prices[t]
        tier  = item.get("tier") or get_tier(t)
        risk  = RISK[tier]
        entry = lp["price"]
        tk, tv = get_theme(t)
        enriched.append({
            **item,
            "earningsDate":  real.get("earningsDate", item.get("earningsDate","")),
            "daysAway":      real.get("daysAway",     item.get("daysAway",0)),
            "tier":          tier,
            "themeLabel":    UNIVERSE.get(item.get("theme",tk), tv)["label"],
            "themeIcon":     UNIVERSE.get(item.get("theme",tk), tv)["icon"],
            "themeColor":    UNIVERSE.get(item.get("theme",tk), tv)["color"],
            "livePrice":     entry,
            "priceChange":   lp["change"],
            "entryPrice":    entry,
            "targetPre":     round(entry*(1+risk["target"]/100/2), 2),
            "targetPost":    round(entry*(1+risk["target"]/100),   2),
            "stopLoss":      round(entry*(1-risk["stop"]/100),     2),
            "suggestedSize": risk["size"],
            "epsEstimate":   real.get("epsEstimate"),
        })

    return sorted(
        [s for s in enriched if s.get("strategy") != "AVOID"],
        key=lambda x: x["overallScore"], reverse=True
    )


# ── Pure-data laggard detection ───────────────────────────────────────────────
def find_laggards(prices):
    laggards = []
    for theme_key, theme in UNIVERSE.items():
        leaders   = theme["tier1"]
        all_stocks= theme["tier1"] + theme["tier2"] + theme["tier3"]

        leader_moves = [prices[l]["change"] for l in leaders if l in prices]
        if not leader_moves:
            continue
        avg_move = sum(leader_moves) / len(leader_moves)
        if abs(avg_move) < 2.0:
            continue  # theme not active enough

        for ticker in all_stocks:
            if ticker in leaders or ticker not in prices:
                continue
            p   = prices[ticker]
            gap = avg_move - p["change"]
            if gap < 1.5:
                continue  # not lagging enough

            tier  = get_tier(ticker)
            risk  = RISK[tier]
            entry = p["price"]
            leader_str = ", ".join(
                f"{l}({prices[l]['change']:+.1f}%)"
                for l in leaders if l in prices
            )
            score = min(3 + int(gap) + (2 if p["vol_ratio"] >= 1.5 else 0), 9)

            laggards.append({
                "ticker":       ticker,
                "tier":         tier,
                "themeKey":     theme_key,
                "themeLabel":   theme["label"],
                "themeIcon":    theme["icon"],
                "themeColor":   theme["color"],
                "type":         "LAGGARD",
                "direction":    "bullish",
                "impact_score": score,
                "headline":     f"{theme['icon']} {theme['label']} leaders +{avg_move:.1f}% — {ticker} only {p['change']:+.1f}% ({gap:.1f}% gap)",
                "source":       "Price Analysis",
                "reasoning":    f"Leaders: {leader_str}. {ticker} lagging {gap:.1f}% — expected to catch up in 1-3 days.",
                "risk":         f"Reversal in {theme['label']} leaders would pull {ticker} down.",
                "confidence":   "High" if score >= 7 else "Medium",
                "entry_price":  entry,
                "target_price": round(entry * (1 + risk["target"] / 100), 2),
                "stop_loss":    round(entry * (1 - risk["stop"]   / 100), 2),
                "hold_days":    2,
                "livePrice":    entry,
                "priceChange":  p["change"],
                "volRatio":     p["vol_ratio"],
                "suggestedSize":risk["size"],
                "lag_gap":      round(gap, 1),
                "articleUrl":   None,
            })

    # Dedup — one per ticker, keep highest score
    seen = {}
    for l in sorted(laggards, key=lambda x: x["impact_score"], reverse=True):
        if l["ticker"] not in seen:
            seen[l["ticker"]] = l
    return sorted(seen.values(), key=lambda x: x["lag_gap"], reverse=True)

# ── Render helpers ─────────────────────────────────────────────────────────────
def badge(text, color):
    return (f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
            f'font-size:10px;font-weight:700;margin-right:5px;margin-bottom:4px;'
            f'background:{color}18;border:1px solid {color}44;color:{color}">{text}</span>')

def price_box(label, value, color):
    return (f'<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:8px;'
            f'padding:8px 6px;text-align:center">'
            f'<div style="font-size:9px;color:#2a4560;letter-spacing:1px;margin-bottom:3px">{label}</div>'
            f'<div style="font-size:13px;font-weight:700;color:{color};'
            f'font-family:\'JetBrains Mono\',monospace">{value}</div></div>')

def render_signal(sig):
    bull  = sig.get("direction", "bullish") == "bullish"
    dc    = "#4ade80" if bull else "#f87171"
    tc    = {"1":"#4ade80","2":"#fbbf24","3":"#f87171"}.get(str(sig["tier"]),"#38bdf8")
    sc    = "#f87171" if sig["impact_score"]>=8 else "#fbbf24" if sig["impact_score"]>=6 else "#38bdf8"
    bord  = "#fbbf24" if sig.get("type")=="LAGGARD" else dc
    up    = round((sig["target_price"]-sig["entry_price"])/sig["entry_price"]*100,1)
    dn    = round((sig["entry_price"]-sig["stop_loss"])/sig["entry_price"]*100,1)
    rr    = round(up/dn, 1) if dn else 0
    chg_c = "#4ade80" if sig["priceChange"]>=0 else "#f87171"
    # Extra related headlines
    extras = sig.get("extraHeadlines", [])
    extra_news_html = "".join(
        f'<div style="font-size:11px;color:#1e3a5f;margin-top:3px;line-height:1.4">'
        f'📌 {h}</div>'
        for h in extras[:2]
    ) if extras else ""

    st.markdown(f"""
<div style="background:#080f1a;border:1px solid {bord}44;border-left:3px solid {bord};
     border-radius:12px;padding:16px;margin-bottom:16px">
  <div style="margin-bottom:10px;flex-wrap:wrap">
    {badge(RISK[sig['tier']]['label'], tc)}
    {badge(sig['themeIcon']+' '+sig['themeLabel'], sig['themeColor'])}
    {badge('⏳ LAGGARD' if sig.get('type')=='LAGGARD' else '⚡ DIRECT', '#fbbf24' if sig.get('type')=='LAGGARD' else '#38bdf8')}
    {badge('IMPACT '+str(sig['impact_score'])+'/10', sc)}
    {badge(sig.get('confidence','Medium')+' CONF', sc)}
  </div>
  <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px">
    <div style="background:{dc}15;border:1px solid {dc}44;border-radius:8px;
         padding:8px 14px;text-align:center;min-width:64px;flex-shrink:0">
      <div style="font-size:18px;font-weight:900;color:{dc}">{sig['ticker']}</div>
      <div style="font-size:9px;color:{dc};letter-spacing:1px">{'BULL' if bull else 'BEAR'}</div>
    </div>
    <div style="flex:1">
      <div style="font-size:13px;font-weight:600;color:#e2e8f0;line-height:1.5;margin-bottom:5px">
        {sig['headline']}
      </div>
      <div style="font-size:11px;color:#2a4560;margin-bottom:{4 if sig.get('extraHeadlines') else 0}px">
        {sig.get('source','')} · {sig.get('hold_days',2)}d hold · Vol {sig.get('volRatio',1.0)}x
      </div>
      {extra_news_html}
    </div>
  </div>
  <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;margin-bottom:10px;
       display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">LIVE PRICE</div>
      <div style="font-size:22px;font-weight:900;color:#e2e8f0">${sig['livePrice']}</div>
    </div>
    <div style="text-align:center">
      <div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">TODAY</div>
      <div style="font-size:16px;font-weight:700;color:{chg_c}">{'+' if sig['priceChange']>=0 else ''}{sig['priceChange']}%</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">RISK/REWARD</div>
      <div style="font-size:16px;font-weight:700;color:{'#4ade80' if rr>=2 else '#fbbf24'}">{rr}:1</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(price_box("ENTRY",  f"${sig['entry_price']}", "#e2e8f0"), unsafe_allow_html=True)
    c2.markdown(price_box("TARGET", f"${sig['target_price']}", "#4ade80"), unsafe_allow_html=True)
    c3.markdown(price_box("STOP",   f"${sig['stop_loss']}",   "#f87171"), unsafe_allow_html=True)
    c4.markdown(price_box("UPSIDE", f"+{up}%",                "#4ade80"), unsafe_allow_html=True)

    st.markdown(f"""
<div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;
     margin:10px 0;font-size:12px;color:#475569;line-height:1.6">
  💡 {sig['reasoning']}
</div>
<div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {sig['risk']}</div>
<div style="background:{dc}08;border:1px solid {dc}20;border-radius:8px;padding:12px 14px;
     margin-bottom:8px;font-size:12px;color:#e2e8f0;line-height:2;
     font-family:'JetBrains Mono',monospace">
  <div style="font-size:10px;color:{dc};letter-spacing:2px;font-weight:700;margin-bottom:8px">
    📋 TRADE INSTRUCTIONS
  </div>
  <span style="color:{dc};font-weight:700">{'BUY' if bull else 'SELL'}</span>
  {sig['ticker']} @ <strong>${sig['livePrice']}</strong><br>
  Limit sell → <span style="color:#4ade80;font-weight:700">${sig['target_price']}</span>
  (+{up}%)<br>
  Stop-loss  → <span style="color:#f87171;font-weight:700">${sig['stop_loss']}</span>
  (-{dn}%)<br>
  Hold max   → <span style="color:#fbbf24;font-weight:700">{sig.get('hold_days',2)} days</span>
  · Size → <span style="color:#38bdf8;font-weight:700">{sig['suggestedSize']}</span>
</div>""", unsafe_allow_html=True)

    if sig.get("articleUrl"):
        st.markdown(f"[📰 Read Article]({sig['articleUrl']})")
    st.markdown("---")

def render_earnings_setup(s):
    tc    = "#4ade80" if s["tier"]==1 else "#fbbf24" if s["tier"]==2 else "#f87171"
    sc_c  = "#f87171" if s["overallScore"]>=8 else "#fbbf24" if s["overallScore"]>=6 else "#38bdf8"
    up_pre = round((s["targetPre"]-s["entryPrice"])/s["entryPrice"]*100,1)
    up_post= round((s["targetPost"]-s["entryPrice"])/s["entryPrice"]*100,1)
    chg_c = "#4ade80" if s["priceChange"]>=0 else "#f87171"
    strat_c={"BUY_NOW":"#4ade80","WAIT":"#fbbf24","AVOID":"#f87171"}.get(s.get("strategy","WAIT"),"#fbbf24")
    strat_label={"BUY_NOW":"🟢 BUY NOW — sell before earnings","WAIT":"⏸ WAIT — mixed signals","AVOID":"🔴 AVOID"}.get(s.get("strategy","WAIT"),"⏸ WAIT")

    st.markdown(f"""
<div style="background:#080f1a;border:1px solid #fbbf2444;border-left:3px solid #fbbf24;
     border-radius:12px;padding:16px;margin-bottom:16px">
  <div style="margin-bottom:10px">
    {badge(RISK[s['tier']]['label'], tc)}
    {badge(s['themeIcon']+' '+s['themeLabel'], s['themeColor'])}
    {badge('📅 '+str(s['daysAway'])+'d to earnings', '#fbbf24')}
    {badge('SCORE '+str(s['overallScore'])+'/10', sc_c)}
    {badge('BEAT PROB '+str(s['beatProbability'])+'%', '#4ade80' if s['beatProbability']>=70 else '#fbbf24')}
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
    <div style="background:{tc}15;border:1px solid {tc}44;border-radius:8px;
         padding:8px 14px;text-align:center;min-width:64px;flex-shrink:0">
      <div style="font-size:18px;font-weight:900;color:{tc}">{s['ticker']}</div>
      <div style="font-size:9px;color:{tc};letter-spacing:1px">T{s['tier']}</div>
    </div>
    <div>
      <div style="font-size:14px;font-weight:700;color:{strat_c};margin-bottom:4px">
        {strat_label}
      </div>
      <div style="font-size:11px;color:#2a4560">
        Reports {s['earningsDate']} ·
        Not priced in: <span style="color:{'#4ade80' if s['priceNotMoved'] else '#f87171'}">
        {'✓ YES' if s['priceNotMoved'] else '✗ NO'}</span>
      </div>
    </div>
  </div>
  <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;
       display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">LIVE</div>
         <div style="font-size:22px;font-weight:900;color:#e2e8f0">${s['livePrice']}</div></div>
    <div style="text-align:center">
         <div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">TODAY</div>
         <div style="font-size:16px;font-weight:700;color:{chg_c}">{'+' if s['priceChange']>=0 else ''}{s['priceChange']}%</div></div>
    <div style="text-align:right">
         <div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">PRICED IN?</div>
         <div style="font-size:16px;font-weight:700;color:{'#4ade80' if s['priceNotMoved'] else '#f87171'}">
         {'✓ NO' if s['priceNotMoved'] else '✗ YES'}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(price_box("ENTRY",         f"${s['entryPrice']}", "#e2e8f0"), unsafe_allow_html=True)
    c2.markdown(price_box("PRE-EARN TGT",  f"${s['targetPre']}",  "#4ade80"), unsafe_allow_html=True)
    c3.markdown(price_box("POST-EARN TGT", f"${s['targetPost']}", "#fbbf24"), unsafe_allow_html=True)
    c4.markdown(price_box("STOP LOSS",     f"${s['stopLoss']}",   "#f87171"), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    col1.markdown(f"""<div style="background:#4ade8008;border:1px solid #4ade8022;border-radius:8px;
        padding:12px;text-align:center;margin-top:8px">
        <div style="font-size:9px;color:#2a4560;margin-bottom:4px">CONSERVATIVE EXIT</div>
        <div style="font-size:24px;font-weight:900;color:#4ade80">+{up_pre}%</div>
        <div style="font-size:10px;color:#2a4560">sell day before earnings</div></div>""",
        unsafe_allow_html=True)
    col2.markdown(f"""<div style="background:#fbbf2408;border:1px solid #fbbf2422;border-radius:8px;
        padding:12px;text-align:center;margin-top:8px">
        <div style="font-size:9px;color:#2a4560;margin-bottom:4px">AGGRESSIVE EXIT</div>
        <div style="font-size:24px;font-weight:900;color:#fbbf24">+{up_post}%</div>
        <div style="font-size:10px;color:#2a4560">hold through earnings</div></div>""",
        unsafe_allow_html=True)

    sigs = s.get("signals", {})
    if sigs:
        with st.expander("📊 Signal Scorecard"):
            for label, sig in sigs.items():
                score = sig.get("score", 5)
                st.progress(score/10,
                    text=f"**{label}**: {score}/10 — {sig.get('detail','')}")

    st.markdown(f"""
<div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;
     margin:10px 0;font-size:12px;color:#475569;line-height:1.6">💡 {s['reasoning']}</div>
<div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {s['risk']}</div>
<div style="background:#4ade8008;border:1px solid #4ade8020;border-radius:8px;padding:12px 14px;
     margin-bottom:8px;font-size:12px;color:#e2e8f0;line-height:2;
     font-family:'JetBrains Mono',monospace">
  <div style="font-size:10px;color:#4ade80;letter-spacing:2px;font-weight:700;margin-bottom:8px">
    📋 TRADE PLAN
  </div>
  <span style="color:#4ade80;font-weight:700">BUY</span>
  {s['ticker']} @ <strong>${s['entryPrice']}</strong> now<br>
  Conservative: sell before earnings →
  <span style="color:#4ade80">${s['targetPre']}</span> (+{up_pre}%)<br>
  Aggressive: hold through →
  <span style="color:#fbbf24">${s['targetPost']}</span> (+{up_post}%)<br>
  Stop-loss: <span style="color:#f87171;font-weight:700">${s['stopLoss']}</span>
  · Size: <span style="color:#38bdf8;font-weight:700">{s['suggestedSize']}</span>
</div>""", unsafe_allow_html=True)
    st.markdown("---")

# ── Layout ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
  <div style="width:9px;height:9px;border-radius:50%;background:#4ade80;
       box-shadow:0 0 10px #4ade80"></div>
  <span style="font-size:11px;color:#4ade80;letter-spacing:3px">TECH SIGNAL SCANNER</span>
</div>
<h1 style="font-size:26px;font-weight:900;color:#e2e8f0;margin:0 0 4px 0">
  AI · Cloud · Cyber · Big Tech
</h1>
<p style="color:#2a4560;font-size:12px;margin:0 0 20px 0">
  Real news via Claude web search · Live prices · Laggard detection ·
  Pre-earnings setups · Top signals only
</p>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("## ⚙️ Settings")

# ── Persistent API key: session state → secrets → manual entry ────────────────
# Priority: 1) already in session  2) st.secrets  3) user types it
if "anthropic_key" not in st.session_state:
    try:
        st.session_state["anthropic_key"] = st.secrets["ANTHROPIC_API_KEY"]
    except:
        st.session_state["anthropic_key"] = ""

def _save_key():
    st.session_state["anthropic_key"] = st.session_state["_key_input"]

typed = st.sidebar.text_input(
    "Anthropic API Key:",
    value=st.session_state["anthropic_key"],
    type="password",
    key="_key_input",
    on_change=_save_key,
    help="Saved for this session automatically. For permanent storage add to Streamlit secrets.",
)
# Also capture if user typed without pressing Enter
if typed:
    st.session_state["anthropic_key"] = typed

anthropic_key = st.session_state["anthropic_key"]

if anthropic_key:
    st.sidebar.success("✓ API key saved for this session")
else:
    st.sidebar.caption("Get your key at console.anthropic.com")

st.sidebar.markdown("---")
max_signals = st.sidebar.slider("Max signals to show", 5, 15, 10)
min_tier = st.sidebar.radio("Min quality tier:", ["Tier 1 only","Tier 1+2","All tiers"], index=1)
st.sidebar.markdown("---")
st.sidebar.caption("**Cost:** ~$0.001/scan · $5 free credit = ~5000 scans")

# Permanent storage tip
with st.sidebar.expander("💾 Save key permanently"):
    st.markdown("""
Add to your Streamlit Cloud secrets:
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```
Go to: App → Settings → Secrets
""")

# Tier filter
tier_map = {"Tier 1 only":[1], "Tier 1+2":[1,2], "All tiers":[1,2,3]}
allowed_tiers = tier_map[min_tier]

# ── Build dynamic universe ────────────────────────────────────────────────────
with st.spinner("Building dynamic universe…"):
    momentum_picks = build_dynamic_universe()
    momentum_tickers = [m["ticker"] for m in momentum_picks]
    ALL_TICKERS = list(dict.fromkeys(ALL_TICKERS_FIXED + momentum_tickers))

# Load prices for full universe
with st.spinner(f"Loading live prices for {len(ALL_TICKERS)} stocks…"):
    prices = fetch_prices(ALL_TICKERS)



# Laggards (always available from price data)
laggards = find_laggards(prices)
laggards = [l for l in laggards if l["tier"] in allowed_tiers]

# Active theme pills from price moves
active_themes = {}
for tk, tv in UNIVERSE.items():
    moves = [prices[l]["change"] for l in tv["tier1"] if l in prices]
    if moves:
        avg = sum(moves)/len(moves)
        if abs(avg) >= 1.5:
            active_themes[tk] = {"avg": avg, "theme": tv}

if active_themes:
    st.markdown("**🔥 Active themes:**")
    tcols = st.columns(min(len(active_themes), 4))
    for i, (k, td) in enumerate(active_themes.items()):
        m = td["avg"]
        c = "#4ade80" if m > 0 else "#f87171"
        tcols[i%4].markdown(
            f'<div style="background:{c}10;border:1px solid {c}33;border-radius:8px;'
            f'padding:8px;text-align:center;margin-bottom:8px">'
            f'<div style="font-size:16px">{td["theme"]["icon"]}</div>'
            f'<div style="font-size:11px;font-weight:700;color:{c}">{td["theme"]["label"]}</div>'
            f'<div style="font-size:12px;color:{c}">{m:+.1f}%</div></div>',
            unsafe_allow_html=True)

# Tabs
tab_sig, tab_lag, tab_earn, tab_prices, tab_universe = st.tabs([
    f"📡 SIGNALS",
    f"⏳ LAGGARDS ({len(laggards)})",
    "📅 EARNINGS",
    f"💹 PRICES ({len(prices)})",
    f"🌐 UNIVERSE ({len(ALL_TICKERS)})",
])

# ── SIGNALS TAB ───────────────────────────────────────────────────────────────
with tab_sig:
    if not anthropic_key:
        st.warning("Add your Anthropic API key in the sidebar to scan for signals")
    else:
        if st.button("⟳  SCAN NOW — Search news + generate signals"):
            with st.spinner("Fetching free RSS news…"):
                news_articles = fetch_rss_news(ALL_TICKERS)
            with st.spinner(f"Claude analysing {len(news_articles)} headlines + scoring signals…"):
                try:
                    client = anthropic.Anthropic(api_key=anthropic_key)
                    result = scan_with_claude(prices, client, max_signals,
                                              momentum_tickers, news_articles)

                    # Market summary
                    if result.get("marketSummary"):
                        st.info(f"📊 {result['marketSummary']}")

                    # Active themes from Claude
                    themes = result.get("activeThemes", [])
                    if themes:
                        theme_labels = [
                            f"{UNIVERSE[t]['icon']} {UNIVERSE[t]['label']}"
                            for t in themes if t in UNIVERSE
                        ]
                        st.markdown(f"**Themes active today:** {' · '.join(theme_labels)}")

                    signals = [
                        s for s in result.get("signals", [])
                        if s["tier"] in allowed_tiers
                    ][:max_signals]

                    if not signals:
                        st.info("No signals found above threshold. Market may be quiet — try again later.")
                    else:
                        direct  = [s for s in signals if s.get("type") != "LAGGARD"]
                        laggard = [s for s in signals if s.get("type") == "LAGGARD"]
                        st.success(
                            f"✓ {len(signals)} signals — "
                            f"{len(direct)} direct news · {len(laggard)} laggards · "
                            f"{sum(1 for s in signals if s['impact_score']>=7)} high impact"
                        )
                        for sig in signals:
                            render_signal(sig)

                except Exception as e:
                    st.error(f"Scan failed: {e}")

# ── LAGGARDS TAB ──────────────────────────────────────────────────────────────
with tab_lag:
    st.markdown("#### Stocks lagging their theme leaders — pure price math, no API needed")
    if not laggards:
        st.info("No laggards right now — theme leaders need to move >2% to trigger laggard detection. Check back when the market is moving.")
    else:
        st.success(f"✓ {len(laggards)} laggards identified from price data alone")
        for lag in laggards[:max_signals]:
            render_signal(lag)

# ── EARNINGS TAB ──────────────────────────────────────────────────────────────
with tab_earn:
    st.markdown("#### Pre-earnings setups — Claude searches calendar + scores beat signals")
    if not anthropic_key:
        st.warning("Add your Anthropic API key in the sidebar")
    else:
        if st.button("⟳  SCAN EARNINGS CALENDAR"):
            with st.spinner("Searching earnings calendar + scoring setups…"):
                try:
                    client  = anthropic.Anthropic(api_key=anthropic_key)
                    setups  = scan_earnings_with_claude(prices, client, finnhub_key)
                    setups  = [s for s in setups if s["tier"] in allowed_tiers]
                    if not setups:
                        st.info("No strong pre-earnings setups found in the next 10 days for tech stocks.")
                    else:
                        st.success(f"✓ {len(setups)} pre-earnings setups")
                        for s in setups:
                            render_earnings_setup(s)
                except Exception as e:
                    st.error(f"Earnings scan failed: {e}")
        else:
            st.markdown("""<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:12px;
                padding:20px;font-size:13px;color:#2a4560;line-height:2.2">
                <div style="font-weight:700;color:#e2e8f0;margin-bottom:10px">What Claude checks:</div>
                ✓ Earnings dates in next 10 days for all watched tech stocks<br>
                ✓ Sector peer read-through (did AI/cloud peers already beat?)<br>
                ✓ Price movement — is it already priced in?<br>
                ✓ Analyst upgrade activity last 2 weeks<br>
                ✓ Supply chain + partner signals<br>
                ✓ Pre-announcement silence check
            </div>""", unsafe_allow_html=True)

# ── PRICES TAB ────────────────────────────────────────────────────────────────
with tab_prices:
    st.markdown("#### Live prices — tech universe")
    theme_sel = st.selectbox("Theme:", ["ALL"] + [
        f"{v['icon']} {v['label']}" for v in UNIVERSE.values()
    ])
    tier_sel = st.radio("Tier:", ["All","T1 only","T1+T2"], horizontal=True)

    filtered = ALL_TICKERS
    if theme_sel != "ALL":
        icon = theme_sel.split(" ")[0]
        for v in UNIVERSE.values():
            if v["icon"] == icon:
                filtered = v["tier1"] + v["tier2"] + v["tier3"]
                break
    if tier_sel == "T1 only":
        filtered = [t for t in filtered if get_tier(t) == 1]
    elif tier_sel == "T1+T2":
        filtered = [t for t in filtered if get_tier(t) <= 2]

    rows = []
    for t in dict.fromkeys(filtered):  # preserve order, dedup
        p = prices.get(t)
        if not p: continue
        tier = get_tier(t)
        tk, tv = get_theme(t)
        rows.append({
            "Ticker":  t,
            "Tier":    f"T{tier}",
            "Theme":   tv["icon"] + " " + tv["label"],
            "Price":   f"${p['price']}",
            "Change":  f"{'+' if p['change']>=0 else ''}{p['change']}%",
            "Volume":  f"{p['vol_ratio']}x avg",
            "Prev":    f"${p['prev']}",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No price data yet")

# ── UNIVERSE TAB ──────────────────────────────────────────────────────────────
with tab_universe:
    st.markdown("#### 🌐 Dynamic Stock Universe")
    st.markdown(
        f"<span style='color:#2a4560;font-size:12px'>Total: **{len(ALL_TICKERS)} stocks** · "
        f"{len(TIER1_FIXED)} anchors + {len(TIER2_FIXED)} growth + "
        f"{len(TIER3_FIXED)} dynamic + {len(momentum_tickers)} momentum picks</span>",
        unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### 🟢 Tier 1 — Anchor Stocks")
    st.caption("Always scanned · Mega cap · Safest · $500 position")
    t1_rows = [{"Ticker":t,"Price":f"${prices.get(t,{}).get('price','—')}",
                "Change":f"{'+' if prices.get(t,{}).get('change',0)>=0 else ''}{prices.get(t,{}).get('change','—')}%",
                "Vol":f"{prices.get(t,{}).get('vol_ratio','—')}x","Stop":"-3%","Target":"+5%","Size":"$500"}
               for t in TIER1_FIXED]
    st.dataframe(pd.DataFrame(t1_rows), use_container_width=True, hide_index=True)

    st.markdown("### 🟡 Tier 2 — Growth Stocks")
    st.caption("S&P 500 tech · Strong fundamentals · $375 position")
    t2_rows = [{"Ticker":t,"Theme":get_theme(t)[1]["icon"]+" "+get_theme(t)[1]["label"],
                "Price":f"${prices.get(t,{}).get('price','—')}",
                "Change":f"{'+' if prices.get(t,{}).get('change',0)>=0 else ''}{prices.get(t,{}).get('change','—')}%",
                "Vol":f"{prices.get(t,{}).get('vol_ratio','—')}x","Size":"$375"}
               for t in TIER2_FIXED]
    st.dataframe(pd.DataFrame(t2_rows), use_container_width=True, hide_index=True)

    st.markdown("### 🔴 Tier 3 — Dynamic Picks")
    st.caption("Higher risk · Smaller cap · $250 position")
    t3_rows = [{"Ticker":t,"Theme":get_theme(t)[1]["icon"]+" "+get_theme(t)[1]["label"],
                "Price":f"${prices.get(t,{}).get('price','—')}",
                "Change":f"{'+' if prices.get(t,{}).get('change',0)>=0 else ''}{prices.get(t,{}).get('change','—')}%",
                "Vol":f"{prices.get(t,{}).get('vol_ratio','—')}x","Size":"$250"}
               for t in TIER3_FIXED]
    st.dataframe(pd.DataFrame(t3_rows), use_container_width=True, hide_index=True)

    st.markdown("### ⚡ Momentum Picks — This Week's Movers")
    st.caption("Auto-detected · 30d momentum >8% · Volume 1.2x+ · Refreshed hourly · $150 max")
    if not momentum_picks:
        st.info("No momentum picks this week — all candidates below threshold.")
    else:
        mom_rows = [{"Ticker":m["ticker"],"30d Move":f"+{m['mom_30d']}%",
                     "Vol Ratio":f"{m['vol_ratio']}x",
                     "Price":f"${prices.get(m['ticker'],{}).get('price',m['price'])}",
                     "Today":f"{'+' if prices.get(m['ticker'],{}).get('change',0)>=0 else ''}{prices.get(m['ticker'],{}).get('change','—')}%",
                     "Why added":m["reason"],"Size":"$150"}
                    for m in momentum_picks]
        st.dataframe(pd.DataFrame(mom_rows), use_container_width=True, hide_index=True)
        st.caption("⚠ Momentum picks are speculative — always use stop-losses")

    st.markdown("---")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Universe",  len(ALL_TICKERS))
    c2.metric("With Live Price", len(prices))
    c3.metric("Momentum Picks",  len(momentum_picks))
    c4.metric("Themes Covered",  len(UNIVERSE))

    st.markdown("""
<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:10px;padding:16px;
     margin-top:16px;font-size:12px;color:#2a4560;line-height:2.2">
  <div style="font-weight:700;color:#c8dff0;margin-bottom:8px">How the universe is built:</div>
  🟢 <b style="color:#c8dff0">Tier 1 Anchors</b> — 10 mega-cap tech stocks, always scanned<br>
  🟡 <b style="color:#c8dff0">Tier 2 Growth</b> — ~45 established S&amp;P 500 tech names<br>
  🔴 <b style="color:#c8dff0">Tier 3 Dynamic</b> — ~25 smaller quality tech picks<br>
  ⚡ <b style="color:#c8dff0">Momentum</b> — auto-detected: &gt;8% 30d move + volume spike + market cap &gt;$2B<br>
  📅 <b style="color:#c8dff0">Earnings week</b> — any tech stock reporting is added automatically
</div>
""", unsafe_allow_html=True)
