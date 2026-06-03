import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Signal Scanner", page_icon="📡", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght=400;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'JetBrains Mono',monospace}
.stApp{background:#03060d;color:#c8dff0}
.block-container{padding:1.2rem 1.8rem}
[data-testid="stSidebar"]{background:#080f1a;border-right:1px solid #0e1e35}
[data-testid="stSidebar"] label{color:#2a4560!important;font-size:11px;letter-spacing:1px}
[data-testid="metric-container"]{background:#080f1a;border:1px solid #0e1e35;border-radius:10px;padding:10px 14px}
[data-testid="stMetricValue"]{color:#c8dff0!important;font-family:'JetBrains Mono',monospace!important}
[data-testid="stMetricLabel"]{color:#2a4560!important;font-size:10px!important;letter-spacing:2px;text-transform:uppercase}
.stButton>button{background:#0e1e35;color:#38bdf8;border:1px solid #38bdf844;border-radius:8px;font-family:'JetBrains Mono',monospace;font-weight:700;letter-spacing:1px}
.stButton>button:hover{background:#38bdf818;border-color:#38bdf8}
.stTabs [data-baseweb="tab-list"]{background:#080f1a;border-bottom:1px solid #0e1e35}
.stTabs [data-baseweb="tab"]{color:#2a4560;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px}
.stTabs [aria-selected="true"]{color:#38bdf8!important;border-bottom:2px solid #38bdf8!important}
.streamlit-expanderHeader{background:#080f1a!important;color:#2a4560!important;border:1px solid #0e1e35!important;border-radius:8px!important}
div[data-testid="stHorizontalBlock"]{gap:8px}
hr{border-color:#0e1e35}
</style>
""", unsafe_allow_html=True)

# ── Universe ───────────────────────────────────────────────────────────────────
UNIVERSE = {
    "AI":       {"label":"AI & Chips",      "icon":"🤖","color":"#a78bfa",
                 "leaders":["NVDA","AMD","MSFT"],
                 "keywords":["nvidia","amd","artificial intelligence","ai","semiconductor","chip","gpu","data center","machine learning","llm","openai","generative"],
                 "tier1":["NVDA","MSFT","GOOGL","AMZN","META"],
                 "tier2":["AMD","CRM","NOW","PANW","ORCL","SNOW"],
                 "tier3":["SMCI","DELL","MRVL","ANET","MU","WDC"]},
    "RATES":    {"label":"Rates & Finance", "icon":"🏦","color":"#34d399",
                 "leaders":["JPM","GS"],
                 "keywords":["federal reserve","fed","interest rate","inflation","bond","yield","rate cut","rate hike","cpi","fomc","treasury","powell"],
                 "tier1":["JPM","BAC","GS","V","MA"],
                 "tier2":["AXP","BLK","SCHW","MS","COF"],
                 "tier3":["ALLY","SYF"]},
    "HEALTHCARE": {"label":"Healthcare",      "icon":"💊","color":"#f87171",
                   "leaders":["JNJ","UNH"],
                   "keywords":["fda","approval","drug","clinical","trial","pharma","biotech","healthcare","medical","cancer","therapy","vaccine"],
                   "tier1":["JNJ","UNH","PFE","MRK","ABBV"],
                   "tier2":["LLY","TMO","ABT","ISRG","MDT"],
                   "tier3":["DXCM","VEEV"]},
    "CONSUMER":   {"label":"Consumer",        "icon":"🛒","color":"#fbbf24",
                   "leaders":["AMZN","WMT"],
                   "keywords":["retail","consumer","spending","sales","e-commerce","amazon","walmart","holiday","shopping","revenue","same-store"],
                   "tier1":["AMZN","WMT","COST","HD"],
                   "tier2":["TGT","MCD","SBUX","NKE","LOW"],
                   "tier3":["ETSY","ROST"]},
    "ENERGY":     {"label":"Energy",          "icon":"⛽","color":"#fb923c",
                   "leaders":["XOM","CVX"],
                   "keywords":["oil","crude","opec","natural gas","energy","barrel","petroleum","lng","pipeline","refinery"],
                   "tier1":["XOM","CVX"],
                   "tier2":["COP","SLB","OXY","PSX","VLO"],
                   "tier3":["DVN","MRO"]},
    "INDUSTRIAL": {"label":"Industrial",      "icon":"⚙️","color":"#60a5fa",
                   "leaders":["CAT","HON"],
                   "keywords":["infrastructure","manufacturing","industrial","construction","equipment","supply chain","tariff","defense","aerospace"],
                   "tier1":["CAT","HON","GE"],
                   "tier2":["DE","EMR","ETN","ITW","PH"],
                   "tier3":["ROK","XYL"]},
    "CYBER":      {"label":"Cybersecurity",   "icon":"🔒","color":"#e879f9",
                   "leaders":["PANW","CRWD"],
                   "keywords":["cybersecurity","hack","breach","ransomware","security","firewall","zero-day","vulnerability","threat","crowdstrike","palo alto"],
                   "tier1":["PANW","MSFT"],
                   "tier2":["CRWD","ZS","FTNT","OKTA","S"],
                   "tier3":["TENB","QLYS"]},
    "CLOUD":      {"label":"Cloud",           "icon":"☁️","color":"#38bdf8",
                   "leaders":["AMZN","MSFT"],
                   "keywords":["cloud","saas","aws","azure","google cloud","subscription","arr","recurring revenue","platform","software"],
                   "tier1":["AMZN","MSFT","GOOGL"],
                   "tier2":["NOW","CRM","SNOW","DDOG","NET"],
                   "tier3":["ESTC","MDB"]},
}

ALL_TICKERS = list(set(
    t for theme in UNIVERSE.values()
    for tier in ["tier1","tier2","tier3"]
    for t in theme[tier]
))

RISK = {
    1: {"stop":3,  "target":5,  "size":"$500",  "label":"🟢 TIER 1 · BLUE CHIP"},
    2: {"stop":4,  "target":8,  "size":"$375",  "label":"🟡 TIER 2 · GROWTH"},
    3: {"stop":5,  "target":12, "size":"$250",  "label":"🔴 TIER 3 · DYNAMIC"},
}

def get_tier(ticker):
    for theme in UNIVERSE.values():
        if ticker in theme["tier1"]: return 1
        if ticker in theme["tier2"]: return 2
        if ticker in theme["tier3"]: return 3
    return 2

def get_themes_for_ticker(ticker):
    return [k for k,v in UNIVERSE.items()
            if ticker in v["tier1"]+v["tier2"]+v["tier3"]]

# ── Data fetching ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_prices(tickers):
    prices = {}
    try:
        batch = " ".join(tickers)
        data  = yf.download(batch, period="5d", interval="1d",
                            progress=False, auto_adjust=True)
        closes = data["Close"]
        volumes= data["Volume"]
        for t in tickers:
            try:
                series = closes[t].dropna()
                vseries= volumes[t].dropna()
                if len(series) >= 2:
                    today = float(series.iloc[-1])
                    prev  = float(series.iloc[-2])
                    chg   = round((today-prev)/prev*100, 2)
                    avg_vol = float(vseries.iloc[:-1].mean())
                    tod_vol = float(vseries.iloc[-1])
                    vol_ratio = round(tod_vol/avg_vol, 1) if avg_vol else 1.0
                    prices[t] = {
                        "price":     round(today, 2),
                        "change":    chg,
                        "prev":      round(prev, 2),
                        "vol_ratio": vol_ratio,
                        "high":      round(float(data["High"][t].iloc[-1]), 2),
                        "low":       round(float(data["Low"][t].iloc[-1]), 2),
                    }
            except: pass
    except: pass
    return prices

@st.cache_data(ttl=900)
def fetch_finnhub_news(tickers, api_key, days_back=2):
    articles = []
    today = datetime.now().strftime("%Y-%m-%d")
    since = (datetime.now()-timedelta(days=days_back)).strftime("%Y-%m-%d")
    for ticker in tickers:
        try:
            url = (f"https://finnhub.io/api/v1/company-news"
                   f"?symbol={ticker}&from={since}&to={today}&token={api_key}")
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                for a in r.json()[:4]:
                    if a.get("headline"):
                        articles.append({
                            "ticker":      ticker,
                            "headline":    a["headline"],
                            "source":      a.get("source",""),
                            "url":         a.get("url",""),
                            "summary":     a.get("summary","")[:300],
                            "published":   datetime.fromtimestamp(
                                               a.get("datetime",0)
                                           ).strftime("%b %d %H:%M") if a.get("datetime") else "",
                        })
        except: pass
    return sorted(articles, key=lambda x: x.get("published",""), reverse=True)

@st.cache_data(ttl=1800)
def fetch_earnings_calendar(tickers, api_key):
    upcoming = []
    today  = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now()+timedelta(days=14)).strftime("%Y-%m-%d")
    try:
        url = (f"https://finnhub.io/api/v1/calendar/earnings"
               f"?from={today}&to={future}&token={api_key}")
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            for e in r.json().get("earningsCalendar",[]):
                if e.get("symbol") in tickers:
                    try:
                        dt   = datetime.strptime(e["date"],"%Y-%m-%d")
                        days = (dt-datetime.now()).days
                        if 0 <= days <= 14:
                            upcoming.append({
                                "ticker":      e["symbol"],
                                "date":        e["date"],
                                "days_away":   days,
                                "eps_est":     e.get("epsEstimate"),
                                "rev_est":     e.get("revenueEstimate"),
                            })
                    except: pass
    except: pass
    return sorted(upcoming, key=lambda x: x["days_away"])

# ── Pure-data intelligence ────────────────────────────────────────────────────

def detect_active_themes(prices):
    active = {}
    for key, theme in UNIVERSE.items():
        moves = [prices[l]["change"] for l in theme["leaders"] if l in prices]
        if moves:
            avg = sum(moves)/len(moves)
            if abs(avg) >= 1.5:
                active[key] = {"avg_move": round(avg,2), "theme": theme}
    return active

def match_article_themes(headline, summary=""):
    text = (headline + " " + summary).lower()
    matched = []
    for key, theme in UNIVERSE.items():
        hits = sum(1 for kw in theme["keywords"] if kw in text)
        if hits > 0:
            matched.append((key, hits))
    return sorted(matched, key=lambda x: x[1], reverse=True)

def score_article(article, prices, active_themes):
    ticker   = article["ticker"]
    headline = article["headline"]
    summary  = article.get("summary","")
    text     = (headline+" "+summary).lower()

    if ticker not in prices:
        return None

    price_data = prices[ticker]
    tier       = get_tier(ticker)
    risk       = RISK[tier]

    score = 1 

    bullish_kw = ["beat", "record", "surge", "upgrade", "buy", "win", "partnership", 
                  "expand", "growth", "profit", "above", "exceed", "acquire", "launch",
                  "approval", "dividend", "buyback", "top", "higher", "gains"]
    bearish_kw = ["miss", "cut", "downgrade", "warn", "drop", "fall", "disappoint", 
                  "below", "layoff", "recall", "investigation", "lawsuit", "loss", 
                  "decline", "concern", "risk", "short", "lower", "slump", "plummet"]

    bull_hits = sum(1 for kw in bullish_kw if kw in text)
    bear_hits = sum(1 for kw in bearish_kw if kw in text)

    direction = "bullish" if bull_hits >= bear_hits else "bearish"
    sentiment_score = min(bull_hits if direction=="bullish" else bear_hits, 4)
    score += sentiment_score

    high_impact_kw = ["fda approval", "earnings", "revenue", "contract", "acquisition", "merger"]
    if any(kw in text for kw in high_impact_kw):
        score += 3

    vol_ratio = price_data.get("vol_ratio", 1.0)
    if vol_ratio >= 1.8:   score += 2
    elif vol_ratio >= 1.2: score += 1

    chg = abs(price_data["change"])
    if chg >= 2.5:   score += 3  
    elif chg >= 1.0: score += 2  
    else:            score += 1  

    ticker_themes = get_themes_for_ticker(ticker)
    for th in ticker_themes:
        if th in active_themes:
            score += 1
            break

    theme_matches = match_article_themes(headline, summary)
    if theme_matches:
        score += min(theme_matches[0][1], 2)

    if score < 3:
        return None

    impact_score = min(score, 10)

    primary_theme = None
    if theme_matches:
        primary_theme = theme_matches[0][0]
    elif ticker_themes:
        primary_theme = ticker_themes[0]
    else:
        primary_theme = "AI"

    theme_info = UNIVERSE[primary_theme]

    entry  = price_data["price"]
    target = round(entry * (1 + risk["target"]/100), 2)
    stop   = round(entry * (1 - risk["stop"]/100), 2)

    hold_days = 3
    if any(kw in text for kw in ["earnings","quarterly","annual"]):   hold_days = 1
    if any(kw in text for kw in ["fda","approval","merger","acquisition"]): hold_days = 5
    if any(kw in text for kw in ["contract","partnership","deal"]):   hold_days = 4

    confidence = "High" if impact_score >= 7 else "Medium" if impact_score >= 5 else "Low"

    category = "General"
    if any(kw in text for kw in ["earnings","eps","revenue","quarterly"]): category = "Earnings"
    elif any(kw in text for kw in ["contract","deal","partnership","agreement"]): category = "Contract"
    elif any(kw in text for kw in ["upgrade","downgrade","target","analyst"]): category = "Analyst"
    elif any(kw in text for kw in ["fda","approval","drug","trial"]): category = "Regulatory"
    elif any(kw in text for kw in ["acquisition","merger","buys","acquires"]): category = "M&A"
    elif any(kw in text for kw in ["buyback","dividend","repurchase"]): category = "Capital Return"

    reasoning = f"Detected actionable {category.lower()} catalyst. Volatility stands at {price_data['change']:.1f}% with solid {vol_ratio}x volume support."
    risk_text = f"Ensure short term {category.lower()} pressure does not compromise long term technical tier targets."

    return {
        "id":           f"{ticker}_{datetime.now().strftime('%H%M%S')}",
        "ticker":       ticker,
        "tier":         tier,
        "theme":        primary_theme,
        "themeLabel":   theme_info["label"],
        "themeIcon":    theme_info["icon"],
        "themeColor":   theme_info["color"],
        "type":         "DIRECT",
        "direction":    direction,
        "impact_score": impact_score,
        "category":     category,
        "headline":     headline,
        "source":       article.get("source",""),
        "published":    article.get("published",""),
        "articleUrl":   article.get("url",""),
        "reasoning":    reasoning,
        "risk":         risk_text,
        "confidence":   confidence,
        "entry_price":  entry,
        "target_price": target,
        "stop_loss":    stop,
        "hold_days":    hold_days,
        "livePrice":    entry,
        "priceChange":  price_data["change"],
        "vol_ratio":    vol_ratio,
        "suggestedSize":risk["size"],
    }

def find_laggards(prices, active_themes):
    laggards = []
    for theme_key, theme_data in active_themes.items():
        theme   = theme_data["theme"]
        avg_move= theme_data["avg_move"]
        if abs(avg_move) < 2.0:
            continue

        direction = "bullish" if avg_move > 0 else "bearish"

        all_stocks = theme["tier1"]+theme["tier2"]+theme["tier3"]
        candidates = [t for t in all_stocks if t not in theme["leaders"] and t in prices]

        for ticker in candidates:
            p = prices[ticker]
            gap = avg_move - p["change"]  

            if direction=="bullish" and gap < 1.5:  continue  
            if direction=="bearish" and gap > -1.5: continue

            tier    = get_tier(ticker)
            risk    = RISK[tier]
            entry   = p["price"]
            target  = round(entry*(1+risk["target"]/100), 2)
            stop    = round(entry*(1-risk["stop"]/100), 2)
            lag_pct = abs(round(gap, 1))

            score = min(3 + int(lag_pct) + (2 if p.get("vol_ratio",1)>=1.5 else 0), 9)

            leader_str = ", ".join(
                f"{l}({prices[l]['change']:+.1f}%)"
                for l in theme["leaders"] if l in prices
            )

            laggards.append({
                "id":           f"LAG_{ticker}_{datetime.now().strftime('%H%M%S')}",
                "ticker":       ticker,
                "tier":         tier,
                "theme":        theme_key,
                "themeLabel":   theme["label"],
                "themeIcon":    theme["icon"],
                "themeColor":   theme["color"],
                "type":         "LAGGARD",
                "direction":    direction,
                "impact_score": score,
                "category":     "Sector Ripple",
                "headline":     f"{theme['icon']} {theme['label']} leaders moved {avg_move:+.1f}% — {ticker} only {p['change']:+.1f}% ({lag_pct}% gap)",
                "source":       "Price Analysis",
                "published":    datetime.now().strftime("%H:%M"),
                "articleUrl":   None,
                "reasoning":    f"Theme leaders: {leader_str}. {ticker} lagging by {lag_pct}% — likely to catch up within 1-3 days as sector momentum broadens.",
                "risk":         f"If {theme['label']} leaders reverse, {ticker} follows down. Verify no company-specific bad news.",
                "confidence":   "High" if score>=7 else "Medium",
                "entry_price":  entry,
                "target_price": target,
                "stop_loss":    stop,
                "hold_days":    2,
                "livePrice":    entry,
                "priceChange":  p["change"],
                "vol_ratio":    p.get("vol_ratio",1.0),
                "suggestedSize":risk["size"],
                "lag_gap":      lag_pct,
            })

    return sorted(laggards, key=lambda x: x["lag_gap"], reverse=True)

def score_pre_earnings(upcoming, prices, finnhub_key):
    setups = []
    for u in upcoming[:8]:
        ticker = u["ticker"]
        if ticker not in prices:
            continue

        p   = prices[ticker]
        tier  = get_tier(ticker)
        risk  = RISK[tier]
        entry = p["price"]

        stock_themes = get_themes_for_ticker(ticker)
        if not stock_themes:
            continue
        primary_theme = stock_themes[0]
        theme = UNIVERSE[primary_theme]

        score = 0
        signal_details = {}

        peer_moves = [prices[l]["change"] for l in theme["leaders"]
                      if l in prices and l != ticker]
        if peer_moves:
            avg_peer = sum(peer_moves)/len(peer_moves)
            peer_score = min(int(abs(avg_peer)*1.5), 8)
            score += peer_score
            signal_details["Sector Read-through"] = {
                "score": peer_score,
                "detail": f"Theme leaders avg {avg_peer:+.1f}% · {'positive signal' if avg_peer>0 else 'negative signal'}"
            }
        else:
            signal_details["Sector Read-through"] = {"score":5,"detail":"No peer data available"}

        if abs(p["change"]) < 0.5:
            score += 3
            signal_details["Price Not Moved"] = {"score":9,"detail":f"Stock flat at {p['change']:+.1f}% — opportunity not priced in"}
        elif abs(p["change"]) < 1.5:
            score += 1
            signal_details["Price Not Moved"] = {"score":6,"detail":f"Modest move {p['change']:+.1f}% — partially priced in"}
        else:
            score += 1
            signal_details["Price Not Moved"] = {"score":3,"detail":f"Already moved {p['change']:+.1f}% — partially priced in"}

        vol_ratio = p.get("vol_ratio",1.0)
        vol_score = min(int(vol_ratio*2), 8)
        score += min(vol_score, 3)
        signal_details["Volume Signal"] = {
            "score": vol_score,
            "detail": f"Volume {vol_ratio}x average — {'institutional interest' if vol_ratio>=1.5 else 'normal activity'}"
        }

        days = u["days_away"]
        if 3 <= days <= 7:
            score += 2
            signal_details["Timing"] = {"score":8,"detail":f"{days} days to earnings — ideal positioning window"}
        elif days <= 2:
            score += 1
            signal_details["Timing"] = {"score":6,"detail":f"{days} days — very close, limited run-up time"}
        else:
            score += 1
            signal_details["Timing"] = {"score":5,"detail":f"{days} days — early positioning, more time for thesis to develop"}

        if u.get("eps_est"):
            score += 1
            signal_details["Analyst Coverage"] = {"score":7,"detail":f"EPS estimate ${u['eps_est']:.2f} — active analyst coverage"}
        else:
            signal_details["Analyst Coverage"] = {"score":4,"detail":"No EPS estimate available"}

        overall = min(score, 10)
        beat_prob = min(40 + overall*5, 90)

        if overall >= 7:   strategy, strat_label = "BUY_NOW", "🟢 BUY NOW — sell before earnings"
        elif overall >= 5: strategy, strat_label = "WAIT",    "⏸ WAIT — mixed signals"
        else:              strategy, strat_label = "AVOID",   "🔴 AVOID"

        target_pre  = round(entry*(1+risk["target"]/100/2), 2)
        target_post = round(entry*(1+risk["target"]/100), 2)
        stop_loss   = round(entry*(1-risk["stop"]/100), 2)

        reasoning = (
            f"Earnings in {days} days. "
            f"{'Sector showing strength — ' if peer_moves and sum(peer_moves)/len(peer_moves)>0 else 'Sector neutral — '}"
            f"{'price not yet moved, opportunity window open.' if abs(p['change'])<0.5 else 'price has some move already priced in.'}"
        )

        setups.append({
            "ticker":        ticker,
            "date":          u["date"],
            "days_away":     days,
            "tier":          tier,
            "theme":         primary_theme,
            "themeLabel":    theme["label"],
            "themeIcon":     theme["icon"],
            "themeColor":    theme["color"],
            "strategy":      strategy,
            "stratLabel":    strat_label,
            "overallScore":  overall,
            "beatProb":      beat_prob,
            "priceNotMoved": abs(p["change"]) < 0.5,
            "livePrice":     entry,
            "priceChange":   p["change"],
            "entryPrice":    entry,
            "targetPre":     target_pre,
            "targetPost":    target_post,
            "stopLoss":      stop_loss,
            "suggestedSize": risk["size"],
            "signals":       signal_details,
            "reasoning":     reasoning,
            "risk":          "Earnings are binary — even good results can drop if guidance disappoints",
            "epsEst":        u.get("eps_est"),
        })

    return sorted(
        [s for s in setups if s["strategy"]!="AVOID"],
        key=lambda x: x["overallScore"],
        reverse=True
    )

# ── Render helpers ─────────────────────────────────────────────────────────────
def badge(text, color):
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;font-size:10px;font-weight:700;margin-right:6px;background:{color}18;border:1px solid {color}44;color:{color}">{text}</span>'

def price_box(label, value, color):
    return f"""<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:8px;padding:8px 6px;text-align:center">
        <div style="font-size:9px;color:#2a4560;letter-spacing:1px;margin-bottom:3px">{label}</div>
        <div style="font-size:13px;font-weight:700;color:{color};font-family:'JetBrains Mono',monospace">{value}</div>
    </div>"""

def render_signal(sig):
    bull  = sig["direction"]=="bullish"
    dc    = "#4ade80" if bull else "#f87171"
    tc    = {"1":"#4ade80","2":"#fbbf24","3":"#f87171"}._get(str(sig["tier"]),"#38bdf8") if hasattr({}, '_get') else "#38bdf8"
    tc    = {"1":"#4ade80","2":"#fbbf24","3":"#f87171"}.get(str(sig["tier"]),"#38bdf8")
    sc    = "#f87171" if sig["impact_score"]>=8 else "#fbbf24" if sig["impact_score"]>=6 else "#38bdf8"
    up    = round((sig["target_price"]-sig["entry_price"])/sig["entry_price"]*100,1)
    dn    = round((sig["entry_price"]-sig["stop_loss"])/sig["entry_price"]*100,1)
    rr    = round(up/dn,1) if dn else 0
    chg_c = "#4ade80" if sig["priceChange"]>=0 else "#f87171"
    bord  = "#fbbf24" if sig["type"]=="LAGGARD" else dc

    st.markdown(f"""<div style="background:#080f1a;border:1px solid {bord}44;border-left:3px solid {bord};border-radius:12px;padding:16px;margin-bottom:14px">
      <div style="margin-bottom:10px">
        {badge(RISK[sig['tier']]['label'], tc)}
        {badge(f"{sig['themeIcon']} {sig['themeLabel']}", sig['themeColor'])}
        {badge('⏳ LAGGARD' if sig['type']=='LAGGARD' else '⚡ DIRECT', '#fbbf24' if sig['type']=='LAGGARD' else '#38bdf8')}
        {badge('▲ BULLISH' if bull else '▼ BEARISH', dc)}
        {badge(f"IMPACT {sig['impact_score']}/10", sc)}
        {badge(sig['category'], '#64748b')}
      </div>
      <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px">
        <div style="background:{dc}15;border:1px solid {dc}44;border-radius:8px;padding:8px 14px;text-align:center;min-width:64px;flex-shrink:0">
          <div style="font-size:18px;font-weight:900;color:{dc}">{sig['ticker']}</div>
          <div style="font-size:9px;color:{dc};letter-spacing:1px">{'BULL' if bull else 'BEAR'}</div>
        </div>
        <div style="flex:1">
          <div style="font-size:13px;font-weight:600;color:#e2e8f0;line-height:1.5;margin-bottom:4px">{sig['headline']}</div>
          <div style="font-size:11px;color:#2a4560">{sig['source']} · {sig['published']} · {sig['hold_days']}d hold · {sig['confidence']} confidence · Vol {sig['vol_ratio']}x</div>
        </div>
      </div>
      <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center">
        <div><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">LIVE PRICE</div><div style="font-size:20px;font-weight:900;color:#e2e8f0">${sig['livePrice']}</div></div>
        <div style="text-align:center"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">TODAY</div><div style="font-size:16px;font-weight:700;color:{chg_c}">{'+' if sig['priceChange']>=0 else ''}{sig['priceChange']}%</div></div>
        <div style="text-align:right"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">RISK/REWARD</div><div style="font-size:16px;font-weight:700;color:{'#4ade80' if rr>=2 else '#fbbf24'}">{rr}:1</div></div>
      </div>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(price_box("ENTRY",  f"${sig['entry_price']}", "#e2e8f0"), unsafe_allow_html=True)
    c2.markdown(price_box("TARGET", f"${sig['target_price']}", "#4ade80"), unsafe_allow_html=True)
    c3.markdown(price_box("STOP",   f"${sig['stop_loss']}",   "#f87171"), unsafe_allow_html=True)
    c4.markdown(price_box("UPSIDE", f"+{up}%",                "#4ade80"), unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;margin:10px 0;font-size:12px;color:#475569;line-height:1.6">
      💡 {sig['reasoning']}
    </div>
    <div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {sig['risk']}</div>
    <div style="background:{dc}08;border:1px solid {dc}20;border-radius:8px;padding:12px 14px;margin-bottom:8px;font-size:12px;color:#e2e8f0;line-height:2;font-family:'JetBrains Mono',monospace">
      <div style="font-size:10px;color:{dc};letter-spacing:2px;font-weight:700;margin-bottom:8px">📋 TRADE INSTRUCTIONS</div>
      <span style="color:{dc};font-weight:700">{'BUY' if bull else 'SELL'}</span> {sig['ticker']} @ <strong>${sig['livePrice']}</strong> (market order)<br>
      Set limit sell → <span style="color:#4ade80;font-weight:700">${sig['target_price']}</span> (+{up}%)<br>
      Set stop-loss  → <span style="color:#f87171;font-weight:700">${sig['stop_loss']}</span> (-{dn}%)<br>
      Max hold → <span style="color:#fbbf24;font-weight:700">{sig['hold_days']} days</span> · Size → <span style="color:#38bdf8;font-weight:700">{sig['suggestedSize']}</span>
    </div>""", unsafe_allow_html=True)

    if sig.get("articleUrl"):
        st.markdown(f"[📰 Read Full Article]({sig['articleUrl']})")
    st.markdown("---")

def render_earnings_setup(s):
    tc     = "#4ade80" if s["tier"]==1 else "#fbbf24" if s["tier"]==2 else "#f87171"
    sc_col = "#f87171" if s["overallScore"]>=8 else "#fbbf24" if s["overallScore"]>=6 else "#38bdf8"
    up_pre = round((s["targetPre"]-s["entryPrice"])/s["entryPrice"]*100,1)
    up_post= round((s["targetPost"]-s["entryPrice"])/s["entryPrice"]*100,1)
    chg_c  = "#4ade80" if s["priceChange"]>=0 else "#f87171"
    strat_c= "#4ade80" if s["strategy"]=="BUY_NOW" else "#64748b"

    st.markdown(f"""<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:12px;padding:16px;margin-bottom:14px">
        <div style="margin-bottom:10px">
            {badge(f"TIER {s['tier']}", tc)}
            {badge(f"{s['themeIcon']} {s['themeLabel']}", s['themeColor'])}
            {badge(s['stratLabel'], strat_c)}
            {badge(f"SCORE {s['overallScore']}/10", sc_col)}
        </div>
        <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
            <div style="background:#0e1e35;border:1px solid #38bdf844;border-radius:8px;padding:8px 14px;text-align:center;min-width:64px">
                <div style="font-size:18px;font-weight:900;color:#38bdf8">{s['ticker']}</div>
                <div style="font-size:9px;color:#2a4560;letter-spacing:1px">{s['days_away']}d away</div>
            </div>
            <div style="flex:1;font-size:13px;color:#e2e8f0;line-height:1.5">
                {s['reasoning']}
            </div>
        </div>
        <div style="background:#060d1a;border:1px solid #0e1e35;border-radius:8px;padding:10px;font-size:11px;color:#475569;margin-bottom:10px">
            ⚠ {s['risk']}
        </div>
    </div>""", unsafe_allow_html=True)
    
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(price_box("ENTRY", f"${s['entryPrice']}", "#e2e8f0"), unsafe_allow_html=True)
    c2.markdown(price_box("RUN-UP TARGET", f"${s['targetPre']} (+{up_pre}%)", "#38bdf8"), unsafe_allow_html=True)
    c3.markdown(price_box("POST TARGET", f"${s['targetPost']} (+{up_post}%)", "#4ade80"), unsafe_allow_html=True)
    c4.markdown(price_box("CRASH STOP", f"${s['stopLoss']}", "#f87171"), unsafe_allow_html=True)
    st.markdown("---")

# ── Main Execution App Loop ───────────────────────────────────────────────────
def main():
    st.title("📡 SIGNAL SCANNER TERMINAL")
    st.sidebar.header("CONFIGURATION")
    
    finnhub_key = st.sidebar.text_input("FINNHUB API KEY", type="password", value="")
    
    if not finnhub_key:
        st.info("Please enter your Finnhub API key in the sidebar to stream direct and laggard signals.")
        return

    with st.spinner("Syncing data feeds across ticker matrix..."):
        prices = fetch_prices(ALL_TICKERS)
        if not prices:
            st.error("Failed to query market pricing feeds from yfinance setup.")
            return
            
        active_themes = detect_active_themes(prices)
        news_articles = fetch_finnhub_news(ALL_TICKERS, finnhub_key)
        earnings_cal  = fetch_earnings_calendar(ALL_TICKERS, finnhub_key)

    tab1, tab2, tab3 = st.tabs(["⚡ DIRECT CATALYSTS", "⏳ THEMATIC LAGGARDS", "🏦 PRE-EARNINGS STRATEGIES"])

    with tab1:
        st.subheader("Real-Time Event Momentum")
        direct_signals = []
        for art in news_articles:
            sig = score_article(art, prices, active_themes)
            if sig:
                direct_signals.append(sig)
                
        if direct_signals:
            for sig in direct_signals:
                render_signal(sig)
        else:
            st.info("No major volatility catalysts cleared the scoring framework threshold.")

    with tab2:
        st.subheader("Sector Dislocation & Catch-Up Plays")
        laggard_signals = find_laggards(prices, active_themes)
        if laggard_signals:
            for lag in laggard_signals:
                render_signal(lag)
        else:
            st.info("No core sector laggards detected with significant leader gaps.")

    with tab3:
        st.subheader("Asymmetric Run-Up Formations")
        earnings_setups = score_pre_earnings(earnings_cal, prices, finnhub_key)
        if earnings_setups:
            for setup in earnings_setups:
                render_earnings_setup(setup)
        else:
            st.info("No liquid earnings run-up setups matched requirements inside the 14-day window.")

if __name__ == "__main__":
    main()
