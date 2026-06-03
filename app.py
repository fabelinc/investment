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
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700;800&display=swap');
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
    "AI":         {"label":"AI & Chips",      "icon":"🤖","color":"#a78bfa",
                   "leaders":["NVDA","AMD","MSFT"],
                   "keywords":["nvidia","amd","artificial intelligence","ai","semiconductor","chip","gpu","data center","machine learning","llm","openai","generative"],
                   "tier1":["NVDA","MSFT","GOOGL","AMZN","META"],
                   "tier2":["AMD","CRM","NOW","PANW","ORCL","SNOW"],
                   "tier3":["SMCI","DELL","MRVL","ANET","MU","WDC"]},
    "RATES":      {"label":"Rates & Finance", "icon":"🏦","color":"#34d399",
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
    """Find themes where leaders are moving significantly"""
    active = {}
    for key, theme in UNIVERSE.items():
        moves = [prices[l]["change"] for l in theme["leaders"] if l in prices]
        if moves:
            avg = sum(moves)/len(moves)
            if abs(avg) >= 1.5:
                active[key] = {"avg_move": round(avg,2), "theme": theme}
    return active

def match_article_themes(headline, summary=""):
    """Match a headline to themes via keywords"""
    text = (headline + " " + summary).lower()
    matched = []
    for key, theme in UNIVERSE.items():
        hits = sum(1 for kw in theme["keywords"] if kw in text)
        if hits > 0:
            matched.append((key, hits))
    return sorted(matched, key=lambda x: x[1], reverse=True)

def score_article(article, prices, active_themes):
    """
    Optimized scoring engine to accurately catch high-quality news drops.
    """
    ticker   = article["ticker"]
    headline = article["headline"]
    summary  = article.get("summary","")
    text     = (headline+" "+summary).lower()

    if ticker not in prices:
        return None

    price_data = prices[ticker]
    tier       = get_tier(ticker)
    risk       = RISK[tier]

    # Initialize Score
    score = 1  # Base point just for matching a core watchlisted company

    # 1. Broadened Sentiment keywords (+/- text matching)
    bullish_kw = ["beat", "record", "surge", "upgrade", "buy", "win", "partnership", 
                  "expand", "growth", "profit", "above", "exceed", "acquire", "launch",
                  "approval", "dividend", "buyback", "top", "higher", "gains"]
    bearish_kw = ["miss", "cut", "downgrade", "warn", "drop", "fall", "disappoint", 
                  "below", "layoff", "recall", "investigation", "lawsuit", "loss", 
                  "decline", "concern", "risk", "short", "lower", "slump", "plummet"]

    bull_hits = sum(1 for kw in bullish_kw if kw in text)
    bear_hits = sum(1 for kw in bearish_kw if kw in text)

    # Determine direction based on heavy keyword clustering
    direction = "bullish" if bull_hits >= bear_hits else "bearish"
    sentiment_score = min(bull_hits if direction=="bullish" else bear_hits, 4)
    score += sentiment_score

    # 2. High-impact conditional clusters (+3 points for huge catalysts)
    high_impact_kw = ["fda approval", "earnings", "revenue", "contract", "acquisition", "merger"]
    if any(kw in text for kw in high_impact_kw):
        score += 3

    # 3. Volume Confirmation (High volume means institutional validity)
    vol_ratio = price_data.get("vol_ratio", 1.0)
    if vol_ratio >= 1.8:   score += 2
    elif vol_ratio >= 1.2: score += 1

    # 4. FIX: Reward High Volatility Moves (Aligns with your strategy)
    chg = abs(price_data["change"])
    if chg >= 2.5:   score += 3  # Massive news impact / high urgency
    elif chg >= 1.0: score += 2  # Moderate news impact
    else:            score += 1  # Slow bleed or minor news

    # 5. Theme leader momentum validation
    ticker_themes = get_themes_for_ticker(ticker)
    for th in ticker_themes:
        if th in active_themes:
            score += 1
            break

    # Lower the gate threshold slightly so interesting articles can pass through
    if score < 3:
        return None

    impact_score = min(score, 10)

    # --- Keep all your styling/variable formatting below the same ---
    primary_theme = theme_matches[0][0] if match_article_themes(headline, summary) else (ticker_themes[0] if ticker_themes else "AI")
    theme_info = UNIVERSE[primary_theme]
    entry  = price_data["price"]
    target = round(entry * (1 + risk["target"]/100), 2)
    stop   = round(entry * (1 - risk["stop"]/100), 2)

    hold_days = 3
    if any(kw in text for kw in ["earnings","quarterly"]): hold_days = 1
    if any(kw in text for kw in ["fda","approval","merger"]): hold_days = 5

    confidence = "High" if impact_score >= 7 else "Medium" if impact_score >= 5 else "Low"
    category = "General"
    if any(kw in text for kw in ["earnings","eps","revenue"]): category = "Earnings"
    elif any(kw in text for kw in ["contract","deal","partnership"]): category = "Contract"
    elif any(kw in text for kw in ["upgrade","downgrade","analyst"]): category = "Analyst"

    reasoning = f"Detected actionable {category.lower()} catalyst. Volatility stands at {price_data['change']:.1f}% with solid {vol_ratio}x volume support."
    risk_text = f"Ensure short term {category.lower()} pressure does not compromise long term technical tier targets."

    return {
        "id": f"{ticker}_{datetime.now().strftime('%H%M%S')}",
        "ticker": ticker, "tier": tier, "theme": primary_theme,
        "themeLabel": theme_info["label"], "themeIcon": theme_info["icon"], "themeColor": theme_info["color"],
        "type": "DIRECT", "direction": direction, "impact_score": impact_score, "category": category,
        "headline": headline, "source": article.get("source",""), "published": article.get("published",""),
        "articleUrl": article.get("url",""), "reasoning": reasoning, "risk": risk_text, "confidence": confidence,
        "entry_price": entry, "target_price": target, "stop_loss": stop, "hold_days": hold_days,
        "livePrice": entry, "priceChange": price_data["change"], "vol_ratio": vol_ratio, "suggestedSize": risk["size"]
    }
def find_laggards(prices, active_themes):
    """
    For each active theme, find stocks that haven't priced in
    the leader's move yet.
    """
    laggards = []
    for theme_key, theme_data in active_themes.items():
        theme   = theme_data["theme"]
        avg_move= theme_data["avg_move"]
        if abs(avg_move) < 2.0:
            continue

        direction = "bullish" if avg_move > 0 else "bearish"

        # All non-leader stocks in this theme
        all_stocks = theme["tier1"]+theme["tier2"]+theme["tier3"]
        candidates = [t for t in all_stocks if t not in theme["leaders"] and t in prices]

        for ticker in candidates:
            p = prices[ticker]
            gap = avg_move - p["change"]  # how much it's lagging

            if direction=="bullish" and gap < 1.5:  continue  # not lagging enough
            if direction=="bearish" and gap > -1.5: continue

            tier    = get_tier(ticker)
            risk    = RISK[tier]
            entry   = p["price"]
            target  = round(entry*(1+risk["target"]/100), 2)
            stop    = round(entry*(1-risk["stop"]/100), 2)
            lag_pct = abs(round(gap, 1))

            # Score: bigger gap = higher score, volume spike helps
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
    """Score upcoming earnings using peer data and price action"""
    setups = []
    for u in upcoming[:8]:
        ticker = u["ticker"]
        if ticker not in prices:
            continue

        p     = prices[ticker]
        tier  = get_tier(ticker)
        risk  = RISK[tier]
        entry = p["price"]

        # Find which themes this stock belongs to
        stock_themes = get_themes_for_ticker(ticker)
        if not stock_themes:
            continue
        primary_theme = stock_themes[0]
        theme = UNIVERSE[primary_theme]

        # ── Score components ──────────────────────────────────────────────────
        score = 0
        signal_details = {}

        # 1. Sector peer moves (read-through)
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

        # 2. Price not moved (not priced in)
        if abs(p["change"]) < 0.5:
            score += 3
            signal_details["Price Not Moved"] = {"score":9,"detail":f"Stock flat at {p['change']:+.1f}% — opportunity not priced in"}
        elif abs(p["change"]) < 1.5:
            score += 1
            signal_details["Price Not Moved"] = {"score":6,"detail":f"Modest move {p['change']:+.1f}% — partially priced in"}
        else:
            signal_details["Price Not Moved"] = {"score":3,"detail":f"Already moved {p['change']:+.1f}% — partially priced in"}

        # 3. Volume signal
        vol_ratio = p.get("vol_ratio",1.0)
        vol_score = min(int(vol_ratio*2), 8)
        score += min(vol_score, 3)
        signal_details["Volume Signal"] = {
            "score": vol_score,
            "detail": f"Volume {vol_ratio}x average — {'institutional interest' if vol_ratio>=1.5 else 'normal activity'}"
        }

        # 4. Days away (sweet spot is 3-7 days)
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

        # 5. EPS estimate exists (analyst coverage = confidence)
        if u.get("eps_est"):
            score += 1
            signal_details["Analyst Coverage"] = {"score":7,"detail":f"EPS estimate ${u['eps_est']:.2f} — active analyst coverage"}
        else:
            signal_details["Analyst Coverage"] = {"score":4,"detail":"No EPS estimate available"}

        overall = min(score, 10)
        beat_prob = min(40 + overall*5, 90)

        # Strategy
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
    strat_c= {"BUY_NOW":"#4ade80","WAIT":"#2a4560","AVOID":"#f87171"}.get(s["strategy"],"#fbbf24")

    st.markdown(f"""<div style="background:#080f1a;border:1px solid #fbbf2444;border-left:3px solid #fbbf24;border-radius:12px;padding:16px;margin-bottom:14px">
      <div style="margin-bottom:10px">
        {badge(RISK[s['tier']]['label'], tc)}
        {badge(f"{s['themeIcon']} {s['themeLabel']}", s['themeColor'])}
        {badge(f"📅 {s['days_away']}d to earnings", '#fbbf24')}
        {badge(f"SCORE {s['overallScore']}/10", sc_col)}
        {badge(f"BEAT PROB {s['beatProb']}%", '#4ade80' if s['beatProb']>=70 else '#fbbf24')}
      </div>
      <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
        <div style="background:{tc}15;border:1px solid {tc}44;border-radius:8px;padding:8px 14px;text-align:center;min-width:64px;flex-shrink:0">
          <div style="font-size:18px;font-weight:900;color:{tc}">{s['ticker']}</div>
          <div style="font-size:9px;color:{tc};letter-spacing:1px">T{s['tier']}</div>
        </div>
        <div style="flex:1">
          <div style="font-size:14px;font-weight:700;color:{strat_c};margin-bottom:4px">{s['stratLabel']}</div>
          <div style="font-size:11px;color:#2a4560">Reports {s['date']} · Not priced in: <span style="color:{'#4ade80' if s['priceNotMoved'] else '#f87171'}">{'✓ YES' if s['priceNotMoved'] else '✗ NO'}</span>{'  · EPS Est: $'+str(s['epsEst']) if s['epsEst'] else ''}</div>
        </div>
      </div>
      <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <div><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">LIVE PRICE</div><div style="font-size:20px;font-weight:900;color:#e2e8f0">${s['livePrice']}</div></div>
        <div style="text-align:center"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">TODAY</div><div style="font-size:16px;font-weight:700;color:{chg_c}">{'+' if s['priceChange']>=0 else ''}{s['priceChange']}%</div></div>
        <div style="text-align:right"><div style="font-size:9px;color:#2a4560;letter-spacing:2px;margin-bottom:2px">NOT PRICED IN</div><div style="font-size:16px;font-weight:700;color:{'#4ade80' if s['priceNotMoved'] else '#f87171'}">{'✓ YES' if s['priceNotMoved'] else '✗ NO'}</div></div>
      </div>
    </div>""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(price_box("ENTRY",         f"${s['entryPrice']}", "#e2e8f0"), unsafe_allow_html=True)
    c2.markdown(price_box("PRE-EARN TGT",  f"${s['targetPre']}",  "#4ade80"), unsafe_allow_html=True)
    c3.markdown(price_box("POST-EARN TGT", f"${s['targetPost']}", "#fbbf24"), unsafe_allow_html=True)
    c4.markdown(price_box("STOP LOSS",     f"${s['stopLoss']}",   "#f87171"), unsafe_allow_html=True)

    cc1,cc2 = st.columns(2)
    cc1.markdown(f"""<div style="background:#4ade8008;border:1px solid #4ade8022;border-radius:8px;padding:12px;text-align:center;margin-top:8px">
        <div style="font-size:9px;color:#2a4560;margin-bottom:4px">CONSERVATIVE EXIT</div>
        <div style="font-size:24px;font-weight:900;color:#4ade80">+{up_pre}%</div>
        <div style="font-size:10px;color:#2a4560">sell day before earnings</div>
    </div>""", unsafe_allow_html=True)
    cc2.markdown(f"""<div style="background:#fbbf2408;border:1px solid #fbbf2422;border-radius:8px;padding:12px;text-align:center;margin-top:8px">
        <div style="font-size:9px;color:#2a4560;margin-bottom:4px">AGGRESSIVE EXIT</div>
        <div style="font-size:24px;font-weight:900;color:#fbbf24">+{up_post}%</div>
        <div style="font-size:10px;color:#2a4560">hold through earnings</div>
    </div>""", unsafe_allow_html=True)

    with st.expander("📊 Signal Scorecard"):
        for label, sig in s["signals"].items():
            score = sig["score"]
            col = "#4ade80" if score>=7 else "#fbbf24" if score>=5 else "#f87171"
            st.progress(score/10, text=f"**{label}**: {score}/10 — {sig['detail']}")

    st.markdown(f"""
    <div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;margin:10px 0;font-size:12px;color:#475569;line-height:1.6">
      💡 {s['reasoning']}
    </div>
    <div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {s['risk']}</div>
    <div style="background:#4ade8008;border:1px solid #4ade8020;border-radius:8px;padding:12px 14px;margin-bottom:8px;font-size:12px;color:#e2e8f0;line-height:2;font-family:'JetBrains Mono',monospace">
      <div style="font-size:10px;color:#4ade80;letter-spacing:2px;font-weight:700;margin-bottom:8px">📋 TRADE PLAN</div>
      <span style="color:#4ade80;font-weight:700">BUY</span> {s['ticker']} @ <strong>${s['entryPrice']}</strong> now<br>
      Conservative: Sell <span style="color:#fbbf24;font-weight:700">day before earnings</span> → <span style="color:#4ade80">${s['targetPre']}</span> (+{up_pre}%)<br>
      Aggressive:   Hold through → <span style="color:#fbbf24">${s['targetPost']}</span> (+{up_post}%)<br>
      Stop-loss: <span style="color:#f87171;font-weight:700">${s['stopLoss']}</span> · Size: <span style="color:#38bdf8;font-weight:700">{s['suggestedSize']}</span>
    </div>""", unsafe_allow_html=True)
    st.markdown("---")

# ── Main layout ────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px">
  <div style="width:10px;height:10px;border-radius:50%;background:#4ade80;box-shadow:0 0 12px #4ade80;animation:pulse 2s infinite"></div>
  <span style="font-size:11px;color:#4ade80;letter-spacing:3px">SIGNAL SCANNER · FREE · NO AI API REQUIRED</span>
</div>
<h1 style="font-size:26px;font-weight:900;color:#e2e8f0;margin:0 0 4px 0">Theme Intelligence · Laggard Detection</h1>
<p style="color:#2a4560;font-size:12px;margin:0 0 20px 0">Finnhub news · yfinance prices · rule-based scoring · 8 themes · 60+ quality stocks · zero AI cost</p>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.markdown("## ⚙️ Settings")
finnhub_key = st.sidebar.text_input("Finnhub API Key:", type="password",
    help="Free at finnhub.io — needed for news + earnings calendar")

st.sidebar.markdown("---")
st.sidebar.markdown("**Tier Filter**")
show_t1 = st.sidebar.checkbox("🟢 Tier 1 — Blue Chip ($500)", value=True)
show_t2 = st.sidebar.checkbox("🟡 Tier 2 — Growth ($375)",    value=True)
show_t3 = st.sidebar.checkbox("🔴 Tier 3 — Dynamic ($250)",   value=False)

st.sidebar.markdown("---")
st.sidebar.markdown("**Min Impact Score**")
min_score = st.sidebar.slider("", 1, 9, 4)

st.sidebar.markdown("---")
st.sidebar.markdown("**Theme Filter**")
show_themes = {k: st.sidebar.checkbox(f"{v['icon']} {v['label']}", value=True)
               for k,v in UNIVERSE.items()}

st.sidebar.markdown("---")
st.sidebar.caption("💡 No Anthropic key needed — all analysis done with rules + math")

# ── Load prices (always) ───────────────────────────────────────────────────────
with st.spinner("Loading live prices…"):
    prices = fetch_prices(ALL_TICKERS)

# ── Leader ticker strip ────────────────────────────────────────────────────────
leaders = ["NVDA","AAPL","MSFT","GOOGL","AMZN","META","TSLA","AMD","JPM","XOM"]
cols = st.columns(len(leaders))
for i,t in enumerate(leaders):
    p = prices.get(t)
    if p:
        cols[i].metric(t, f"${p['price']}", f"{'+' if p['change']>=0 else ''}{p['change']}%")

st.markdown("---")

# ── Detect active themes immediately from price data ───────────────────────────
active_themes = detect_active_themes(prices)
if active_themes:
    st.markdown("**🔥 Active Themes (from price moves):**")
    tcols = st.columns(min(len(active_themes),4))
    for i,(k,td) in enumerate(active_themes.items()):
        m = td["avg_move"]
        c = "#4ade80" if m>0 else "#f87171"
        tcols[i%4].markdown(f"""<div style="background:{c}10;border:1px solid {c}33;border-radius:8px;padding:8px 10px;text-align:center;margin-bottom:8px">
            <div style="font-size:18px">{td['theme']['icon']}</div>
            <div style="font-size:11px;font-weight:700;color:{c}">{td['theme']['label']}</div>
            <div style="font-size:13px;color:{c};font-family:'JetBrains Mono',monospace">{'+' if m>0 else ''}{m}%</div>
        </div>""", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_signals, tab_laggards, tab_earnings, tab_news, tab_prices = st.tabs([
    "📡 SIGNALS", "⏳ LAGGARDS", "📅 EARNINGS", "📰 NEWS", "💹 PRICES"
])

# ── SIGNALS TAB ───────────────────────────────────────────────────────────────
with tab_signals:
    st.markdown("#### News-based signals — scored by rules, no AI cost")
    if not finnhub_key:
        st.warning("Add your Finnhub API key in the sidebar to fetch news signals")
    else:
        if st.button("⟳  SCAN NEWS SIGNALS", use_container_width=True):
            tickers_to_scan = list(set(
                t for k,td in active_themes.items()
                for tier in ["tier1","tier2","tier3"]
                for t in td["theme"][tier]
            ))[:12] or [t for theme in UNIVERSE.values() for t in theme["tier1"]]

            with st.spinner("Fetching Finnhub news…"):
                articles = fetch_finnhub_news(tickers_to_scan, finnhub_key)

            if not articles:
                st.info("No recent news found. Try expanding to more tickers or check your Finnhub key.")
            else:
                tiers_ok  = ([1] if show_t1 else[])+([2] if show_t2 else[])+([3] if show_t3 else[])
                themes_ok = [k for k,v in show_themes.items() if v]

                signals = []
                for art in articles:
                    sig = score_article(art, prices, active_themes)
                    if sig and sig["tier"] in tiers_ok and sig["theme"] in themes_ok and sig["impact_score"]>=min_score:
                        signals.append(sig)

                signals.sort(key=lambda x: x["impact_score"], reverse=True)
                signals = signals[:10]  # top 10

                if not signals:
                    st.info(f"No signals scored above {min_score}/10 with current filters. Lower the min score in the sidebar.")
                else:
                    st.success(f"✓ {len(signals)} signals from {len(articles)} articles — {sum(1 for s in signals if s['impact_score']>=7)} high impact")
                    for sig in signals:
                        render_signal(sig)

# ── LAGGARDS TAB ──────────────────────────────────────────────────────────────
with tab_laggards:
    st.markdown("#### Stocks lagging their theme leaders — pure price math")
    if not active_themes:
        st.info("No themes strongly active right now (leaders need >1.5% move). Check back when the market is moving.")
    else:
        laggards = find_laggards(prices, active_themes)
        tiers_ok  = ([1] if show_t1 else[])+([2] if show_t2 else[])+([3] if show_t3 else[])
        themes_ok = [k for k,v in show_themes.items() if v]
        laggards  = [l for l in laggards if l["tier"] in tiers_ok and l["theme"] in themes_ok and l["impact_score"]>=min_score]

        if not laggards:
            st.info("No laggards found with current filters. All theme stocks moving together today.")
        else:
            st.success(f"✓ {len(laggards)} laggard opportunities identified — no news needed, pure price gap analysis")
            for lag in laggards:
                render_signal(lag)

# ── EARNINGS TAB ──────────────────────────────────────────────────────────────
with tab_earnings:
    st.markdown("#### Pre-earnings setups — scored with peer data, no AI needed")
    if not finnhub_key:
        st.warning("Add your Finnhub API key in the sidebar to fetch the earnings calendar")
    else:
        if st.button("⟳  SCAN EARNINGS CALENDAR", use_container_width=True):
            with st.spinner("Fetching upcoming earnings from Finnhub…"):
                upcoming = fetch_earnings_calendar(ALL_TICKERS, finnhub_key)

            if not upcoming:
                st.info("No upcoming earnings found for watched stocks in the next 14 days.")
            else:
                st.success(f"✓ {len(upcoming)} upcoming earnings found")
                with st.spinner("Scoring setups with peer price data…"):
                    setups = score_pre_earnings(upcoming, prices, finnhub_key)

                if not setups:
                    st.info("No strong pre-earnings setups (all scored below threshold or marked AVOID).")
                else:
                    st.success(f"✓ {len(setups)} pre-earnings setups scored")
                    for s in setups:
                        render_earnings_setup(s)
        else:
            st.markdown("""<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:12px;padding:20px;font-size:13px;color:#2a4560;line-height:2.2">
                <div style="font-weight:700;color:#e2e8f0;margin-bottom:10px">How scoring works (no AI):</div>
                ✓ <strong style="color:#c8dff0">Sector read-through</strong> — are theme leaders already moving?<br>
                ✓ <strong style="color:#c8dff0">Price not moved</strong> — is the opportunity still open?<br>
                ✓ <strong style="color:#c8dff0">Volume signal</strong> — institutional interest showing?<br>
                ✓ <strong style="color:#c8dff0">Timing</strong> — 3-7 days is the ideal positioning window<br>
                ✓ <strong style="color:#c8dff0">Analyst coverage</strong> — EPS estimate = active coverage<br>
            </div>""", unsafe_allow_html=True)

# ── NEWS TAB ──────────────────────────────────────────────────────────────────
with tab_news:
    st.markdown("#### Raw Finnhub headlines — unscored, unfiltered")
    if not finnhub_key:
        st.warning("Add your Finnhub API key in the sidebar")
    else:
        news_ticker = st.selectbox("Select ticker:", ["ALL"]+sorted(ALL_TICKERS))
        if st.button("⟳  FETCH NEWS", use_container_width=True):
            tickers = ALL_TICKERS if news_ticker=="ALL" else [news_ticker]
            with st.spinner("Fetching headlines…"):
                articles = fetch_finnhub_news(tickers[:10], finnhub_key, days_back=3)

            if not articles:
                st.info("No recent news found.")
            else:
                st.success(f"✓ {len(articles)} headlines")
                for a in articles:
                    p = prices.get(a["ticker"],{})
                    chg = p.get("change",0)
                    chg_c = "#4ade80" if chg>=0 else "#f87171"
                    themes = match_article_themes(a["headline"], a.get("summary",""))
                    theme_str = " ".join(f"{UNIVERSE[t]['icon']}" for t,_ in themes[:2])

                    st.markdown(f"""<div style="background:#080f1a;border:1px solid #0e1e35;border-radius:8px;padding:12px 14px;margin-bottom:8px">
                      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
                        <div style="flex:1">
                          <div style="margin-bottom:6px">
                            {badge(a['ticker'], '#38bdf8')}
                            {badge(f"{'+' if chg>=0 else ''}{chg}%", chg_c)}
                            {f'<span style="font-size:14px">{theme_str}</span>' if theme_str else ''}
                          </div>
                          <div style="font-size:13px;font-weight:600;color:#c8dff0;line-height:1.4;margin-bottom:4px">
                            {"<a href='"+a['url']+"' target='_blank' style='color:#c8dff0;text-decoration:none'>"+a['headline']+"</a>" if a.get('url') else a['headline']}
                          </div>
                          <div style="font-size:11px;color:#2a4560">{a['source']} · {a['published']}</div>
                          {f"<div style='font-size:11px;color:#334155;margin-top:6px;line-height:1.5'>{a['summary'][:200]}…</div>" if a.get('summary') else ''}
                        </div>
                      </div>
                    </div>""", unsafe_allow_html=True)

# ── PRICES TAB ────────────────────────────────────────────────────────────────
with tab_prices:
    st.markdown("#### Live prices — all quality stocks")
    theme_filter = st.selectbox("Theme:", ["ALL"]+[f"{v['icon']} {v['label']}" for v in UNIVERSE.values()])
    tier_filter  = st.radio("Tier:", ["All","Tier 1","Tier 1+2"], horizontal=True)

    filtered = ALL_TICKERS
    if theme_filter!="ALL":
        icon = theme_filter.split(" ")[0]
        for k,v in UNIVERSE.items():
            if v["icon"]==icon:
                filtered = v["tier1"]+v["tier2"]+v["tier3"]
                break
    if tier_filter=="Tier 1":
        filtered = [t for t in filtered if get_tier(t)==1]
    elif tier_filter=="Tier 1+2":
        filtered = [t for t in filtered if get_tier(t)<=2]

    rows = []
    for t in filtered:
        p = prices.get(t)
        if p:
            tier = get_tier(t)
            tkey,tinfo = [(k,v) for k,v in UNIVERSE.items()
                          if t in v["tier1"]+v["tier2"]+v["tier3"]][0] if get_themes_for_ticker(t) else ("AI",UNIVERSE["AI"])
            rows.append({
                "Ticker": t,
                "Tier":   f"T{tier}",
                "Theme":  tinfo["icon"]+" "+tinfo["label"],
                "Price":  f"${p['price']}",
                "Change": f"{'+' if p['change']>=0 else ''}{p['change']}%",
                "Vol":    f"{p.get('vol_ratio',1.0)}x",
                "High":   f"${p.get('high',p['price'])}",
                "Low":    f"${p.get('low',p['price'])}",
            })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No price data loaded yet.")
