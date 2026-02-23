import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_datareader.data as web
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import feedparser # [추가됨] 뉴스 RSS 파싱용 라이브러리
from email.utils import parsedate_to_datetime # 날짜 변환용

# --- 1. 페이지 및 테마 설정 ---
st.set_page_config(layout="wide", page_title="Global Macro & Liquidity Terminal", page_icon="🌊")

BG_COLOR = "#161C27"
TABLE_BG_COLOR = "#363C4C"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    .stApp {{ background-color: {BG_COLOR} !important; font-family: 'Inter', sans-serif; }}
    
    h1, h2, h3, h4, h5, h6, p, label, span, li, div {{ color: #ffffff !important; }}
    
    .metric-card {{ background-color: {TABLE_BG_COLOR}; border-radius: 12px; padding: 20px; border: 1px solid #4a5161; text-align: center; height: 100%; }}
    .metric-label {{ color: #f8f9fa !important; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 800; color: #64ffda !important; }}
    .metric-diff {{ font-size: 1rem; font-weight: 600; }}
    .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: 800; font-size: 1.2rem; margin-bottom: 20px; }}
    .risk-on {{ background-color: rgba(100, 255, 218, 0.2); color: #64ffda !important; border: 1px solid #64ffda; }}
    .risk-off {{ background-color: rgba(255, 107, 107, 0.2); color: #ff6b6b !important; border: 1px solid #ff6b6b; }}
    .neutral {{ background-color: rgba(254, 202, 87, 0.2); color: #feca57 !important; border: 1px solid #feca57; }}
    
    .info-box {{ background-color: rgba(255, 255, 255, 0.1); border-left: 4px solid #ffffff; padding: 10px 15px; border-radius: 4px; font-size: 0.9rem; margin-bottom: 15px; color: #ffffff !important; }}
    .info-box b {{ color: #64ffda !important; }}
    
    /* 뉴스 카드 스타일 */
    .news-card {{ background-color: {TABLE_BG_COLOR}; border-left: 4px solid #a29bfe; padding: 15px; border-radius: 6px; margin-bottom: 12px; transition: 0.3s; }}
    .news-card:hover {{ background-color: #4a5161; }}
    .news-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 5px; }}
    .news-title a {{ color: #ffffff !important; text-decoration: none; }}
    .news-title a:hover {{ color: #64ffda !important; }}
    .news-meta {{ font-size: 0.8rem; color: #aeb9cc !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 ---
@st.cache_data(ttl=3600*12) 
def get_macro_data():
    end = datetime.now()
    start = end - timedelta(days=365 * 3)
    
    fred_tickers = ['WALCL', 'M2SL', 'BAMLC0A0CM']
    df_fred = web.DataReader(fred_tickers, 'fred', start, end)
    df_fred.columns = ['Fed_Assets', 'M2_Supply', 'High_Yield_Spread']
    
    yf_tickers = ['DX-Y.NYB', 'BTC-USD', '^GSPC']
    df_yf = yf.download(yf_tickers, start=start, end=end)['Close']
    df_yf.columns = ['Bitcoin', 'DXY', 'S&P500']
    
    df = df_fred.join(df_yf, how='outer').ffill().dropna()
    
    df['DXY_50MA'] = df['DXY'].rolling(window=50).mean()
    df['HY_Spread_50MA'] = df['High_Yield_Spread'].rolling(window=50).mean()
    
    return df

# [새로 추가됨] 구글 뉴스 RSS 실시간 파싱 함수
@st.cache_data(ttl=3600) # 뉴스는 1시간마다 새로고침
def get_macro_news():
    # '연준 OR 금리 OR 인플레이션 OR 거시경제' 키워드로 최근 1일간의 한국어 뉴스 검색
    url = 'https://news.google.com/rss/search?q=연준+OR+금리+OR+인플레이션+OR+거시경제+when:1d&hl=ko&gl=KR&ceid=KR:ko'
    feed = feedparser.parse(url)
    news_items = []
    
    for entry in feed.entries[:8]: # 최신 뉴스 8개만 가져오기
        try:
            # 시간 포맷을 예쁘게 변경
            dt = parsedate_to_datetime(entry.published)
            time_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = entry.published
            
        news_items.append({
            'title': entry.title,
            'link': entry.link,
            'published': time_str,
            'source': entry.source.title if hasattr(entry, 'source') else "Google News"
        })
    return news_items

def get_transparent_layout():
    return dict(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#ffffff"), 
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

# --- 3. 신호 판별 로직 ---
def analyze_regime(df):
    latest = df.iloc[-1]
    dxy_bullish = latest['DXY'] < latest['DXY_50MA']
    hy_bullish = latest['High_Yield_Spread'] < latest['HY_Spread_50MA']
    
    if dxy_bullish and hy_bullish:
        return "RISK ON 🟢 (유동성 팽창: 위험자산 적극 투자)", "risk-on"
    elif not dxy_bullish and not hy_bullish:
        return "RISK OFF 🔴 (유동성 축소: 현금 비중 확대 및 보수적 접근)", "risk-off"
    else:
        return "NEUTRAL 🟡 (방향성 탐색 구간: 개별 종목 장세)", "neutral"

# --- 4. 메인 대시보드 화면 ---
st.title("🌎 Global Macro & Liquidity Terminal")

df = get_macro_data()

if not df.empty:
    latest_date = df.index[-1].strftime("%Y-%m-%d")
    st.markdown(f"<p style='color: #ffffff;'>마지막 업데이트: {latest_date}</p>", unsafe_allow_html=True)
    
    regime_text, badge_class = analyze_regime(df)
    st.markdown(f"<div class='status-badge {badge_class}'>현재 매크로 환경: {regime_text}</div>", unsafe_allow_html=True)

    # --- 메트릭 요약 ---
    st.markdown("### 📊 핵심 유동성 지표 요약")
    latest = df.iloc[-1]
    month_ago = df.iloc[-21] 
    
    c1, c2, c3, c4 = st.columns(4)
    
    def render_metric(col, title, current, previous, unit="", reverse_color=False):
        diff = current - previous
        diff_pct = (diff / previous) * 100
        
        if reverse_color:
            color = "#ff6b6b" if diff > 0 else "#64ffda"
            sign = "▲" if diff > 0 else "▼"
        else:
            color = "#64ffda" if diff > 0 else "#ff6b6b"
            sign = "▲" if diff > 0 else "▼"
            
        col.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{title}</div>
                <div class="metric-value">{current:,.2f}{unit}</div>
                <div class="metric-diff" style="color: {color};">{sign} {abs(diff):,.2f} ({diff_pct:+.2f}%) 1M</div>
            </div>
        """, unsafe_allow_html=True)

    render_metric(c1, "연준 총자산 (Fed Assets)", latest['Fed_Assets'], month_ago['Fed_Assets'])
    render_metric(c2, "M2 통화량", latest['M2_Supply'], month_ago['M2_Supply'])
    render_metric(c3, "달러 인덱스 (DXY)", latest['DXY'], month_ago['DXY'], reverse_color=True)
    render_metric(c4, "하이일드 스프레드", latest['High_Yield_Spread'], month_ago['High_Yield_Spread'], "%", reverse_color=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- 개별 지표 추세 인터랙티브 차트 ---
    st.markdown("### 📈 지표별 3년 추세 (인터랙티브 차트)")
    chart_c1, chart_c2 = st.columns(2)
    
    with chart_c1:
        st.subheader("💵 달러 인덱스 (DXY)")
        st.markdown("""<div class='info-box'><b>💡 읽는 법:</b> 전 세계 돈이 미국으로 빨려 들어가는 속도입니다. <b>하락할수록(약달러)</b> 신흥국과 주식 시장에 돈이 넘쳐나 호재입니다.</div>""", unsafe_allow_html=True)
        
        fig_dxy = px.line(df, y=['DXY', 'DXY_50MA'], color_discrete_sequence=["#ff6b6b", "#8892b0"])
        fig_dxy.update_layout(**get_transparent_layout(), xaxis_title="", yaxis_title="Index Value")
        fig_dxy.data[0].name = "달러 인덱스"
        fig_dxy.data[1].name = "50일 평균선"
        st.plotly_chart(fig_dxy, use_container_width=True)
        
        st.subheader("🏦 연준 총자산 (Fed Balance Sheet)")
        st.markdown("""<div class='info-box'><b>💡 읽는 법:</b> 미국 중앙은행이 헬리콥터로 뿌린 돈의 총량입니다. <b>우상향할수록</b> 시장에 펌프질을 하고 있다는 뜻(호재)입니다.</div>""", unsafe_allow_html=True)
        
        fig_fed = px.line(df, y='Fed_Assets', color_discrete_sequence=["#64ffda"])
        fig_fed.update_layout(**get_transparent_layout(), xaxis_title="", yaxis_title="Millions of Dollars")
        fig_fed.data[0].name = "연준 자산"
        st.plotly_chart(fig_fed, use_container_width=True)

    with chart_c2:
        st.subheader("🚨 하이일드 스프레드")
        st.markdown("""<div class='info-box'><b>💡 읽는 법:</b> 부실 기업이 돈을 빌릴 때 내야 하는 웃돈(가산금리)입니다. <b>급등하면</b> 은행이 돈줄을 죈다는 뜻으로 증시 폭락의 전조증상(악재)입니다.</div>""", unsafe_allow_html=True)
        
        fig_hy = px.line(df, y=['High_Yield_Spread', 'HY_Spread_50MA'], color_discrete_sequence=["#feca57", "#8892b0"])
        fig_hy.update_layout(**get_transparent_layout(), xaxis_title="", yaxis_title="Spread (%)")
        fig_hy.data[0].name = "스프레드"
        fig_hy.data[1].name = "50일 평균선"
        st.plotly_chart(fig_hy, use_container_width=True)
        
        st.subheader("💸 미국 M2 통화량")
        st.markdown("""<div class='info-box'><b>💡 읽는 법:</b> 내 지갑과 은행에 있는 당장 쓸 수 있는 현금의 총합입니다. <b>증가할수록</b> 주식을 살 수 있는 대기 자금이 많아진다는 뜻(호재)입니다.</div>""", unsafe_allow_html=True)
        
        fig_m2 = px.line(df, y='M2_Supply', color_discrete_sequence=["#a29bfe"])
        fig_m2.update_layout(**get_transparent_layout(), xaxis_title="", yaxis_title="Billions of Dollars")
        fig_m2.data[0].name = "M2 통화량"
        st.plotly_chart(fig_m2, use_container_width=True)

    st.divider()

    # --- 하단 레이아웃 분할: 프록시 차트 & 실시간 뉴스 ---
    col_bottom1, col_bottom2 = st.columns([1.2, 1])
    
    with col_bottom1:
        st.markdown("### 🚀 유동성 민감 자산 흐름")
        st.markdown("""<div class='info-box'><b>💡 S&P 500 vs Bitcoin:</b> 비트코인은 유동성에 가장 먼저 반응합니다. (비교를 위해 시작점을 100으로 정규화)</div>""", unsafe_allow_html=True)
        
        df_normalized = df[['S&P500', 'Bitcoin']] / df[['S&P500', 'Bitcoin']].iloc[0] * 100
        
        fig_proxy = px.line(df_normalized, y=['S&P500', 'Bitcoin'], color_discrete_sequence=["#00b894", "#fdcb6e"])
        fig_proxy.update_layout(**get_transparent_layout(), xaxis_title="", yaxis_title="Normalized Value (Base=100)")
        st.plotly_chart(fig_proxy, use_container_width=True)

    with col_bottom2:
        st.markdown("### 📰 실시간 매크로 뉴스 (최근 24시간)")
        news_data = get_macro_news()
        
        if news_data:
            for news in news_data:
                st.markdown(f"""
                <div class="news-card">
                    <div class="news-title"><a href="{news['link']}" target="_blank">{news['title']}</a></div>
                    <div class="news-meta">🕒 {news['published']} | 🗞️ {news['source']}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("현재 수집된 매크로 뉴스가 없습니다.")

else:
    st.error("데이터를 불러오는 중 문제가 발생했습니다. FRED 또는 Yahoo Finance API 상태를 확인해 주세요.")
