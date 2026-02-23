import streamlit as st
import pandas as pd
import yfinance as yf
import pandas_datareader.data as web
from datetime import datetime, timedelta

# --- 1. 페이지 및 테마 설정 ---
st.set_page_config(layout="wide", page_title="Global Macro & Liquidity Terminal", page_icon="🌊")

BG_COLOR = "#161C27"
TABLE_BG_COLOR = "#363C4C"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    .stApp {{ background-color: {BG_COLOR} !important; font-family: 'Inter', sans-serif; }}
    h1, h2, h3, h4, h5, h6, p, label, span {{ color: #ccd6f6 !important; }}
    .metric-card {{ background-color: {TABLE_BG_COLOR}; border-radius: 12px; padding: 20px; border: 1px solid #4a5161; text-align: center; height: 100%; }}
    .metric-label {{ color: #aeb9cc !important; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; margin-bottom: 5px; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 800; color: #64ffda !important; }}
    .metric-diff {{ font-size: 1rem; font-weight: 600; }}
    .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: 800; font-size: 1.2rem; margin-bottom: 20px; }}
    .risk-on {{ background-color: rgba(100, 255, 218, 0.2); color: #64ffda !important; border: 1px solid #64ffda; }}
    .risk-off {{ background-color: rgba(255, 107, 107, 0.2); color: #ff6b6b !important; border: 1px solid #ff6b6b; }}
    .neutral {{ background-color: rgba(254, 202, 87, 0.2); color: #feca57 !important; border: 1px solid #feca57; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 수집 엔진 ---
@st.cache_data(ttl=3600*12) # 12시간마다 업데이트 (매크로 지표는 변동 주기가 긺)
def get_macro_data():
    end = datetime.now()
    start = end - timedelta(days=365 * 3) # 최근 3년 데이터
    
    # 1. FRED(연준 경제 데이터) 수집
    # WALCL: 연준 총자산, M2SL: 미국 M2 통화량, BAMLC0A0CM: 하이일드 스프레드
    fred_tickers = ['WALCL', 'M2SL', 'BAMLC0A0CM']
    df_fred = web.DataReader(fred_tickers, 'fred', start, end)
    df_fred.columns = ['Fed_Assets', 'M2_Supply', 'High_Yield_Spread']
    
    # 2. Yahoo Finance 데이터 수집
    # DX-Y.NYB: 달러 인덱스, BTC-USD: 비트코인, ^GSPC: S&P 500
    yf_tickers = ['DX-Y.NYB', 'BTC-USD', '^GSPC']
    df_yf = yf.download(yf_tickers, start=start, end=end)['Close']
    df_yf.columns = ['Bitcoin', 'DXY', 'S&P500']
    
    # 데이터 병합 및 빈칸 채우기 (FRED는 주간/월간 발표이므로 ffill 적용)
    df = df_fred.join(df_yf, how='outer').ffill().dropna()
    
    # 추세 분석을 위한 50일 이동평균선 계산
    df['DXY_50MA'] = df['DXY'].rolling(window=50).mean()
    df['HY_Spread_50MA'] = df['High_Yield_Spread'].rolling(window=50).mean()
    
    return df

# --- 3. 신호 판별 로직 ---
def analyze_regime(df):
    latest = df.iloc[-1]
    
    # 달러가 약세(50MA 아래)이고, 하이일드 스프레드가 축소(50MA 아래)될 때 = 유동성 풍부
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
    st.markdown(f"<p style='color: #8892b0;'>마지막 업데이트: {latest_date}</p>", unsafe_allow_html=True)
    
    # 신호등 배지 출력
    regime_text, badge_class = analyze_regime(df)
    st.markdown(f"<div class='status-badge {badge_class}'>현재 매크로 환경: {regime_text}</div>", unsafe_allow_html=True)

    # --- 메트릭 요약 (최근 값 및 한 달 전 대비 증감) ---
    st.markdown("### 📊 핵심 유동성 지표")
    latest = df.iloc[-1]
    month_ago = df.iloc[-21] # 약 1개월(영업일 21일) 전 데이터
    
    c1, c2, c3, c4 = st.columns(4)
    
    def render_metric(col, title, current, previous, unit="", reverse_color=False):
        diff = current - previous
        diff_pct = (diff / previous) * 100
        
        # 색상 로직 (달러, 스프레드는 오르면 나쁜 것(빨강), 내리면 좋은 것(초록))
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

    # 연준 총자산 (단위: 백만 달러 -> 조 달러로 간소화 표시하면 좋지만 여기선 원본 유지)
    render_metric(c1, "연준 총자산 (Fed Assets)", latest['Fed_Assets'], month_ago['Fed_Assets'])
    # M2 통화량
    render_metric(c2, "M2 통화량", latest['M2_Supply'], month_ago['M2_Supply'])
    # 달러 인덱스 (내려야 주식에 좋음 -> reverse_color=True)
    render_metric(c3, "달러 인덱스 (DXY)", latest['DXY'], month_ago['DXY'], reverse_color=True)
    # 하이일드 스프레드 (내려야 주식에 좋음 -> reverse_color=True)
    render_metric(c4, "하이일드 스프레드", latest['High_Yield_Spread'], month_ago['High_Yield_Spread'], "%", reverse_color=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- 개별 지표 추세 차트 ---
    st.markdown("### 📈 지표별 3년 추세 (Trend)")
    chart_c1, chart_c2 = st.columns(2)
    
    with chart_c1:
        st.write("**💵 달러 인덱스 (DXY) & 50일 이평선**")
        st.line_chart(df[['DXY', 'DXY_50MA']], color=["#ff6b6b", "#8892b0"])
        
        st.write("**🏦 연준 총자산 (Fed Balance Sheet)**")
        st.line_chart(df['Fed_Assets'], color="#64ffda")

    with chart_c2:
        st.write("**🚨 하이일드 스프레드 (High Yield Spread) & 50일 이평선**")
        st.line_chart(df[['High_Yield_Spread', 'HY_Spread_50MA']], color=["#feca57", "#8892b0"])
        
        st.write("**💸 미국 M2 통화량 (M2 Money Supply)**")
        st.line_chart(df['M2_Supply'], color="#a29bfe")

    st.divider()

    # --- 유동성 프록시 자산 비교 ---
    st.markdown("### 🚀 유동성 민감 자산 흐름 (S&P 500 vs Bitcoin)")
    st.markdown("비트코인은 유동성 팽창/축소에 가장 민감하게 반응하는 선행 지표 역할을 합니다. (시작일 기준 100 정규화)")
    
    # 첫 날을 100으로 맞추어 수익률을 직관적으로 비교 (정규화)
    df_normalized = df[['S&P500', 'Bitcoin']] / df[['S&P500', 'Bitcoin']].iloc[0] * 100
    st.line_chart(df_normalized, color=["#00b894", "#fdcb6e"])

else:
    st.error("데이터를 불러오는 중 문제가 발생했습니다. FRED 또는 Yahoo Finance API 상태를 확인해 주세요.")
