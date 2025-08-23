import streamlit as st
import yfinance as yf
from tradingview_ta import TA_Handler, Interval

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

def render_info_section(stock, info, summary, ticker_input):
    """정보 섹션 UI를 그립니다."""
    
    # --- 3. 가격 관련 수치 ---
    st.subheader(f"{info.get('longName', ticker_input)} ({info.get('symbol', '')})")
    
    price_cols = st.columns(4)
    price_cols[0].metric("현재가", f"${info.get('currentPrice', 0):,.2f}", f"{info.get('regularMarketChange', 0):,.2f} ({info.get('regularMarketChangePercent', 0)*100:.2f}%)")
    price_cols[1].metric("시가", f"${info.get('open', 0):,.2f}")
    price_cols[2].metric("고가", f"${info.get('dayHigh', 0):,.2f}")
    price_cols[3].metric("저가", f"${info.get('dayLow', 0):,.2f}")

    st.markdown("---")

    # --- 4. 지표 세트 ---
    st.subheader("지표 세트")
    indicator_cols = st.columns(3)
    
    with indicator_cols[0]:
        st.write("**TradingView 요약**")
        
        # TradingView 요약 결과에 따라 색상 지정
        summary_text = summary.get('RECOMMENDATION', 'N/A')
        if "BUY" in summary_text:
            st.success(f"**{summary_text}**")
        elif "SELL" in summary_text:
            st.error(f"**{summary_text}**")
        else:
            st.warning(f"**{summary_text}**")
            
        st.write(f"매수: {summary.get('BUY', 0)}, 매도: {summary.get('SELL', 0)}, 중립: {summary.get('NEUTRAL', 0)}")

    with indicator_cols[1]:
        st.write("**거래 정보**")
        st.text(f"거래량: {info.get('volume', 0):,}")
        st.text(f"52주 최고가: {info.get('fiftyTwoWeekHigh', 0):,.2f}")
        st.text(f"52주 최저가: {info.get('fiftyTwoWeekLow', 0):,.2f}")

    with indicator_cols[2]:
        st.write("**주요 지표**")
        st.text(f"시가총액: {info.get('marketCap', 0):,}")
        st.text(f"PER: {info.get('trailingPE', 0):,.2f}")
        st.text(f"배당수익률: {info.get('dividendYield', 0)*100 if info.get('dividendYield') else 0:.2f}%")
        
# --- 메인 실행 로직 (테스트용) ---
if __name__ == "__main__":
    render_stock_analysis_page()