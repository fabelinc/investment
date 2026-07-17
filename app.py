import streamlit as st
import requests
import yfinance as yf
import anthropic
import json
import pandas as pd
from datetime import datetime, timedelta

# ── 1. GLOBAL CONFIGURATIONS (Previously Missing Dependencies) ────────────────
RISK = {
    1: {"label": "Low Risk", "target": 10, "stop": 5, "size": "$500"},
    2: {"label": "Medium Risk", "target": 20, "stop": 10, "size": "$300"},
    3: {"label": "High Risk", "target": 35, "stop": 15, "size": "$150"},
    4: {"label": "Speculative", "target": 50, "stop": 20, "size": "$100"}
}

UNIVERSE = {
    "AI_CHIPS": {"label": "AI Chips & Hardware", "icon": "⚡", "color": "#38bdf8"},
    "CLOUD": {"label": "Cloud & Infrastructure", "icon": "☁️", "color": "#a855f7"},
    "CYBER": {"label": "Cybersecurity", "icon": "🛡️", "color": "#f43f5e"},
    "BIG_TECH": {"label": "Mega Cap Tech", "icon": "🏛️", "color": "#22c55e"},
    "BIOTECH": {"label": "Biotech & Genomics", "icon": "🧬", "color": "#ec4899"},
    "DIGITAL_HEALTH": {"label": "Digital Health", "icon": "🏥", "color": "#14b8a6"},
    "FINTECH": {"label": "Fintech & Payments", "icon": "💳", "color": "#eab308"},
    "NEOBANKS": {"label": "Digital Banking", "icon": "🏦", "color": "#f97316"},
    "ECOM": {"label": "E-Commerce", "icon": "🛒", "color": "#06b6d4"},
    "STREAMING": {"label": "Entertainment & Media", "icon": "🎬", "color": "#6366f1"}
}

SECTORS = {
    "TECH": {
        "label": "Technology", "icon": "💻", "color": "#38bdf8",
        "tier1": ["NVDA", "AAPL", "MSFT"], "tier2": ["AMD", "PANW", "CRWD"], "tier3": ["PLTR", "APP"],
        "themes": {
            "AI_CHIPS": {"label": "AI Chips & Hardware", "icon": "⚡", "color": "#38bdf8", "leaders": ["NVDA", "AMD"]},
            "CLOUD": {"label": "Cloud & Infrastructure", "icon": "☁️", "color": "#a855f7", "leaders": ["MSFT"]},
            "CYBER": {"label": "Cybersecurity", "icon": "🛡️", "color": "#f43f5e", "leaders": ["PANW", "CRWD"]}
        }
    },
    "HEALTHCARE": {
        "label": "Healthcare", "icon": "💊", "color": "#ec4899",
        "tier1": ["LLY", "PFE", "MRK"], "tier2": ["REGN", "VRTX"], "tier3": ["TDOC"],
        "themes": {
            "BIOTECH": {"label": "Biotech & Genomics", "icon": "🧬", "color": "#ec4899", "leaders": ["LLY", "REGN"]},
            "DIGITAL_HEALTH": {"label": "Digital Health", "icon": "🏥", "color": "#14b8a6", "leaders": ["TDOC"]}
        }
    },
    "FINANCIALS": {
        "label": "Financials", "icon": "💳", "color": "#eab308",
        "tier1": ["V", "MA", "JPM"], "tier2": ["PYPL", "SQ"], "tier3": ["SOFI", "HOOD"],
        "themes": {
            "FINTECH": {"label": "Fintech & Payments", "icon": "💳", "color": "#eab308", "leaders": ["V", "MA"]},
            "NEOBANKS": {"label": "Digital Banking", "icon": "🏦", "color": "#f97316", "leaders": ["SOFI"]}
        }
    },
    "CONSUMER": {
        "label": "Consumer", "icon": "🛒", "color": "#06b6d4",
        "tier1": ["AMZN", "WMT"], "tier2": ["NFLX", "MELI"], "tier3": ["SHOP"],
        "themes": {
            "ECOM": {"label": "E-Commerce", "icon": "🛒", "color": "#06b6d4", "leaders": ["AMZN"]},
            "STREAMING": {"label": "Entertainment & Media", "icon": "🎬", "color": "#6366f1", "leaders": ["NFLX"]}
        }
    }
}

# Master fallback lookup generation
ALL_TICKERS_FIXED = []
SECTOR_TICKERS = {}
for s_key, s_val in SECTORS.items():
    tickers = s_val["tier1"] + s_val["tier2"] + s_val["tier3"]
    SECTOR_TICKERS[s_key] = tickers
    ALL_TICKERS_FIXED.extend(tickers)

