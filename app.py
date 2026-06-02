import streamlit as st
import yfinance as yf
import requests
import anthropic
from datetime import datetime, timedelta
import json
import time

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Signal Scanner",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    code, .mono { font-family: 'JetBrains Mono', monospace; }
    
    .stApp { background: #03060d; color: #c8dff0; }
    .block-container { padding: 1.5rem 2rem; }
    
    /* Metric cards */
    [data-testid="metric-container"] {
        background: #080f1a;
        border: 1px solid #0e1e35;
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricValue"] { color: #c8dff0 !important; font-family: 'JetBrains Mono', monospace !important; }
    [data-testid="stMetricLabel"] { color: #2a4560 !important; font-size: 10px !important; letter-spacing: 2px; text-transform: uppercase; }
    [data-testid="stMetricDelta"] { font-family: 'JetBrains Mono', monospace !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background: #080f1a; border-right: 1px solid #0e1e35; }
    [data-testid="stSidebar"] label { color: #2a4560 !important; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; }
    
    /* Buttons */
    .stButton > button {
        background: #0e1e35;
        color: #38bdf8;
        border: 1px solid #38bdf844;
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        letter-spacing: 1px;
        transition: all 0.2s;
    }
    .stButton > button:hover { background: #38bdf818; border-color: #38bdf8; }
    
    /* Signal cards */
    .signal-card {
        background: #080f1a;
        border: 1px solid #0e1e35;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 16px;
        font-family: 'JetBrains Mono', monospace;
    }
    .signal-card.bullish { border-left: 3px solid #4ade80; }
    .signal-card.bearish { border-left: 3px solid #f87171; }
    .signal-card.laggard { border-left: 3px solid #fbbf24; }
    
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 700;
        margin-right: 6px;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: 0.5px;
    }
    .badge-green  { background: #4ade8018; border: 1px solid #4ade8044; color: #4ade80; }
    .badge-red    { background: #f8717118; border: 1px solid #f8717144; color: #f87171; }
    .badge-amber  { background: #fbbf2418; border: 1px solid #fbbf2444; color: #fbbf24; }
    .badge-blue   { background: #38bdf818; border: 1px solid #38bdf844; color: #38bdf8; }
    .badge-purple { background: #a78bfa18; border: 1px solid #a78bfa44; color: #a78bfa; }
    
    .price-box {
        background: #141f33;
        border: 1px solid #0e1e35;
        border-radius: 8px;
        padding: 10px 14px;
        text-align: center;
        font-family: 'JetBrains Mono', monospace;
    }
    .live-price {
        background: #0e1e35;
        border-radius: 8px;
        padding: 10px 16px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 10px 0;
        font-family: 'JetBrains Mono', monospace;
    }
    .instructions {
        background: #0a1628;
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid #141f33;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
        line-height: 1.8;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { background: #080f1a; border-bottom: 1px solid #0e1e35; gap: 0; }
    .stTabs [data-baseweb="tab"] { color: #2a4560; font-family: 'JetBrains Mono', monospace; font-size: 12px; letter-spacing: 1px; }
    .stTabs [aria-selected="true"] { color: #38bdf8 !important; border-bottom: 2px solid #38bdf8 !important; }
    
    /* Expander */
    .streamlit-expanderHeader { background: #080f1a !important; color: #2a4560 !important; border: 1px solid #0e1e35 !important; border-radius: 8px !important; font-family: 'JetBrains Mono', monospace !important; }
    
    /* Selectbox / inputs */
    .stSelectbox > div > div { background: #080f1a; border: 1px solid #0e1e35; color: #c8dff0; }
    .stTextInput > div > div > input { background: #080f1a; border: 1px solid #0e1e35; color: #c8dff0; font-family: 'JetBrains Mono', monospace; }
    
    div[data-testid="stHorizontalBlock"] { gap: 8px; }
    hr { border-color: #0e1e35; }
</style>
""", unsafe_allow_html=True)

# ── Universe ──────────────────────────────────────────────────────────────────
UNIVERSE = {
    "AI":         {"label":"AI & Chips",      "icon":"🤖", "leaders":["NVDA","AMD","MSFT"], "tier1":["NVDA","MSFT","GOOGL","AMZN","META"], "tier2":["AMD","CRM","NOW","PANW","ORCL","SNOW"], "tier3":["SMCI","DELL","MRVL","ANET","MU","WDC"]},
    "RATES":      {"label":"Rates & Finance", "icon":"🏦", "leaders":["JPM","GS"],            "tier1":["JPM","BAC","GS","V","MA"],            "tier2":["AXP","BLK","SCHW","MS","COF"],         "tier3":["ALLY","SYF"]},
    "HEALTHCARE": {"label":"Healthcare",      "icon":"💊", "leaders":["JNJ","UNH"],           "tier1":["JNJ","UNH","PFE","MRK","ABBV"],        "tier2":["LLY","TMO","ABT","ISRG","MDT"],        "tier3":["DXCM","VEEV"]},
    "CONSUMER":   {"label":"Consumer",        "icon":"🛒", "leaders":["AMZN","WMT"],          "tier1":["AMZN","WMT","COST","HD"],              "tier2":["TGT","MCD","SBUX","NKE","LOW"],        "tier3":["ETSY","ROST"]},
    "ENERGY":     {"label":"Energy",          "icon":"⛽", "leaders":["XOM","CVX"],           "tier1":["XOM","CVX"],                          "tier2":["COP","SLB","OXY","PSX","VLO"],        "tier3":["DVN","MRO"]},
    "INDUSTRIAL": {"label":"Industrial",      "icon":"⚙️", "leaders":["CAT","HON"],           "tier1":["CAT","HON","GE"],                     "tier2":["DE","EMR","ETN","ITW","PH"],           "tier3":["ROK","XYL"]},
    "CYBER":      {"label":"Cybersecurity",   "icon":"🔒", "leaders":["PANW","CRWD"],         "tier1":["PANW","MSFT"],                        "tier2":["CRWD","ZS","FTNT","OKTA","S"],         "tier3":["TENB","QLYS"]},
    "CLOUD":      {"label":"Cloud",           "icon":"☁️", "leaders":["AMZN","MSFT"],         "tier1":["AMZN","MSFT","GOOGL"],                "tier2":["NOW","CRM","SNOW","DDOG","NET"],       "tier3":["ESTC","MDB"]},
}

ALL_TICKERS = list(set(t for theme in UNIVERSE.values() for tier in ["tier1","tier2","tier3"] for t in theme[tier]))

RISK = {1: {"stop":3, "target":5, "size":"$500"}, 2: {"stop":4, "target":8, "size":"$375"}, 3: {"stop":5, "target":12, "size":"$250"}}

def get_tier(ticker):
    for theme in UNIVERSE.values():
        if ticker in theme["tier1"]: return 1
        if ticker in theme["tier2"]: return 2
        if ticker in theme["tier3"]: return 3
    return 2

def get_theme(ticker):
    for key, theme in UNIVERSE.items():
        if ticker in theme["tier1"]+theme["tier2"]+theme["tier3"]:
            return key, theme
    return "AI", UNIVERSE["AI"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 📡 Signal Scanner")
st.sidebar.markdown("---")

finnhub_key  = st.sidebar.text_input("Finnhub API Key:", type="password", help="Get free key at finnhub.io")
anthropic_key = st.sidebar.text_input("Anthropic API Key:", type="password", help="Get at console.anthropic.com")

st.sidebar.markdown("---")
st.sidebar.markdown("**Scan Settings**")
scan_mode = st.sidebar.radio("Mode", ["Manual", "Auto (30 min)"], index=0)

st.sidebar.markdown("---")
st.sidebar.markdown("**Tier Filter**")
show_t1 = st.sidebar.checkbox("Tier 1 — Blue Chip ($500)",  value=True)
show_t2 = st.sidebar.checkbox("Tier 2 — Growth ($375)",     value=True)
show_t3 = st.sidebar.checkbox("Tier 3 — Dynamic ($250)",    value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("**Theme Filter**")
show_themes = {}
for k, v in UNIVERSE.items():
    show_themes[k] = st.sidebar.checkbox(f"{v['icon']} {v['label']}", value=True)

# ── Data functions ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(tickers):
    prices = {}
    try:
        data = yf.download(tickers, period="2d", interval="1d", progress=False, auto_adjust=True)
        closes = data["Close"]
        for t in tickers:
            try:
                today_p  = float(closes[t].iloc[-1])
                yest_p   = float(closes[t].iloc[-2])
                change   = round((today_p - yest_p) / yest_p * 100, 2)
                prices[t] = {"price": round(today_p,2), "change": change, "prev": round(yest_p,2)}
            except:
                pass
    except:
        pass
    return prices

@st.cache_data(ttl=900)
def fetch_finnhub_news(tickers, api_key):
    """Fetch via server-side requests — no CORS issue in Streamlit"""
    articles = []
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    for ticker in tickers[:8]:
        try:
            url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={yesterday}&to={today}&token={api_key}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    for a in data[:3]:
                        articles.append({
                            "ticker":      ticker,
                            "headline":    a.get("headline",""),
                            "source":      a.get("source",""),
                            "url":         a.get("url",""),
                            "summary":     a.get("summary","")[:200],
                            "publishedAt": datetime.fromtimestamp(a.get("datetime",0)).isoformat() if a.get("datetime") else "",
                        })
            time.sleep(0.2)  # rate limit courtesy
        except:
            pass
    
    return sorted(articles, key=lambda x: x.get("publishedAt",""), reverse=True)

def score_with_claude(articles, prices, api_key):
    """Use Claude to score news articles into trade signals"""
    if not articles:
        return []

    client = anthropic.Anthropic(api_key=api_key)
    
    price_ref = " ".join([
        f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}%)"
        for t,p in list(prices.items())[:20]
    ])
    
    article_list = "\n".join([
        f"{i+1}. [{a['ticker']}] {a['headline']} — {a['source']}"
        for i,a in enumerate(articles[:10])
    ])
    
    theme_map = "\n".join([
        f"{k}: leaders={','.join(v['leaders'])} tier2={','.join(v['tier2'])}"
        for k,v in UNIVERSE.items()
    ])

    prompt = f"""You are a senior equity analyst. Score these REAL news articles and find laggard opportunities.

Articles:
{article_list}

Theme map:
{theme_map}

Live prices: {price_ref}

For each significant article (impact>=4), identify:
1. Direct signals for the mentioned stock
2. Laggard opportunities — related stocks in same theme not yet moved

Return ONLY raw JSON array, no markdown:
[{{"id":"s001","ticker":"DELL","tier":2,"theme":"AI","headline":"exact headline","source":"Reuters","type":"LAGGARD","direction":"bullish","impact_score":7,"reasoning":"Short reason under 80 chars.","entry_price":142.50,"target_price":154.00,"stop_loss":136.80,"hold_days":3,"confidence":"High","risk":"Short risk under 60 chars.","articleUrl":"https://..."}}]

Rules:
- entry_price MUST match live price above
- type: LAGGARD or DIRECT
- Max 5 signals, keep strings SHORT"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role":"user","content":prompt}]
    )
    
    raw = message.content[0].text.strip()
    raw = raw.replace("```json","").replace("```","").strip()
    s,e = raw.find("["), raw.rfind("]")
    if s==-1 or e==-1:
        return []
    
    try:
        signals = json.loads(raw[s:e+1])
    except:
        return []

    # Enrich with live prices
    enriched = []
    for sig in signals:
        lp = prices.get(sig["ticker"])
        tier = sig.get("tier") or get_tier(sig["ticker"])
        risk = RISK[tier]
        entry = lp["price"] if lp else sig.get("entry_price",100)
        theme_key, theme_info = get_theme(sig["ticker"])
        enriched.append({
            **sig,
            "tier":        tier,
            "themeKey":    sig.get("theme", theme_key),
            "themeLabel":  UNIVERSE.get(sig.get("theme","AI"),{}).get("label","Mixed"),
            "themeIcon":   UNIVERSE.get(sig.get("theme","AI"),{}).get("icon","📈"),
            "livePrice":   entry,
            "priceChange": lp["change"] if lp else 0,
            "entry_price": entry,
            "target_price": lp and round(entry*(1+risk["target"]/100),2) or sig.get("target_price"),
            "stop_loss":    lp and round(entry*(1-risk["stop"]/100),2) or sig.get("stop_loss"),
            "suggestedSize": risk["size"],
        })
    return enriched

@st.cache_data(ttl=1800)
def fetch_earnings_calendar(tickers, finnhub_api):
    """Fetch upcoming earnings dates from Finnhub"""
    upcoming = []
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d")
    try:
        url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={future}&token={finnhub_api}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            data = r.json()
            for e in data.get("earningsCalendar",[]):
                if e.get("symbol") in tickers:
                    days = (datetime.strptime(e["date"],"%Y-%m-%d") - datetime.now()).days
                    upcoming.append({
                        "ticker":       e["symbol"],
                        "earningsDate": e["date"],
                        "daysAway":     days,
                        "epsEstimate":  e.get("epsEstimate"),
                        "revenueEstimate": e.get("revenueEstimate"),
                    })
    except:
        pass
    return sorted(upcoming, key=lambda x: x["daysAway"])

def score_earnings(upcoming, prices, anthropic_api):
    """Score upcoming earnings for beat probability"""
    if not upcoming:
        return []
    client = anthropic.Anthropic(api_key=anthropic_api)
    
    ticker_list = ", ".join([u["ticker"] for u in upcoming[:5]])
    price_ref   = " ".join([
        f"{u['ticker']}=${prices.get(u['ticker'],{}).get('price','?')}({'+' if prices.get(u['ticker'],{}).get('change',0)>=0 else ''}{prices.get(u['ticker'],{}).get('change',0)}%)"
        for u in upcoming[:5]
    ])
    dates = ", ".join([f"{u['ticker']} reports {u['earningsDate']} ({u['daysAway']}d)" for u in upcoming[:5]])

    prompt = f"""Score these upcoming earnings for beat probability based on sector read-through, analyst activity, supply chain, macro tailwinds.

Upcoming: {dates}
Live prices: {price_ref}

Return ONLY raw JSON array, no markdown:
[{{"ticker":"NVDA","earningsDate":"2026-06-03","daysAway":4,"tier":1,"theme":"AI","analystConsensus":"Beat expected","beatProbability":78,"priceNotMoved":true,"signals":{{"sectorReadthrough":{{"score":8,"detail":"AMD beat 12%"}},"analystActivity":{{"score":7,"detail":"3 upgrades"}},"supplyChain":{{"score":8,"detail":"AMAT record orders"}},"preAnnouncement":{{"score":9,"detail":"No warnings"}},"macroTailwind":{{"score":7,"detail":"AI capex up"}}}},"overallScore":8,"strategy":"BUY_NOW","targetPreEarnings":228.00,"targetPostEarnings":245.00,"stopLoss":209.00,"reasoning":"Short reason.","risk":"Short risk."}}]

strategy: BUY_NOW / BUY_HOLD / WAIT / AVOID. Keep all strings under 80 chars."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role":"user","content":prompt}]
    )
    raw = message.content[0].text.strip().replace("```json","").replace("```","").strip()
    s,e = raw.find("["), raw.rfind("]")
    if s==-1 or e==-1: return []
    try:
        scored = json.loads(raw[s:e+1])
    except:
        return []

    enriched = []
    for item in scored:
        base  = next((u for u in upcoming if u["ticker"]==item["ticker"]),{})
        lp    = prices.get(item["ticker"],{})
        tier  = item.get("tier") or get_tier(item["ticker"])
        risk  = RISK[tier]
        entry = lp.get("price",100)
        enriched.append({
            **item,
            "earningsDate":      item.get("earningsDate") or base.get("earningsDate",""),
            "daysAway":          item.get("daysAway")     or base.get("daysAway",0),
            "tier":              tier,
            "themeLabel":        UNIVERSE.get(item.get("theme","AI"),{}).get("label","Mixed"),
            "themeIcon":         UNIVERSE.get(item.get("theme","AI"),{}).get("icon","📈"),
            "livePrice":         entry,
            "priceChange":       lp.get("change",0),
            "entryPrice":        entry,
            "targetPreEarnings": item.get("targetPreEarnings") or round(entry*(1+risk["target"]/100/2),2),
            "targetPostEarnings":item.get("targetPostEarnings") or round(entry*(1+risk["target"]/100),2),
            "stopLoss":          item.get("stopLoss") or round(entry*(1-risk["stop"]/100),2),
            "suggestedSize":     risk["size"],
            "epsEstimate":       base.get("epsEstimate"),
        })
    return enriched

# ── Render helpers ─────────────────────────────────────────────────────────────
def tier_badge(tier):
    labels = {1:"🟢 TIER 1 · BLUE CHIP", 2:"🟡 TIER 2 · GROWTH", 3:"🔴 TIER 3 · DYNAMIC"}
    classes = {1:"badge-green", 2:"badge-amber", 3:"badge-red"}
    return f'<span class="badge {classes[tier]}">{labels[tier]}</span>'

def direction_badge(d):
    return f'<span class="badge badge-green">▲ BULLISH</span>' if d=="bullish" else f'<span class="badge badge-red">▼ BEARISH</span>'

def type_badge(t):
    return f'<span class="badge badge-amber">⏳ LAGGARD</span>' if t=="LAGGARD" else f'<span class="badge badge-blue">⚡ DIRECT</span>'

def score_badge(s):
    cls = "badge-red" if s>=8 else "badge-amber" if s>=6 else "badge-blue"
    return f'<span class="badge {cls}">IMPACT {s}/10</span>'

def render_signal(sig, idx):
    bull = sig["direction"]=="bullish"
    card_class = "bullish" if bull else "bearish"
    if sig.get("type")=="LAGGARD": card_class = "laggard"
    upside = round((sig["target_price"]-sig["entry_price"])/sig["entry_price"]*100,1)
    riskpct= round((sig["entry_price"]-sig["stop_loss"])/sig["entry_price"]*100,1)
    rr     = round(upside/riskpct,1) if riskpct else 0
    chg_color = "#4ade80" if sig["priceChange"]>=0 else "#f87171"

    st.markdown(f"""
<div class="signal-card {card_class}">
  <div style="margin-bottom:10px;">
    {tier_badge(sig['tier'])}
    <span class="badge badge-purple">{sig['themeIcon']} {sig['themeLabel']}</span>
    {type_badge(sig.get('type','DIRECT'))}
    {direction_badge(sig['direction'])}
    {score_badge(sig['impact_score'])}
  </div>
  <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px;">
    <div style="background:{'#4ade8018' if bull else '#f8717118'};border:1px solid {'#4ade8044' if bull else '#f8717144'};border-radius:8px;padding:8px 14px;text-align:center;min-width:64px;">
      <div style="font-size:18px;font-weight:900;color:{'#4ade80' if bull else '#f87171'};font-family:'JetBrains Mono',monospace">{sig['ticker']}</div>
      <div style="font-size:9px;color:{'#4ade80' if bull else '#f87171'};letter-spacing:1px">{'BULL' if bull else 'BEAR'}</div>
    </div>
    <div style="flex:1">
      <div style="font-size:14px;font-weight:600;color:#e2e8f0;line-height:1.5;margin-bottom:4px">{sig['headline']}</div>
      <div style="font-size:11px;color:#2a4560">{sig['source']} · {sig.get('hold_days',2)}d hold · {sig['confidence']} confidence</div>
    </div>
  </div>
  <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;margin-bottom:10px;display:flex;justify-content:space-between;">
    <div><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">LIVE PRICE</div><div style="font-size:20px;font-weight:900;font-family:'JetBrains Mono',monospace;color:#e2e8f0">${sig['livePrice']}</div></div>
    <div style="text-align:center"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">TODAY</div><div style="font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace;color:{chg_color}">{'+' if sig['priceChange']>=0 else ''}{sig['priceChange']}%</div></div>
    <div style="text-align:right"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">RISK/REWARD</div><div style="font-size:16px;font-weight:700;font-family:'JetBrains Mono',monospace;color:{'#4ade80' if rr>=2 else '#fbbf24'}">{rr}:1</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Price boxes
    c1,c2,c3,c4 = st.columns(4)
    for col, label, val, color in [
        (c1,"ENTRY",    f"${sig['entry_price']}", "#e2e8f0"),
        (c2,"TARGET",   f"${sig['target_price']}", "#4ade80"),
        (c3,"STOP",     f"${sig['stop_loss']}",    "#f87171"),
        (c4,f"UPSIDE",  f"+{upside}%",             "#4ade80"),
    ]:
        col.markdown(f"""<div class="price-box">
            <div style="font-size:9px;color:#2a4560;letter-spacing:1px;margin-bottom:4px">{label}</div>
            <div style="font-size:14px;font-weight:700;color:{color};font-family:'JetBrains Mono',monospace">{val}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""
<div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;margin:10px 0;font-size:12px;color:#475569;line-height:1.6">
  💡 {sig['reasoning']}
</div>
<div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {sig['risk']}</div>
<div class="instructions">
  <div style="font-size:10px;color:{'#4ade80' if bull else '#f87171'};letter-spacing:2px;font-weight:700;margin-bottom:8px">📋 TRADE INSTRUCTIONS</div>
  <span style="color:{'#4ade80' if bull else '#f87171'};font-weight:700">{'BUY' if bull else 'SELL'}</span> {sig['ticker']} @ <span style="font-weight:700">${sig['livePrice']}</span> (market order)<br>
  Set limit sell → <span style="color:#4ade80;font-weight:700">${sig['target_price']}</span> (+{upside}%)<br>
  Set stop-loss  → <span style="color:#f87171;font-weight:700">${sig['stop_loss']}</span> (-{riskpct}%)<br>
  Max hold → <span style="color:#fbbf24;font-weight:700">{sig.get('hold_days',2)} days</span> · Suggested size → <span style="color:#38bdf8;font-weight:700">{sig['suggestedSize']}</span>
</div>
""", unsafe_allow_html=True)

    if sig.get("articleUrl"):
        st.markdown(f"[📰 Read Article]({sig['articleUrl']})")
    st.markdown("---")

def render_earnings_card(item):
    bull = True
    tc = "#4ade80" if item["tier"]==1 else "#fbbf24" if item["tier"]==2 else "#f87171"
    sc = item["overallScore"]
    sc_color = "#f87171" if sc>=8 else "#fbbf24" if sc>=6 else "#38bdf8"
    strat_color = {"BUY_NOW":"#4ade80","BUY_HOLD":"#fbbf24","WAIT":"#2a4560","AVOID":"#f87171"}.get(item["strategy"],"#2a4560")
    strat_label = {"BUY_NOW":"🟢 BUY NOW — sell before earnings","BUY_HOLD":"🟡 BUY & HOLD through earnings","WAIT":"⏸ WAIT — signals mixed","AVOID":"🔴 AVOID"}.get(item["strategy"],item["strategy"])
    up_pre  = round((item["targetPreEarnings"]-item["entryPrice"])/item["entryPrice"]*100,1) if item["entryPrice"] else 0
    up_post = round((item["targetPostEarnings"]-item["entryPrice"])/item["entryPrice"]*100,1) if item["entryPrice"] else 0

    st.markdown(f"""
<div class="signal-card bullish">
  <div style="margin-bottom:10px">
    {tier_badge(item['tier'])}
    <span class="badge badge-purple">{item['themeIcon']} {item['themeLabel']}</span>
    <span class="badge badge-amber">📅 {item['daysAway']}d to earnings</span>
    <span class="badge" style="background:{sc_color}18;border:1px solid {sc_color}44;color:{sc_color}">SCORE {sc}/10</span>
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
    <div style="background:{tc}18;border:1px solid {tc}44;border-radius:8px;padding:8px 14px;text-align:center;min-width:64px">
      <div style="font-size:18px;font-weight:900;color:{tc};font-family:'JetBrains Mono',monospace">{item['ticker']}</div>
      <div style="font-size:9px;color:{tc};letter-spacing:1px">T{item['tier']}</div>
    </div>
    <div>
      <div style="font-size:14px;font-weight:700;color:{strat_color};margin-bottom:4px">{strat_label}</div>
      <div style="font-size:11px;color:#2a4560">Earnings: {item['earningsDate']} · Beat prob: <span style="color:{'#4ade80' if item['beatProbability']>=70 else '#fbbf24'};font-weight:700">{item['beatProbability']}%</span></div>
    </div>
  </div>
  <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;margin-bottom:12px;display:flex;justify-content:space-between">
    <div><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">LIVE PRICE</div><div style="font-size:20px;font-weight:900;font-family:'JetBrains Mono',monospace;color:#e2e8f0">${item['livePrice']}</div></div>
    <div style="text-align:center"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">NOT PRICED IN</div><div style="font-size:16px;font-weight:700;color:{'#4ade80' if item['priceNotMoved'] else '#f87171'}">{'✓ YES' if item['priceNotMoved'] else '✗ NO'}</div></div>
    <div style="text-align:right"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">CONSENSUS</div><div style="font-size:12px;font-weight:700;color:#38bdf8">{item['analystConsensus']}</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    for col,label,val,color in [
        (c1,"ENTRY",        f"${item['entryPrice']}",        "#e2e8f0"),
        (c2,"PRE-EARN TGT", f"${item['targetPreEarnings']}", "#4ade80"),
        (c3,"POST-EARN TGT",f"${item['targetPostEarnings']}", "#fbbf24"),
        (c4,"STOP LOSS",    f"${item['stopLoss']}",          "#f87171"),
    ]:
        col.markdown(f"""<div class="price-box">
            <div style="font-size:9px;color:#2a4560;letter-spacing:1px;margin-bottom:4px">{label}</div>
            <div style="font-size:14px;font-weight:700;color:{color};font-family:'JetBrains Mono',monospace">{val}</div>
        </div>""", unsafe_allow_html=True)

    cc1, cc2 = st.columns(2)
    cc1.markdown(f"""<div style="background:#4ade8008;border:1px solid #4ade8022;border-radius:8px;padding:12px;text-align:center;margin-top:8px">
        <div style="font-size:9px;color:#2a4560;margin-bottom:4px">CONSERVATIVE EXIT</div>
        <div style="font-size:22px;font-weight:900;color:#4ade80;font-family:'JetBrains Mono',monospace">+{up_pre}%</div>
        <div style="font-size:10px;color:#2a4560">sell day before earnings</div>
    </div>""", unsafe_allow_html=True)
    cc2.markdown(f"""<div style="background:#fbbf2408;border:1px solid #fbbf2422;border-radius:8px;padding:12px;text-align:center;margin-top:8px">
        <div style="font-size:9px;color:#2a4560;margin-bottom:4px">AGGRESSIVE EXIT</div>
        <div style="font-size:22px;font-weight:900;color:#fbbf24;font-family:'JetBrains Mono',monospace">+{up_post}%</div>
        <div style="font-size:10px;color:#2a4560">hold through earnings</div>
    </div>""", unsafe_allow_html=True)

    # Signal scorecard
    signals = item.get("signals",{})
    if signals:
        with st.expander("📊 Signal Scorecard"):
            for label, key in [
                ("Sector Read-through","sectorReadthrough"),
                ("Analyst Activity",   "analystActivity"),
                ("Supply Chain",       "supplyChain"),
                ("Pre-announcement",   "preAnnouncement"),
                ("Macro Tailwind",     "macroTailwind"),
            ]:
                s = signals.get(key,{})
                if s:
                    score = s.get("score",5)
                    st.progress(score/10, text=f"{label}: **{score}/10** — {s.get('detail','')}")

    st.markdown(f"""
<div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;margin:10px 0;font-size:12px;color:#475569;line-height:1.6">
  💡 {item['reasoning']}
</div>
<div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {item['risk']}</div>
<div class="instructions">
  <div style="font-size:10px;color:#4ade80;letter-spacing:2px;font-weight:700;margin-bottom:8px">📋 TRADE PLAN</div>
  <span style="color:#4ade80;font-weight:700">BUY</span> {item['ticker']} @ <span style="font-weight:700">${item['entryPrice']}</span> now<br>
  Conservative: Sell <span style="color:#fbbf24;font-weight:700">day before earnings</span> → <span style="color:#4ade80">${item['targetPreEarnings']}</span> (+{up_pre}%)<br>
  Aggressive:   Hold through → target <span style="color:#fbbf24">${item['targetPostEarnings']}</span> (+{up_post}%)<br>
  Stop-loss: <span style="color:#f87171;font-weight:700">${item['stopLoss']}</span> · Size: <span style="color:#38bdf8;font-weight:700">{item['suggestedSize']}</span>
</div>
""", unsafe_allow_html=True)
    st.markdown("---")

# ── Main layout ───────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
  <div style="width:10px;height:10px;border-radius:50%;background:#4ade80;box-shadow:0 0 12px #4ade80"></div>
  <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#4ade80;letter-spacing:3px">SIGNAL SCANNER</span>
</div>
<h1 style="font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:900;color:#e2e8f0;margin:0 0 4px 0">Theme-Based Market Intelligence</h1>
<p style="color:#2a4560;font-size:13px;margin:0 0 24px 0">Quality stocks · 8 themes · Laggard detection · Pre-earnings setups · Finnhub news</p>
""", unsafe_allow_html=True)

# API key checks
if not finnhub_key:
    st.warning("⚙️ Add your **Finnhub API key** in the sidebar to fetch real news. Get a free key at [finnhub.io](https://finnhub.io)")
if not anthropic_key:
    st.warning("⚙️ Add your **Anthropic API key** in the sidebar to generate trade signals. Get one at [console.anthropic.com](https://console.anthropic.com)")

# ── Live price ticker strip ───────────────────────────────────────────────────
leaders = ["NVDA","AAPL","MSFT","GOOGL","AMZN","META","TSLA","AMD","JPM","XOM"]
with st.spinner("Loading live prices…"):
    prices = fetch_prices(leaders + ALL_TICKERS)

if prices:
    cols = st.columns(len(leaders))
    for i, t in enumerate(leaders):
        p = prices.get(t)
        if p:
            delta_str = f"{'+' if p['change']>=0 else ''}{p['change']}%"
            cols[i].metric(t, f"${p['price']}", delta_str)

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_signals, tab_earnings, tab_prices, tab_about = st.tabs([
    "📡 SIGNALS", "📅 EARNINGS", "💹 PRICES", "ℹ️ ABOUT"
])

# ── SIGNALS TAB ───────────────────────────────────────────────────────────────
with tab_signals:
    col_scan, col_info = st.columns([1,2])
    with col_scan:
        scan_btn = st.button("⟳  SCAN NOW", use_container_width=True)
    with col_info:
        st.markdown(f"<span style='color:#2a4560;font-size:12px'>Watching {len(ALL_TICKERS)} quality stocks across {len(UNIVERSE)} themes · Finnhub news · Claude scoring</span>", unsafe_allow_html=True)

    if scan_btn:
        if not finnhub_key:
            st.error("Add your Finnhub API key in the sidebar first")
        elif not anthropic_key:
            st.error("Add your Anthropic API key in the sidebar first")
        else:
            # Active theme detection from price moves
            active_themes = []
            for theme_key, theme in UNIVERSE.items():
                leader_moves = [prices.get(l,{}).get("change",0) for l in theme["leaders"] if l in prices]
                avg_move = sum(leader_moves)/len(leader_moves) if leader_moves else 0
                if abs(avg_move) >= 1.5:
                    active_themes.append((theme_key, theme, avg_move))

            if active_themes:
                st.markdown("**🔥 Active Themes Today:**")
                theme_cols = st.columns(min(len(active_themes),4))
                for i,(k,t,move) in enumerate(active_themes):
                    with theme_cols[i%4]:
                        color = "#4ade80" if move>0 else "#f87171"
                        st.markdown(f"""<div style="background:{color}10;border:1px solid {color}33;border-radius:8px;padding:8px 12px;text-align:center;margin-bottom:8px">
                            <div style="font-size:18px">{t['icon']}</div>
                            <div style="font-size:11px;font-weight:700;color:{color}">{t['label']}</div>
                            <div style="font-size:12px;color:{color};font-family:'JetBrains Mono',monospace">{'+' if move>0 else ''}{move:.1f}%</div>
                        </div>""", unsafe_allow_html=True)

            # Fetch Finnhub news
            with st.spinner("📰 Fetching Finnhub news…"):
                # Prioritise tickers in active themes + leaders
                priority = list(set(
                    t for k,theme,_ in active_themes
                    for tier in ["tier1","tier2","tier3"]
                    for t in UNIVERSE[k][tier]
                ))[:10] or leaders
                articles = fetch_finnhub_news(priority, finnhub_key)

            if not articles:
                st.warning("No news found from Finnhub for the last 48 hours. Try again later or check your API key.")
            else:
                st.success(f"✓ Found {len(articles)} articles from Finnhub")

                # Score with Claude
                with st.spinner("🧠 Scoring signals with Claude…"):
                    tiers_to_show = ([1] if show_t1 else []) + ([2] if show_t2 else []) + ([3] if show_t3 else [])
                    active_theme_keys = [k for k,_,_ in active_themes] if active_themes else list(UNIVERSE.keys())
                    themes_to_show = [k for k,v in show_themes.items() if v]

                    try:
                        signals = score_with_claude(articles, prices, anthropic_key)
                        signals = [s for s in signals
                                   if s["tier"] in tiers_to_show
                                   and s.get("themeKey","AI") in themes_to_show]
                        signals.sort(key=lambda x: x["impact_score"], reverse=True)

                        if not signals:
                            st.info("No signals passed the current tier/theme filters. Try enabling more in the sidebar.")
                        else:
                            st.success(f"✓ {len(signals)} signals — {sum(1 for s in signals if s.get('type')=='LAGGARD')} laggards, {sum(1 for s in signals if s['impact_score']>=6)} high impact")
                            for i, sig in enumerate(signals):
                                render_signal(sig, i)
                    except Exception as e:
                        st.error(f"Claude scoring failed: {e}")

# ── EARNINGS TAB ──────────────────────────────────────────────────────────────
with tab_earnings:
    st.markdown("### 📅 Pre-Earnings Setups")
    st.markdown("<span style='color:#2a4560;font-size:12px'>Stocks reporting in next 10 days · scored for beat probability · pre-priced opportunity detection</span>", unsafe_allow_html=True)
    st.markdown("")

    earn_btn = st.button("⟳  SCAN EARNINGS CALENDAR", use_container_width=True)

    if earn_btn:
        if not finnhub_key:
            st.error("Add your Finnhub API key in the sidebar first")
        elif not anthropic_key:
            st.error("Add your Anthropic API key in the sidebar first")
        else:
            with st.spinner("📅 Fetching earnings calendar from Finnhub…"):
                upcoming = fetch_earnings_calendar(ALL_TICKERS, finnhub_key)

            if not upcoming:
                st.info("No upcoming earnings found for watched stocks in the next 12 days.")
            else:
                st.success(f"✓ Found {len(upcoming)} upcoming earnings")
                for u in upcoming[:5]:
                    st.markdown(f"- **{u['ticker']}** reports {u['earningsDate']} ({u['daysAway']}d)")

                with st.spinner("🧠 Scoring beat probability with Claude…"):
                    try:
                        scored = score_earnings(upcoming, prices, anthropic_key)
                        scored = [s for s in scored if s["strategy"] not in ["AVOID"]]
                        scored.sort(key=lambda x: x["overallScore"], reverse=True)

                        if not scored:
                            st.info("No strong pre-earnings setups found right now.")
                        else:
                            st.success(f"✓ {len(scored)} pre-earnings setups scored")
                            for item in scored:
                                render_earnings_card(item)
                    except Exception as e:
                        st.error(f"Scoring failed: {e}")
    else:
        st.markdown("""<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:12px;padding:20px;font-size:13px;color:#2a4560;line-height:2">
            <div style="font-weight:700;color:#e2e8f0;margin-bottom:10px">What this scans for:</div>
            ✓ Stocks in your quality universe reporting earnings in next 10 days<br>
            ✓ Sector peer read-through signals (did competitors already beat?)<br>
            ✓ Recent analyst upgrades and price target raises<br>
            ✓ Supply chain confirmation signals<br>
            ✓ Pre-announcement silence (no warnings = clean)<br>
            ✓ Whether current price has already priced in good news<br>
            ✓ Conservative exit (sell before) vs aggressive (hold through) targets
        </div>""", unsafe_allow_html=True)

# ── PRICES TAB ────────────────────────────────────────────────────────────────
with tab_prices:
    st.markdown("### 💹 Live Prices — Quality Universe")
    theme_filter = st.selectbox("Filter by theme:", ["ALL"] + [f"{v['icon']} {v['label']}" for v in UNIVERSE.values()])
    
    filtered_tickers = ALL_TICKERS
    if theme_filter != "ALL":
        theme_icon = theme_filter.split(" ")[0]
        for k,v in UNIVERSE.items():
            if v["icon"] == theme_icon:
                filtered_tickers = v["tier1"]+v["tier2"]+v["tier3"]
                break
    
    tier_filter = st.radio("Tier:", ["All","Tier 1 only","Tier 1 + 2"], horizontal=True)
    if tier_filter=="Tier 1 only":
        filtered_tickers = [t for t in filtered_tickers if get_tier(t)==1]
    elif tier_filter=="Tier 1 + 2":
        filtered_tickers = [t for t in filtered_tickers if get_tier(t)<=2]

    cols = st.columns(4)
    for i,t in enumerate(filtered_tickers):
        p = prices.get(t)
        if p:
            tier = get_tier(t)
            tier_label = {1:"🟢",2:"🟡",3:"🔴"}[tier]
            theme_k, theme_info = get_theme(t)
            delta_str = f"{'+' if p['change']>=0 else ''}{p['change']}%"
            cols[i%4].metric(
                f"{tier_label} {t} {theme_info['icon']}",
                f"${p['price']}",
                delta_str
            )

# ── ABOUT TAB ─────────────────────────────────────────────────────────────────
with tab_about:
    st.markdown("""
### 📡 Signal Scanner — How It Works

This tool combines **real financial news** (Finnhub), **live prices** (Yahoo Finance via yfinance), and **AI analysis** (Claude) to surface high-quality trade signals.

---

#### 🏗️ Architecture
```
Finnhub API  →  Real company news (last 48h)
yfinance     →  Live prices for 60+ quality stocks  
Claude AI    →  Theme detection + signal scoring + laggard identification
```

#### 🎯 Signal Types
| Type | Description |
|------|-------------|
| **DIRECT** | News directly about this stock |
| **LAGGARD** | Stock in same theme as a mover, hasn't priced it in yet |

#### 📊 Quality Tiers
| Tier | Type | Size | Stop | Target |
|------|------|------|------|--------|
| 🟢 Tier 1 | Blue Chip (AAPL, MSFT, NVDA…) | $500 | -3% | +5% |
| 🟡 Tier 2 | Growth (AMD, CRM, CRWD…) | $375 | -4% | +8% |
| 🔴 Tier 3 | Dynamic (SMCI, ANET, DDOG…) | $250 | -5% | +12% |

#### 🔄 Themes
AI & Chips · Rates & Finance · Healthcare · Consumer · Energy · Industrial · Cybersecurity · Cloud

#### 📅 Pre-Earnings Strategy
1. Find stocks reporting in next 10 days
2. Score 5 signals: sector read-through, analyst activity, supply chain, pre-announcement silence, macro
3. Conservative exit: sell day before earnings (lock in run-up)
4. Aggressive exit: hold through (higher reward, binary risk)

#### ⚠️ Disclaimer
This tool is for informational purposes only. Not financial advice. Always do your own research before trading.
    """)
