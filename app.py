import streamlit as st
import yfinance as yf
import requests
from datetime import datetime

st.set_page_config(page_title="Tech Terminal", layout="wide")
st.title("📈 Tech Stock Catalyst Terminal")

# Sidebar
API_KEY = st.sidebar.text_input("Alpha Vantage API Key (Optional):", type="password")
ticker = st.sidebar.selectbox("Select Watchlist Stock:", ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA"])

# --- OPTIMIZATION: Cache API results for 15 minutes to save your daily limits ---
@st.cache_data(ttl=900)  
def fetch_alpha_vantage_news(ticker, api_key):
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&apikey={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # If Alpha Vantage throttles us, return None so we can fall back to yfinance
            if "Note" in data or "Information" in data:
                return None
            return data.get("feed", [])[:8]
    except:
        return None
    return None

if ticker:
    stock = yf.Ticker(ticker)
    
    # 1. Fundamentals Section
    try:
        info = stock.info
        current_price = info.get("currentPrice", 0)
        trailing_pe = info.get("trailingPE", "N/A")
        forward_pe = info.get("forwardPE", "N/A")
        cash_holding = info.get("totalCash", 0) / 1e9
        
        st.subheader(f"📊 {info.get('longName', ticker)} Financials")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Price", f"${current_price:,.2f}")
        col2.metric("Trailing P/E", f"{trailing_pe}")
        col3.metric("Forward P/E", f"{forward_pe}")
        col4.metric("Cash Balance", f"${cash_holding:,.1f}B")
    except Exception as e:
        st.error(f"Error loading financials: {e}")

    st.markdown("---")
    st.subheader(f"📰 Recent News Catalysts")

    # 2. News Section with Intelligent Fallback
    news_feed = None
    if API_KEY:
        news_feed = fetch_alpha_vantage_news(ticker, API_KEY)
        
    if news_feed:
        st.caption("⚡ Serving cached Alpha Vantage premium sentiment feed")
        for article in news_feed:
            time_pub = article.get("time_published", "20260101T000000")
            try:
                date_obj = datetime.strptime(time_pub, "%Y%m%dT%H%M%S")
                formatted_date = date_obj.strftime("%b %d, %Y")
            except:
                formatted_date = "Recent"
                
            ticker_sentiment = "Neutral"
            for t in article.get("ticker_sentiment", []):
                if t.get("ticker") == ticker:
                    ticker_sentiment = t.get("ticker_sentiment_label", "Neutral")

            st.markdown(f"### [{article.get('title')}]({article.get('url')})")
            st.markdown(f"⏱️ *{formatted_date}* | Sentiment: **{ticker_sentiment}**")
            st.write(article.get("summary", ""))
            st.markdown("---")
    else:
        # FALLBACK: If Alpha Vantage is rate-limited or key is missing, use completely free yfinance news
        st.caption("🔄 Alpha Vantage limit reached or key missing. Falling back to free Yahoo Finance stream.")
        yf_news = stock.news[:8]
        if yf_news:
            for article in yf_news:
                # Format yfinance news array structural items
                title = article.get('title')
                link = article.get('link')
                publisher = article.get('publisher')
                
                st.markdown(f"### [{title}]({link})")
                st.markdown(f"📢 Publisher: *{publisher}*")
                st.markdown("---")
        else:
            st.info("No news streams available right now.")