# Helper Mappers
def get_tier(ticker):
    for s in SECTORS.values():
        if ticker in s["tier1"]: return 1
        if ticker in s["tier2"]: return 2
        if ticker in s["tier3"]: return 3
    return 4

def get_theme(ticker):
    for s in SECTORS.values():
        for t_key, t_val in s.get("themes", {}).items():
            if ticker in t_val.get("leaders", []):
                return t_key, t_val
    return "BIG_TECH", UNIVERSE["BIG_TECH"]

def get_sector(ticker):
    for s_key, s_val in SECTORS.items():
        if ticker in s_val["tier1"] + s_val["tier2"] + s_val["tier3"]:
            return s_key, s_val
    return "TECH", SECTORS["TECH"]


# ── 2. DATA PROCESSING FUNCTIONS ─────────────────────────────────────────────

def clean_json_response(raw):
    import re
    text = raw.replace("```json","").replace("```","").strip()
    obj_s, obj_e = text.find("{"), text.rfind("}")
    arr_s, arr_e = text.find("["), text.rfind("]")
    if obj_s == -1 and arr_s == -1:
        raise ValueError("No JSON found: " + text[:150])
    if obj_s != -1 and (arr_s == -1 or obj_s < arr_s):
        s, e = obj_s, obj_e
    else:
        s, e = arr_s, arr_e
    if e <= s:
        raise ValueError("Malformed JSON: " + text[:150])
    text = text[s:e+1]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    try:
        return json.loads(text)
    except:
        pass
    result = []
    in_string = False
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"' and (i == 0 or text[i-1] != '\\'):
            in_string = not in_string
            result.append(c)
        elif in_string and c == '\n':
            result.append('\\n')
        elif in_string and c == '\r':
            result.append('\\r')
        elif in_string and c == '\t':
            result.append('\\t')
        else:
            result.append(c)
        i += 1
    text = "".join(result)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except:
        pass
    sig_s = text.find('"signals"')
    if sig_s != -1:
        arr_start = text.find("[", sig_s)
        if arr_start != -1:
            last_obj = text.rfind("},")
            if last_obj > arr_start:
                candidate = text[arr_start:last_obj+1] + "]"
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                try:
                    sigs = json.loads(candidate)
                    return {"signals": sigs, "marketSummary": ""}
                except:
                    pass
    raise ValueError("JSON parse failed. Preview: " + text[:200])


