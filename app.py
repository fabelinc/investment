import streamlit as st
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

# ── Focused tech universe ─────────────────────────────────────────────────────
# Deliberately narrow — tech, AI, semiconductors, cloud, cybersecurity only
UNIVERSE = {
    "AI_CHIPS": {
        "label": "AI & Semiconductors", "icon": "🤖", "color": "#a78bfa",
        "tier1": ["NVDA", "MSFT", "GOOGL", "AMZN", "META"],
        "tier2": ["AMD", "AVGO", "QCOM", "ARM", "TSM"],
        "tier3": ["MU", "SMCI", "MRVL", "ANET", "WDC"],
    },
    "CLOUD_SAAS": {
        "label": "Cloud & SaaS", "icon": "☁️", "color": "#38bdf8",
        "tier1": ["MSFT", "AMZN", "GOOGL"],
        "tier2": ["CRM", "NOW", "SNOW", "DDOG", "NET"],
        "tier3": ["MDB", "ESTC", "GTLB", "CFLT"],
    },
    "CYBER": {
        "label": "Cybersecurity", "icon": "🔒", "color": "#e879f9",
        "tier1": ["MSFT", "PANW"],
        "tier2": ["CRWD", "ZS", "FTNT", "OKTA", "S"],
        "tier3": ["TENB", "QLYS", "SAIL"],
    },
    "BIG_TECH": {
        "label": "Big Tech", "icon": "💻", "color": "#4ade80",
        "tier1": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
        "tier2": ["TSLA", "NFLX", "UBER", "ORCL"],
        "tier3": ["DELL", "HPQ", "INTC"],
    },
}

# Unique tickers preserving priority order
_seen = set()
ALL_TICKERS = []
for theme in UNIVERSE.values():
    for tier in ["tier1", "tier2", "tier3"]:
        for t in theme[tier]:
            if t not in _seen:
                _seen.add(t)
                ALL_TICKERS.append(t)

RISK = {
    1: {"stop": 3,  "target": 5,  "size": "$500",  "label": "🟢 TIER 1 · BLUE CHIP"},
    2: {"stop": 4,  "target": 8,  "size": "$375",  "label": "🟡 TIER 2 · GROWTH"},
    3: {"stop": 5,  "target": 12, "size": "$250",  "label": "🔴 TIER 3 · DYNAMIC"},
}

def get_tier(ticker):
    for theme in UNIVERSE.values():
        if ticker in theme["tier1"]: return 1
        if ticker in theme["tier2"]: return 2
        if ticker in theme["tier3"]: return 3
    return 2

def get_theme(ticker):
    for k, v in UNIVERSE.items():
        if ticker in v["tier1"] + v["tier2"] + v["tier3"]:
            return k, v
    return "BIG_TECH", UNIVERSE["BIG_TECH"]

# ── Live prices via yfinance ───────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(tickers):
    prices = {}
    try:
        data = yf.download(" ".join(tickers), period="5d", interval="1d",
                           progress=False, auto_adjust=True)
        for t in tickers:
            try:
                closes  = data["Close"][t].dropna()
                volumes = data["Volume"][t].dropna()
                if len(closes) >= 2:
                    today = float(closes.iloc[-1])
                    prev  = float(closes.iloc[-2])
                    chg   = round((today - prev) / prev * 100, 2)
                    avg_v = float(volumes.iloc[:-1].mean())
                    tod_v = float(volumes.iloc[-1])
                    prices[t] = {
                        "price":     round(today, 2),
                        "change":    chg,
                        "prev":      round(prev, 2),
                        "vol_ratio": round(tod_v / avg_v, 1) if avg_v else 1.0,
                    }
            except:
                pass
    except:
        pass
    return prices

