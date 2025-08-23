import streamlit as st
import yfinance as yf
from tradingview_ta import TA_Handler, Interval
import pandas_ta as ta
import pandas as pd

def render_stock_analysis_page():
    st.title("📈 주식 분석")

    # --- 1. 주식 티커 검색 ---
    ticker_input = st.text_input("분석할 주식의 티커를 입력하세요 (예: AAPL, GOOG, NVDA)", "AAPL").upper()

    if ticker_input:
        try:
            # --- 2. 기본 정보 및 기술적 분석 요약 ---
            stock = yf.Ticker(ticker_input)
            info = stock.info
            
            # TradingView 기술적 분석 요약 가져오기
            handler = TA_Handler(symbol=ticker_input, screener="america", exchange="NASDAQ", interval=Interval.INTERVAL_1_DAY)
            summary = handler.get_analysis().summary

            # --- UI 섹션 바 ---
            selected_section = st.radio(
                "섹션 선택",
                ["정보", "그래프", "재무제표"],
                horizontal=True,
                label_visibility="collapsed"
            )

            if selected_section == "정보":
                render_info_section(stock, info, summary, ticker_input)

            elif selected_section == "그래프":
                st.info("그래프 섹션은 다음 단계에서 구현될 예정입니다.")
                
            elif selected_section == "재무제표":
                st.info("재무제표 섹션은 다음 단계에서 구현될 예정입니다.")

        except Exception as e:
            st.error(f"'{ticker_input}'에 대한 정보를 가져오는 중 오류가 발생했습니다. 티커가 올바른지 확인해주세요. (오류: {e})")

def calculate_full_indicators(stock_data):
    """pandas-ta를 사용해 모든 기술적 지표를 계산합니다."""
    df = stock_data.copy()
    
    # 기본 지표 추가
    df.ta.sma(length=20, append=True)
    df.ta.ema(length=20, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    
    # 고급 지표 추가
    df.ta.adx(length=14, append=True)
    df.ta.obv(append=True)
    df.ta.willr(length=14, append=True)
    df.ta.mom(length=10, append=True)
    
    # 일목균형표 추가
    ichimoku_df = df.ta.ichimoku(append=True)
    
    # 마지막 행(가장 최신 데이터)만 반환
    return df.iloc[-1]

def render_info_section(stock, info, summary, ticker_input):
    """정보 섹션 UI를 그립니다."""
    
    # --- 스타일 정의 ---
    st.markdown("""
    <style>
    .info-container { font-size: 0.9em; }
    .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px 15px; margin-bottom: 20px; }
    .info-row { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #222; padding: 4px 0; }
    .info-label { color: #888; }
    .info-value { font-weight: 500; color: #DCDCDC; text-align: right; white-space: normal; }
    .st-emotion-cache-1r6slb0 { font-size: 1.1rem; } /* Subheader 크기 조절 */
    .indicator-desc { font-size: 0.8em; color: #666; margin-left: 8px; }
    </style>
    """, unsafe_allow_html=True)

    st.subheader(f"{info.get('longName', ticker_input)} ({info.get('symbol', '')})")
    
    # --- 가격 정보 (2x2 그리드) ---
    st.markdown(f"""
    <div class="info-container">
        <div class="info-grid">
            <div class="info-row">
                <span class="info-label">현재가</span>
                <span class="info-value">${info.get('currentPrice', 0):,.2f}</span>
            </div>
            <div class="info-row">
                <span class="info-label">등락</span>
                <span class="info-value">{info.get('regularMarketChange', 0):,.2f} ({info.get('regularMarketChangePercent', 0)*100:.2f}%)</span>
            </div>
            <div class="info-row">
                <span class="info-label">고가</span>
                <span class="info-value">${info.get('dayHigh', 0):,.2f}</span>
            </div>
            <div class="info-row">
                <span class="info-label">저가</span>
                <span class="info-value">${info.get('dayLow', 0):,.2f}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # --- 지표 세트 ---
    st.subheader("지표 세트")
    
    hist_data = stock.history(period="1y") # 1년치 데이터로 지표 계산
    indicators = calculate_full_indicators(hist_data)
    
    st.write("**TradingView 요약**")
    summary_text = summary.get('RECOMMENDATION', 'N/A')
    st.markdown(f"**{summary_text}** (매수: {summary.get('BUY', 0)}, 중립: {summary.get('NEUTRAL', 0)}, 매도: {summary.get('SELL', 0)})")

    st.markdown('<div class="info-container" style="margin-top: 20px;">', unsafe_allow_html=True)
    
    # 각 지표를 설명과 함께 표시
    st.markdown(f"""
        <div class="info-row">
            <span class="info-label">단순이동평균 (SMA 20)</span>
            <span class="info-value">{indicators.get('SMA_20', 0):,.2f} <span class="indicator-desc"> (추세 확인)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">지수이동평균 (EMA 20)</span>
            <span class="info-value">{indicators.get('EMA_20', 0):,.2f} <span class="indicator-desc"> (최근 가격 가중)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">RSI (14)</span>
            <span class="info-value">{indicators.get('RSI_14', 0):,.2f} <span class="indicator-desc"> (과매수/과매도)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">MACD Level</span>
            <span class="info-value">{indicators.get('MACD_12_26_9', 0):,.2f} <span class="indicator-desc"> (추세 강도/방향)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">볼린저 밴드 (20, 2)</span>
            <span class="info-value">{indicators.get('BBL_20_2.0', 0):,.2f} ~ {indicators.get('BBU_20_2.0', 0):,.2f} <span class="indicator-desc"> (변동성)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">ADX (14)</span>
            <span class="info-value">{indicators.get('ADX_14', 0):,.2f} <span class="indicator-desc"> (추세 강도)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">OBV (On-Balance Volume)</span>
            <span class="info-value">{indicators.get('OBV', 0):,} <span class="indicator-desc"> (거래량 동력)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">Williams %R (14)</span>
            <span class="info-value">{indicators.get('WILLR_14', 0):,.2f} <span class="indicator-desc"> (과매수/과매도)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">모멘텀 (10)</span>
            <span class="info-value">{indicators.get('MOM_10', 0):,.2f} <span class="indicator-desc"> (가격 변화 속도)</span></span>
        </div>
        <div class="info-row">
            <span class="info-label">일목균형표 (전환/기준)</span>
            <span class="info-value">{indicators.get('ITS_9', 0):,.2f} / {indicators.get('IKS_26', 0):,.2f} <span class="indicator-desc"> (추세/지지/저항)</span></span>
        </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


# --- 메인 실행 로직 (테스트용) ---
if __name__ == "__main__":
    render_stock_analysis_page()