def fetch_rss_news(tickers):
    import xml.etree.ElementTree as ET
    articles     = []
    seen         = set()
    ticker_set   = set(t.upper() for t in tickers)

    for ticker in tickers[:20]:
        try:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
            r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for item in root.findall(".//item")[:3]:
                    title = (item.findtext("title") or "").strip()
                    if title and title not in seen:
                        seen.add(title)
                        articles.append({
                            "ticker":    ticker,
                            "headline":  title,
                            "source":    "Yahoo Finance",
                            "url":       (item.findtext("link") or "").strip(),
                            "summary":   (item.findtext("description") or "")[:200],
                            "published": (item.findtext("pubDate") or "").strip(),
                        })
        except:
            pass

    general_feeds = [
        ("https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135", "CNBC"),
        ("https://feeds.marketwatch.com/marketwatch/realtimeheadlines/", "MarketWatch"),
    ]
    for feed_url, source in general_feeds:
        try:
            r = requests.get(feed_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                root = ET.fromstring(r.content)
                for item in root.findall(".//item")[:30]:
                    title = (item.findtext("title") or "").strip()
                    desc  = (item.findtext("description") or "")[:200]
                    if not title or title in seen:
                        continue
                    text_up  = (title + " " + desc).upper()
                    matched  = [t for t in ticker_set if t in text_up]
                    if matched:
                        seen.add(title)
                        articles.append({
                            "ticker":    matched[0],
                            "headline":  title,
                            "source":    source,
                            "url":       (item.findtext("link") or "").strip(),
                            "summary":   desc,
                            "published": (item.findtext("pubDate") or "").strip(),
                        })
        except:
            pass

    return articles[:40]


@st.cache_data(ttl=300)
def fetch_prices(tickers):
    prices = {}
    if not tickers:
        return prices
    try:
        batch = list(dict.fromkeys(tickers))
        data  = yf.download(" ".join(batch), period="5d", interval="1d", progress=False, auto_adjust=True)
        closes  = data["Close"]  if "Close"  in data.columns else data
        volumes = data["Volume"] if "Volume" in data.columns else None
        for t in batch:
            try:
                c = (closes[t] if t in closes.columns else closes).dropna()
                v = (volumes[t] if volumes is not None and t in volumes.columns else None)
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


# ── 3. DYNAMIC UNIVERSE BUILDER (Fixed Implementation) ───────────────────────

@st.cache_data(ttl=3600)
def build_dynamic_universe():
    """
    Scans candidate stocks not in the fixed universe.
    Adds any with strong 30-day momentum + volume spike.
    """
    candidates = [
        "PLTR","APP","RDDT","HOOD","COIN","MSTR","RKLB","ACHR",
        "ONTO","FORM","AMKR","COHU","ACLS","CAMT","AMBA",
        "BILL","FRSH","PCTY","PAYC","HUBS","ZI","BOX","DBX",
        "CYBR","VRNS","RPD","HIMS","RXRX","NVAX","TDOC","ACCD",
        "AFRM","SOFI","NU","OPEN","UWMC",
    ]
    
    # SOLUTION: Dynamic tracking from the existing SECTORS config map
    fixed = set()
    for s in SECTORS.values():
        for tier in ["tier1","tier2","tier3"]:
            fixed.update(s.get(tier,[]))
            
    candidates = [c for c in candidates if c not in fixed]
    momentum   = []
    try:
        data    = yf.download(" ".join(candidates), period="30d", interval="1d", progress=False, auto_adjust=True)
        closes  = data.get("Close",  pd.DataFrame())
        volumes = data.get("Volume", pd.DataFrame())
        for t in candidates:
            try:
                c = closes[t].dropna() if t in closes.columns else pd.Series()
                v = volumes[t].dropna() if t in volumes.columns else pd.Series()
                if len(c) < 10:
                    continue
                price     = float(c.iloc[-1])
                price_30d = float(c.iloc[0])
                if price < 3:
                    continue
                mom_30d   = round((price - price_30d) / price_30d * 100, 1)
                avg_vol   = float(v.iloc[:-5].mean()) if len(v) > 5 else 0
                rec_vol   = float(v.iloc[-5:].mean()) if len(v) >= 5 else 0
                vol_ratio = round(rec_vol / avg_vol, 1) if avg_vol > 0 else 1.0
                if mom_30d < 8 or vol_ratio < 1.2:
                    continue
                momentum.append({
                    "ticker":    t,
                    "price":     round(price, 2),
                    "mom_30d":   mom_30d,
                    "vol_ratio": vol_ratio,
                    "reason":    f"+{mom_30d}% in 30 days, vol {vol_ratio}x avg",
                })
            except:
                pass
    except:
        pass
    momentum.sort(key=lambda x: x["mom_30d"] * x["vol_ratio"], reverse=True)
    return momentum[:15]


# ── 4. ANALYSIS ENGINE FUNCTIONS ──────────────────────────────────────────────

def scan_sector_with_claude(sector_key, sector_data, prices, client,
                             news_articles=None, max_signals=8,
                             momentum_tickers=None):
    momentum_tickers = momentum_tickers or []
    today     = datetime.now().strftime("%B %d, %Y")
    tickers   = SECTOR_TICKERS[sector_key]
    all_scan  = list(dict.fromkeys(tickers + [m for m in momentum_tickers if get_sector(m)[0] == sector_key]))

    price_lines = [
        f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}% vol{p['vol_ratio']}x)"
        for t in sector_data["tier1"] if (p := prices.get(t))
    ]
    all_prices = [
        f"{t}=${p['price']}({'+' if p['change']>=0 else ''}{p['change']}%)"
        for t in all_scan if (p := prices.get(t))
    ]

    news_by_ticker = {}
    for a in (news_articles or []):
        tk = a["ticker"]
        if tk in set(all_scan):
            news_by_ticker.setdefault(tk, []).append(a)

    news_lines = ""
    if news_by_ticker:
        news_lines = "\nREAL NEWS HEADLINES:\n" + "\n".join(
            f"- [{tk}] {arts[0]['headline']} ({arts[0]['source']})"
            for tk, arts in list(news_by_ticker.items())[:15]
        )

    prompt = f"""You are a senior equity analyst covering {sector_data['label']}. Today is {today}.

Find the {max_signals} strongest trade signals for these {sector_data['label']} stocks.
{news_lines}

WATCHLIST: {', '.join(all_scan[:35])}

LEADER PRICES: {' | '.join(price_lines[:8])}
ALL PRICES: {' '.join(all_prices[:40])}

Rules:
- ONE signal per ticker, no duplicates
- DIRECT signals (own news catalyst) or LAGGARD (sector ripple not yet priced)
- Bullish only unless very strong bearish catalyst
- impact_score >= 6 only
- entry_price MUST match live price shown
- Keep strings short (headline<90, reasoning<100, risk<70 chars)

Return ONLY raw JSON object, start with {{ immediately:
{{
  "marketSummary": "one sentence on {sector_data['label']} today",
  "signals": [
    {{
      "ticker": "LLY",
      "tier": 1,
      "theme": "PHARMA",
      "type": "DIRECT",
      "direction": "bullish",
      "impact_score": 8,
      "headline": "real headline under 90 chars",
      "source": "Reuters",
      "reasoning": "why this moves under 100 chars",
      "entry_price": 850.00,
      "target_price": 893.00,
      "stop_loss": 824.00,
      "hold_days": 3,
      "confidence": "High",
      "risk": "specific risk under 70 chars",
      "articleUrl": null
    }}
  ]
}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = "".join(b.text for b in message.content if hasattr(b,"text")).strip()
    result = clean_json_response(raw)

    seen = set()
    enriched = []
    for sig in result.get("signals", []):
        t = sig.get("ticker","")
        if t in seen or t not in prices:
            continue
        seen.add(t)
        lp   = prices[t]
        tier = sig.get("tier") or get_tier(t)
        risk = RISK[tier]
        entry = lp["price"]
        sk, sv = get_sector(t)
        extras = [f"{a['headline']} — {a['source']}" for a in news_by_ticker.get(t, [])[1:3]]
        
        theme_key = sig.get("theme","")
        theme_info = UNIVERSE.get(theme_key, {"label": sv["label"], "icon": sv["icon"], "color": sv["color"]})
        
        enriched.append({
            **sig,
            "sector":         sector_key,
            "sectorLabel":    sv["label"],
            "sectorIcon":     sv["icon"],
            "tier":           tier,
            "themeKey":       theme_key,
            "themeLabel":     theme_info.get("label", sv["label"]),
            "themeIcon":      theme_info.get("icon",  sv["icon"]),
            "themeColor":     theme_info.get("color", sv["color"]),
            "livePrice":      entry,
            "priceChange":    lp["change"],
            "volRatio":       lp["vol_ratio"],
            "entry_price":    entry,
            "target_price":   round(entry*(1+risk["target"]/100), 2),
            "stop_loss":      round(entry*(1-risk["stop"]/100),   2),
            "suggestedSize":  risk["size"],
            "isMomentum":     t in momentum_tickers,
            "extraHeadlines": extras,
        })

    result["signals"] = sorted(enriched, key=lambda x: x["impact_score"], reverse=True)
    return result


def fetch_earnings_calendar(tickers, finnhub_key=None):
    upcoming = []
    today    = datetime.now().date()
    end_date = today + timedelta(days=14)

    if finnhub_key:
        try:
            url = f"https://finnhub.io/api/v1/calendar/earnings?from={today}&to={end_date}&token={finnhub_key}"
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
    return []


def scan_earnings_with_claude(prices, client, finnhub_key=None):
    today_dt = datetime.now()
    with_dates = fetch_earnings_calendar(ALL_TICKERS_FIXED, finnhub_key)

    if not with_dates:
        raise ValueError(f"No upcoming earnings found in the next 14 days.")

    today_str = today_dt.strftime("%B %d, %Y")
    price_ref = " ".join(f"{u['ticker']}=${prices[u['ticker']]['price']}({'+' if prices[u['ticker']]['change']>=0 else ''}{prices[u['ticker']]['change']}%)" for u in with_dates[:6] if u["ticker"] in prices)
    dates_str = " | ".join(f"{u['ticker']} on {u['earningsDate']} ({u['daysAway']}d)" + (f" EPS est ${u['epsEstimate']:.2f}" if u.get("epsEstimate") else "") for u in with_dates[:6])

    score_prompt = f"""You are a pre-earnings analyst. Today is exactly {today_str}.