# ── Claude: search news + generate signals in one call ────────────────────────
def scan_with_claude(prices, client, max_signals=12):
    today = datetime.now().strftime("%B %d, %Y")

    # Build price context — leaders only for brevity
    leaders = ["NVDA","AAPL","MSFT","GOOGL","AMZN","META","AMD","TSLA","PANW","CRWD"]
    price_lines = []
    for t in leaders:
        p = prices.get(t)
        if p:
            price_lines.append(
                f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}% today, vol {p['vol_ratio']}x)"
            )

    # Full watchlist with prices for reference
    watchlist_prices = []
    for t in ALL_TICKERS:
        p = prices.get(t)
        if p:
            watchlist_prices.append(f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}%)")

    prompt = f"""You are a senior tech equity analyst. Today is {today}.

TASK: Search today's financial news and identify the {max_signals} strongest trade signals for tech stocks.

WATCHLIST (these are the only stocks to consider):
{', '.join(ALL_TICKERS)}

LIVE PRICES:
{' | '.join(price_lines)}

ALL PRICES:
{' '.join(watchlist_prices)}

SEARCH AND ANALYZE:
1. Search for real breaking news today for these tech stocks
2. Identify which themes are active (AI/chips, cloud, cybersecurity, big tech)
3. For each significant news item find:
   - DIRECT signals: stock with its own news catalyst
   - LAGGARD signals: related stocks that haven't priced in the theme move yet
4. Eliminate duplicates — ONE signal per stock maximum
5. Only BULLISH signals unless there is very strong specific bearish catalyst

STRICT RULES:
- Maximum ONE signal per ticker — never repeat a stock
- Only include stocks from the watchlist above
- entry_price MUST exactly match the live price shown
- Prefer TIER 1 and TIER 2 stocks
- Only include if impact_score >= 6
- Keep all text SHORT (headline < 90 chars, reasoning < 100 chars, risk < 70 chars)
- Focus on actionable setups, not noise

Return ONLY a raw JSON object, no markdown:
{{
  "marketSummary": "One sentence on what is driving tech markets today",
  "activeThemes": ["AI_CHIPS", "CLOUD_SAAS"],
  "signals": [
    {{
      "ticker": "NVDA",
      "tier": 1,
      "theme": "AI_CHIPS",
      "type": "DIRECT",
      "direction": "bullish",
      "impact_score": 8,
      "headline": "exact real headline under 90 chars",
      "source": "Reuters",
      "reasoning": "why this moves the stock, under 100 chars",
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
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = "".join(b.text for b in message.content if hasattr(b, "text")).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1:
        raise ValueError("No JSON in response: " + raw[:150])

    result = json.loads(raw[s:e+1])

    # Enrich signals with live prices + dedup
    seen_tickers = set()
    enriched = []
    for sig in result.get("signals", []):
        t = sig.get("ticker", "")
        if t in seen_tickers or t not in prices:
            continue
        seen_tickers.add(t)

        lp   = prices[t]
        tier = sig.get("tier") or get_tier(t)
        risk = RISK[tier]
        tk, tv = get_theme(t)

        # Always recalculate target/stop from live price
        entry  = lp["price"]
        target = round(entry * (1 + risk["target"] / 100), 2)
        stop   = round(entry * (1 - risk["stop"]   / 100), 2)

        enriched.append({
            **sig,
            "tier":         tier,
            "themeKey":     sig.get("theme", tk),
            "themeLabel":   UNIVERSE.get(sig.get("theme", tk), tv)["label"],
            "themeIcon":    UNIVERSE.get(sig.get("theme", tk), tv)["icon"],
            "themeColor":   UNIVERSE.get(sig.get("theme", tk), tv)["color"],
            "livePrice":    entry,
            "priceChange":  lp["change"],
            "volRatio":     lp["vol_ratio"],
            "entry_price":  entry,
            "target_price": target,
            "stop_loss":    stop,
            "suggestedSize":risk["size"],
        })

    result["signals"] = sorted(enriched, key=lambda x: x["impact_score"], reverse=True)
    return result

# ── Pre-earnings via Claude ────────────────────────────────────────────────────
def scan_earnings_with_claude(prices, client):
    today = datetime.now().strftime("%B %d, %Y")
    price_ref = " ".join(
        f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}%)"
        for t, p in prices.items() if t in ALL_TICKERS
    )

    prompt = f"""You are a pre-earnings analyst. Today is {today}.

Search for tech stocks from this list that report earnings in the next 10 days:
{', '.join(ALL_TICKERS)}

Live prices: {price_ref}

For each upcoming earner, score these signals:
- Sector peer read-through (did theme leaders already beat?)
- Price not yet moved (opportunity open?)
- Analyst upgrades in last 2 weeks
- Supply chain / partner signals
- Pre-announcement silence (no warnings = good)