These tech stocks have CONFIRMED upcoming earnings (from Finnhub calendar):
{dates_str}

Live prices today: {price_ref}
Return ONLY a raw JSON array structure starting with [ immediately."""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": score_prompt}],
    )

    raw = "".join(b.text for b in msg.content if hasattr(b, "text")).strip().replace("```json","").replace("```","").strip()
    s, e = raw.find("["), raw.rfind("]")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("Scoring returned no JSON.")

    try:
        scored = json.loads(raw[s:e+1])
    except Exception as ex:
        raise ValueError(f"JSON parse error: {ex}")

    enriched = []
    for item in scored:
        t = item.get("ticker","")
        if t not in prices:
            continue
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

    return sorted([s for s in enriched if s.get("strategy") != "AVOID"], key=lambda x: x["overallScore"], reverse=True)


def find_laggards(prices):
    laggards = []
    for sector_key, sector_data in SECTORS.items():
        for theme_key, theme in sector_data.get("themes", {}).items():
            leaders   = theme.get("leaders", [])
            all_stocks= sector_data.get("tier1", []) + sector_data.get("tier2", []) + sector_data.get("tier3", [])

            leader_moves = [prices[l]["change"] for l in leaders if l in prices]
            if not leader_moves:
                continue
            avg_move = sum(leader_moves) / len(leader_moves)
            if abs(avg_move) < 2.0:
                continue  

            for ticker in all_stocks:
                if ticker in leaders or ticker not in prices:
                    continue
                p   = prices[ticker]
                gap = avg_move - p["change"]
                if gap < 1.5:
                    continue  

                tier  = get_tier(ticker)
                risk  = RISK[tier]
                entry = p["price"]
                leader_str = ", ".join(f"{l}({prices[l]['change']:+.1f}%)" for l in leaders if l in prices)
                score = min(3 + int(gap) + (2 if p["vol_ratio"] >= 1.5 else 0), 9)

                laggards.append({
                    "ticker":       ticker,
                    "sector":       sector_key,
                    "tier":         tier,
                    "themeKey":     theme_key,
                    "themeLabel":   theme.get("label",""),
                    "themeIcon":    theme.get("icon","📈"),
                    "themeColor":   theme.get("color","#38bdf8"),
                    "type":         "LAGGARD",
                    "direction":    "bullish",
                    "impact_score": score,
                    "headline":     f"{theme['icon']} {theme['label']} leaders +{avg_move:.1f}% — {ticker} only {p['change']:+.1f}% ({gap:.1f}% gap)",
                    "source":       "Price Analysis",
                    "reasoning":    f"Leaders: {leader_str}. {ticker} lagging {gap:.1f}% — expected to catch up in 1-3 days.",
                    "risk":         f"Reversal in leaders would pull down.",
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

    seen = {}
    for l in sorted(laggards, key=lambda x: x["impact_score"], reverse=True):
        if l["ticker"] not in seen:
            seen[l["ticker"]] = l
    return sorted(seen.values(), key=lambda x: x["lag_gap"], reverse=True)


# ── 5. UI DISPLAY/RENDER HELPERS ──────────────────────────────────────────────

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
    
    extras = sig.get("extraHeadlines", [])
    extra_news_html = "".join(f'<div style="font-size:11px;color:#1e3a5f;margin-top:3px;line-height:1.4">📌 {h}</div>' for h in extras[:2]) if extras else ""

    st.markdown(f"""
<div style="background:#080f1a;border:1px solid {bord}44;border-left:3px solid {bord};border-radius:12px;padding:16px;margin-bottom:16px">
  <div style="margin-bottom:10px;flex-wrap:wrap">
    {badge(RISK[sig['tier']]['label'], tc)}
    {badge(sig['themeIcon']+' '+sig['themeLabel'], sig['themeColor'])}
    {badge('⏳ LAGGARD' if sig.get('type')=='LAGGARD' else '⚡ DIRECT', '#fbbf24' if sig.get('type')=='LAGGARD' else '#38bdf8')}
    {badge('IMPACT '+str(sig['impact_score'])+'/10', sc)}
    {badge(sig.get('confidence','Medium')+' CONF', sc)}
  </div>
  <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px">
    <div style="background:{dc}15;border:1px solid {dc}44;border-radius:8px;padding:8px 14px;text-align:center;min-width:64px;flex-shrink:0">
      <div style="font-size:18px;font-weight:900;color:{dc}">{sig['ticker']}</div>
      <div style="font-size:9px;color:{dc};letter-spacing:1px">{'BULL' if bull else 'BEAR'}</div>
    </div>
    <div style="flex:1">
      <div style="font-size:13px;font-weight:600;color:#e2e8f0;line-height:1.5;margin-bottom:5px">{sig['headline']}</div>
      <div style="font-size:11px;color:#2a4560;margin-bottom:0px">{sig.get('source','')} · {sig.get('hold_days',2)}d hold · Vol {sig.get('volRatio',1.0)}x</div>
      {extra_news_html}
    </div>
  </div>
  <div style="background:#0e1e35;border-radius:8px;padding:10px 16px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center">
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
<div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;margin:10px 0;font-size:12px;color:#475569;line-height:1.6">💡 {sig['reasoning']}</div>
<div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {sig['risk']}</div>
<div style="background:{dc}08;border:1px solid {dc}20;border-radius:8px;padding:12px 14px;margin-bottom:8px;font-size:12px;color:#e2e8f0;line-height:2;font-family:'JetBrains Mono',monospace">
  <div style="font-size:10px;color:{dc};letter-spacing:2px;font-weight:700;margin-bottom:8px">📋 TRADE INSTRUCTIONS</div>
  <span style="color:{dc};font-weight:700">{'BUY' if bull else 'SELL'}</span> {sig['ticker']} @ <strong>${sig['livePrice']}</strong><br>
  Limit sell → <span style="color:#4ade80;font-weight:700">${sig['target_price']}</span> (+{up}%)<br>
  Stop-loss  → <span style="color:#f87171;font-weight:700">${sig['stop_loss']}</span> (-{dn}%)<br>
  Hold max   → <span style="color:#fbbf24;font-weight:700">{sig.get('hold_days',2)} days</span> · Size → <span style="color:#38bdf8;font-weight:700">{sig['suggestedSize']}</span>
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
<div style="background:#080f1a;border:1px solid #fbbf2444;border-left:3px solid #fbbf24;border-radius:12px;padding:16px;margin-bottom:16px">
  <div style="margin-bottom:10px">
    {badge(RISK[s['tier']]['label'], tc)}
    {badge(s['themeIcon']+' '+s['themeLabel'], s['themeColor'])}
    {badge('📅 '+str(s['daysAway'])+'d to earnings', '#fbbf24')}
    {badge('SCORE '+str(s['overallScore'])+'/10', sc_c)}
    {badge('BEAT PROB '+str(s['beatProbability'])+'%', '#4ade80' if s['beatProbability']>=70 else '#fbbf24')}
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
    <div style="background:{tc}15;border:1px solid {tc}44;border-radius:8px;padding:8px 14px;text-align:center;min-width:64px;flex-shrink:0">
      <div style="font-size:18px;font-weight:900;color:{tc}">{s['ticker']}</div>
      <div style="font-size:9px;color:{tc};letter-spacing:1px">T{s['tier']}</div>
    </div>
    <div>
      <div style="font-size:14px;font-weight:700;color:{strat_c};margin-bottom:4px">{strat_label}</div>
      <div style="font-size:11px;color:#2a4560">Reports {s['earningsDate']} · Not priced in: <span style="color:{'#4ade80' if s['priceNotMoved'] else '#f87171'}">{'✓ YES' if s['priceNotMoved'] else '✗ NO'}</span></div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(price_box("ENTRY",         f"${s['entryPrice']}", "#e2e8f0"), unsafe_allow_html=True)
    c2.markdown(price_box("PRE-EARN TGT",  f"${s['targetPre']}",  "#4ade80"), unsafe_allow_html=True)
    c3.markdown(price_box("POST-EARN TGT", f"${s['targetPost']}", "#fbbf24"), unsafe_allow_html=True)
    c4.markdown(price_box("STOP LOSS",     f"${s['stopLoss']}",   "#f87171"), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    col1.markdown(f"""<div style="background:#4ade8008;border:1px solid #4ade8022;border-radius:8px;padding:12px;text-align:center;margin-top:8px"><div style="font-size:9px;color:#2a4560;margin-bottom:4px">CONSERVATIVE EXIT</div><div style="font-size:24px;font-weight:900;color:#4ade80">+{up_pre}%</div><div style="font-size:10px;color:#2a4560">sell day before earnings</div></div>""", unsafe_allow_html=True)
    col2.markdown(f"""<div style="background:#fbbf2408;border:1px solid #fbbf2422;border-radius:8px;padding:12px;text-align:center;margin-top:8px"><div style="font-size:9px;color:#2a4560;margin-bottom:4px">AGGRESSIVE EXIT</div><div style="font-size:24px;font-weight:900;color:#fbbf24">+{up_post}%</div><div style="font-size:10px;color:#2a4560">hold through earnings</div></div>""", unsafe_allow_html=True)

    sigs = s.get("signals", {})
    if sigs:
        with st.expander("📊 Signal Scorecard"):
            for label, sig in sigs.items():
                score = sig.get("score", 5)
                st.progress(score/10, text=f"**{label}**: {score}/10 — {sig.get('detail','')}")

    st.markdown(f"""
<div style="background:#060d1a;border-radius:7px;padding:10px 14px;border:1px solid #0e1e35;margin:10px 0;font-size:12px;color:#475569;line-height:1.6">💡 {s['reasoning']}</div>
<div style="font-size:11px;color:#1e3a5f;margin-bottom:10px">⚠ {s['risk']}</div>
<div style="background:#4ade8008;border:1px solid #4ade8020;border-radius:8px;padding:12px 14px;margin-bottom:8px;font-size:12px;color:#e2e8f0;line-height:2;font-family:'JetBrains Mono',monospace">
  <div style="font-size:10px;color:#4ade80;letter-spacing:2px;font-weight:700;margin-bottom:8px">📋 TRADE PLAN</div>
  <span style="color:#4ade80;font-weight:700">BUY</span> {s['ticker']} @ <strong>${s['entryPrice']}</strong> now<br>
  Conservative: sell before earnings → <span style="color:#4ade80">${s['targetPre']}</span> (+{up_pre}%)<br>
  Aggressive: hold through → <span style="color:#fbbf24">${s['targetPost']}</span> (+{up_post}%)<br>
  Stop-loss: <span style="color:#f87171;font-weight:700">${s['stopLoss']}</span> · Size: <span style="color:#38bdf8;font-weight:700">{s['suggestedSize']}</span>
</div>""", unsafe_allow_html=True)
    st.markdown("---")


# ── 6. APPLICATION INITIALIZATION & CORE CYCLE ────────────────────────────────

st.markdown("""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
  <div style="width:9px;height:9px;border-radius:50%;background:#4ade80;box-shadow:0 0 10px #4ade80"></div>
  <span style="font-size:11px;color:#4ade80;letter-spacing:3px">TECH SIGNAL SCANNER</span>
</div>
<h1 style="font-size:26px;font-weight:900;color:#e2e8f0;margin:0 0 4px 0">AI · Cloud · Cyber · Big Tech</h1>
<p style="color:#2a4560;font-size:12px;margin:0 0 20px 0">Live prices · Laggard detection · Pre-earnings setups · Top signals only</p>
""", unsafe_allow_html=True)

# Sidebar UI
st.sidebar.markdown("## ⚙️ Settings")

if "anthropic_key" not in st.session_state:
    try: st.session_state["anthropic_key"] = st.secrets["ANTHROPIC_API_KEY"]
    except: st.session_state["anthropic_key"] = ""

def _save_key(): st.session_state["anthropic_key"] = st.session_state["_key_input"]

typed = st.sidebar.text_input("Anthropic API Key:", value=st.session_state["anthropic_key"], type="password", key="_key_input", on_change=_save_key)
if typed: st.session_state["anthropic_key"] = typed
anthropic_key = st.session_state["anthropic_key"]

if "finnhub_key" not in st.session_state:
    try: st.session_state["finnhub_key"] = st.secrets["FINNHUB_API_KEY"]
    except: st.session_state["finnhub_key"] = ""

def _save_finnhub(): st.session_state["finnhub_key"] = st.session_state["_finnhub_input"]

typed_fh = st.sidebar.text_input("Finnhub API Key:", value=st.session_state["finnhub_key"], type="password", key="_finnhub_input", on_change=_save_finnhub)
if typed_fh: st.session_state["finnhub_key"] = typed_fh
finnhub_key = st.session_state["finnhub_key"]

max_signals = st.sidebar.slider("Max signals to show", 5, 15, 10)
min_tier = st.sidebar.radio("Min quality tier:", ["Tier 1 only","Tier 1+2","All tiers"], index=1)
tier_map = {"Tier 1 only":[1], "Tier 1+2":[1,2], "All tiers":[1,2,3]}
allowed_tiers = tier_map[min_tier]

# Build Real-Time Dynamic Universe Sequence
with st.spinner("Building dynamic universe…"):
    momentum_picks = build_dynamic_universe()
    momentum_tickers = [m["ticker"] for m in momentum_picks]
    ALL_TICKERS = list(dict.fromkeys(ALL_TICKERS_FIXED + momentum_tickers))

with st.spinner(f"Loading live prices for {len(ALL_TICKERS)} stocks…"):
    prices = fetch_prices(ALL_TICKERS)

laggards = [l for l in find_laggards(prices) if l["tier"] in allowed_tiers]

# Top Ribbon Theme Metric Engine
active_themes = {}
for tk, tv in UNIVERSE.items():
    moves = [prices[l]["change"] for l in tv.get("tier1", []) if l in prices]
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
        tcols[i%4].markdown(f'<div style="background:{c}10;border:1px solid {c}33;border-radius:8px;padding:8px;text-align:center;margin-bottom:8px"><div style="font-size:16px">{td["theme"]["icon"]}</div><div style="font-size:11px;font-weight:700;color:{c}">{td["theme"]["label"]}</div><div style="font-size:12px;color:{c}">{m:+.1f}%</div></div>', unsafe_allow_html=True)

# ── 7. APPLICATION LAYOUT TABS ───────────────────────────────────────────────

tab_tech, tab_health, tab_fin, tab_consumer, tab_lag, tab_earn, tab_universe = st.tabs([
    "💻 TECH", "💊 HEALTH", "💳 FINANCE", "🛒 CONSUMER", f"⏳ LAGGARDS ({len(laggards)})", "📅 EARNINGS", f"🌐 UNIVERSE ({len(ALL_TICKERS)})"
])

sector_tabs = {"TECH": tab_tech, "HEALTHCARE": tab_health, "FINANCIALS": tab_fin, "CONSUMER": tab_consumer}

for sector_key, tab in sector_tabs.items():
    sector_data = SECTORS[sector_key]
    with tab:
        col_info, col_btn = st.columns([3,1])
        with col_info:
            sector_tickers_list = SECTOR_TICKERS[sector_key]
            active = []
            for theme_key, theme in sector_data.get("themes",{}).items():
                moves = [prices[l]["change"] for l in theme.get("leaders",[]) if l in prices]
                if moves:
                    avg = sum(moves)/len(moves)
                    if abs(avg) >= 1.0:
                        c = "#4ade80" if avg>0 else "#f87171"
                        active.append(f'<span style="font-size:11px;padding:2px 8px;border-radius:12px;background:{c}18;border:1px solid {c}44;color:{c};margin-right:6px">{theme["icon"]} {theme["label"]} {avg:+.1f}%</span>')
            if active: st.markdown("**Active:** " + " ".join(active), unsafe_allow_html=True)
            else: st.markdown(f"<span style='color:#2a4560;font-size:12px'>Watching {len(sector_tickers_list)} {sector_data['label']} stocks</span>", unsafe_allow_html=True)

        with col_btn:
            scan_btn = st.button(f"⟳ SCAN", key=f"scan_{sector_key}", use_container_width=True)

        if not anthropic_key:
            st.warning("Add Anthropic API key in sidebar")
        elif scan_btn:
            with st.spinner(f"Fetching {sector_data['label']} news…"):
                sector_news = fetch_rss_news(sector_tickers_list)
            with st.spinner(f"Claude scoring {sector_data['label']} signals…"):
                try:
                    client = anthropic.Anthropic(api_key=anthropic_key)
                    result = scan_sector_with_claude(sector_key, sector_data, prices, client, sector_news, max_signals, momentum_tickers)
                    if result.get("marketSummary"): st.info(f"📊 {result['marketSummary']}")
                    signals = result.get("signals", [])
                    if not signals: st.info(f"No strong signals in {sector_data['label']} right now.")
                    else:
                        for sig in signals: render_signal(sig)
                except Exception as ex: st.error(f"Scan failed: {ex}")
        else:
            st.markdown("---")
            rows = [{"Ticker": t, "Tier": f"T{get_tier(t)}", "Price": f"${prices.get(t,{}).get('price','—')}", "Change": f"{prices.get(t,{}).get('change',0):+.2f}%", "Vol": f"{prices.get(t,{}).get('vol_ratio','—')}x"} for t in sector_tickers_list if t in prices]
            if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=300)

with tab_lag:
    st.markdown("#### ⏳ Laggards — stocks lagging their sector leaders")
    if not laggards: st.info("No laggards right now — sector leaders need >2% move to trigger detection.")
    else:
        by_sector = {}
        for l in laggards[:max_signals]: by_sector.setdefault(l.get("sector"), []).append(l)
        for sk, lags in by_sector.items():
            st.markdown(f"**{SECTORS.get(sk, {}).get('icon','')} {SECTORS.get(sk, {}).get('label',sk)}**")
            for lag in lags: render_signal(lag)

with tab_earn:
    st.markdown("#### 📅 Pre-Earnings Setups")
    if not anthropic_key or not finnhub_key: st.warning("Add Anthropic and Finnhub API keys in sidebar")
    else:
        if st.button("⟳  SCAN EARNINGS CALENDAR", use_container_width=True):
            with st.spinner("Fetching real earnings dates from Finnhub…"):
                try:
                    client  = anthropic.Anthropic(api_key=anthropic_key)
                    setups  = scan_earnings_with_claude(prices, client, finnhub_key)
                    if not setups: st.info("No upcoming earnings found.")
                    else:
                        by_sector_e = {}
                        for s in setups: by_sector_e.setdefault(get_sector(s["ticker"])[0], []).append(s)
                        for sk, items in by_sector_e.items():
                            st.markdown(f"**{SECTORS.get(sk,{}).get('icon','')} {SECTORS.get(sk,{}).get('label',sk)}**")
                            for item in items: render_earnings_setup(item)
                except Exception as ex: st.error(f"Earnings scan failed: {ex}")

with tab_universe:
    st.markdown("#### 🌐 Stock Universe — All Sectors")
    for sector_key, sector_data in SECTORS.items():
        with st.expander(f"{sector_data['icon']} {sector_data['label']}", expanded=False):
            rows = [{"Ticker": t, "Tier": f"T{get_tier(t)}", "Price": f"${prices.get(t,{}).get('price','—')}", "Change": f"{prices.get(t,{}).get('change',0):+.2f}%", "Vol": f"{prices.get(t,{}).get('vol_ratio','—')}x"} for t in SECTOR_TICKERS[sector_key]]
            if rows: st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