Return ONLY raw JSON, no markdown:
{{
  "setups": [
    {{
      "ticker": "NVDA",
      "earningsDate": "2026-06-05",
      "daysAway": 3,
      "tier": 1,
      "theme": "AI_CHIPS",
      "beatProbability": 78,
      "priceNotMoved": true,
      "overallScore": 8,
      "strategy": "BUY_NOW",
      "signals": {{
        "sectorReadthrough": {{"score": 8, "detail": "AMD beat by 12%"}},
        "priceAction":       {{"score": 9, "detail": "Stock flat — not priced in"}},
        "analystActivity":   {{"score": 7, "detail": "3 upgrades last 2 weeks"}},
        "supplyChain":       {{"score": 8, "detail": "AMAT record orders"}},
        "silence":           {{"score": 9, "detail": "No pre-announcements"}}
      }},
      "reasoning": "Short reason under 100 chars",
      "risk": "Short risk under 70 chars"
    }}
  ]
}}

strategy: BUY_NOW (score>=7), WAIT (score 5-6), AVOID (score<5)
Only include stocks with confirmed earnings in next 10 days. Max 5 setups."""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = "".join(b.text for b in message.content if hasattr(b, "text")).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    s, e = raw.find("{"), raw.rfind("}")
    if s == -1 or e == -1:
        raise ValueError("No JSON: " + raw[:150])

    result = json.loads(raw[s:e+1])

    # Enrich setups
    enriched = []
    for item in result.get("setups", []):
        t = item.get("ticker", "")
        if t not in prices:
            continue
        lp   = prices[t]
        tier = item.get("tier") or get_tier(t)
        risk = RISK[tier]
        entry = lp["price"]
        tk, tv = get_theme(t)
        enriched.append({
            **item,
            "tier":         tier,
            "themeLabel":   UNIVERSE.get(item.get("theme", tk), tv)["label"],
            "themeIcon":    UNIVERSE.get(item.get("theme", tk), tv)["icon"],
            "themeColor":   UNIVERSE.get(item.get("theme", tk), tv)["color"],
            "livePrice":    entry,
            "priceChange":  lp["change"],
            "entryPrice":   entry,
            "targetPre":    round(entry * (1 + risk["target"] / 100 / 2), 2),
            "targetPost":   round(entry * (1 + risk["target"] / 100), 2),
            "stopLoss":     round(entry * (1 - risk["stop"]   / 100), 2),
            "suggestedSize":risk["size"],
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
      <div style="font-size:11px;color:#2a4560">
        {sig.get('source','')} · {sig.get('hold_days',2)}d hold · Vol {sig.get('volRatio',1.0)}x
      </div>
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
        {{"BUY_NOW":"🟢 BUY NOW — sell before earnings","WAIT":"⏸ WAIT — mixed signals"}}
        .get(s.get('strategy','WAIT'),'⏸ WAIT')}
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
anthropic_key = st.sidebar.text_input("Anthropic API Key:", type="password",
    help="console.anthropic.com — ~$0.001 per scan with Haiku")
st.sidebar.markdown("---")
max_signals = st.sidebar.slider("Max signals to show", 5, 15, 10)
min_tier = st.sidebar.radio("Min quality tier:", ["Tier 1 only","Tier 1+2","All tiers"], index=1)
st.sidebar.markdown("---")
st.sidebar.caption("**Cost estimate:** ~$0.001/scan with claude-haiku · $5 free credit covers ~5000 scans")

# Tier filter
tier_map = {"Tier 1 only":[1], "Tier 1+2":[1,2], "All tiers":[1,2,3]}
allowed_tiers = tier_map[min_tier]

# Load prices
with st.spinner("Loading live prices…"):
    prices = fetch_prices(ALL_TICKERS)

# Leader strip
leaders = ["NVDA","AAPL","MSFT","GOOGL","AMZN","META","AMD","TSLA","PANW","CRWD"]
cols = st.columns(len(leaders))
for i, t in enumerate(leaders):
    p = prices.get(t)
    if p:
        cols[i].metric(t, f"${p['price']}", f"{'+' if p['change']>=0 else ''}{p['change']}%")

st.markdown("---")

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
tab_sig, tab_lag, tab_earn, tab_prices = st.tabs([
    f"📡 SIGNALS",
    f"⏳ LAGGARDS ({len(laggards)})",
    "📅 EARNINGS",
    f"💹 PRICES ({len(prices)})",
])

# ── SIGNALS TAB ───────────────────────────────────────────────────────────────
with tab_sig:
    if not anthropic_key:
        st.warning("Add your Anthropic API key in the sidebar to scan for signals")
    else:
        if st.button("⟳  SCAN NOW — Search news + generate signals"):
            with st.spinner("Claude searching real news + scoring signals…"):
                try:
                    client = anthropic.Anthropic(api_key=anthropic_key)
                    result = scan_with_claude(prices, client, max_signals)

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
                    setups  = scan_earnings_with_claude(prices, client)
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
