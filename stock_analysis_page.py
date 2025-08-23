import streamlit as st
import yfinance as yf
from tradingview_ta import TA_Handler, Interval
import pandas_ta as ta
import pandas as pd

def render_stock_analysis_page():
    st.title("주식 분석")

    ticker_input = st.text_input("분석할 주식의 티커를 입력하세요 (예: AAPL, GOOG, NVDA)", "AAPL").upper()

    if ticker_input:
        try:
            stock = yf.Ticker(ticker_input)
            info = stock.info
            if not info or info.get('trailingPE') is None:
                st.error(f"'{ticker_input}'에 대한 정보를 찾을 수 없습니다. 티커를 확인해주세요.")
                return

            handler = TA_Handler(symbol=ticker_input, screener="america", exchange="NASDAQ", interval=Interval.INTERVAL_1_DAY)
            summary = handler.get_analysis().summary

            selected_section = st.radio(
                "섹션 선택", ["정보", "그래프", "재무제표"],
                horizontal=True, label_visibility="collapsed"
            )

            if selected_section == "정보":
                render_info_section(stock, info, summary, ticker_input)
            elif selected_section == "그래프":
                render_graph_section(info, ticker_input) # 그래프 섹션 함수 호출
            elif selected_section == "재무제표":
                st.info("재무제표 섹션은 다음 단계에서 구현될 예정입니다.")

        except Exception as e:
            st.error(f"'{ticker_input}'에 대한 정보를 가져오는 중 오류가 발생했습니다.")

def render_graph_section(info, ticker_input):
    """TradingView 위젯을 사용해 그래프 섹션 UI를 그립니다."""
    st.subheader(f"{info.get('longName', '')} 가격 차트")

    # --- 시간 기준 선택 ---
    time_intervals = {
        "15분": "15", "30분": "30", "1시간": "60", "1일": "D",
        "1주": "W", "1달": "M"
    }
    selected_interval_label = st.selectbox(
        "시간 기준(봉) 선택:",
        time_intervals.keys(),
        index=3 
    )
    
    interval_code = time_intervals[selected_interval_label]
    tv_symbol = ticker_input

    # --- TradingView 위젯 HTML 코드 (가로세로 비율 적용) ---
    tradingview_widget_html = f"""
    <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden;">
        <div class="tradingview-widget-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
          <div id="tradingview_chart" style="height:100%;width:100%"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget(
          {{
            "autosize": true,
            "symbol": "{tv_symbol}",
            "interval": "{interval_code}",
            "timezone": "Etc/UTC",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "allow_symbol_change": true,
            "studies": [
              "bollinger@tv-basicstudies",
              "RSI@tv-basicstudies",
              {{"id": "MASimple@tv-basicstudies", "inputs": {{"length": 5}}}},
              {{"id": "MASimple@tv-basicstudies", "inputs": {{"length": 20}}}},
              {{"id": "MASimple@tv-basicstudies", "inputs": {{"length": 60}}}}
            ],
            "container_id": "tradingview_chart"
          }}
          );
          </script>
        </div>
    </div>
    """
    
    # height를 지정하지 않으면 Streamlit이 자동으로 높이를 조절합니다.
    st.components.v1.html(tradingview_widget_html, scrolling=False)
    
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
    .info-value { font-weight: 600; color: #212529; text-align: right; white-space: normal; } /* 폰트 색상 및 굵기 수정 */
    .st-emotion-cache-1r6slb0 { font-size: 1.1rem; } /* Subheader 크기 조절 */
    
    /* 지표 세트 스타일 */
    .indicator-block { 
        border-bottom: 1px solid #222; 
        padding: 8px 0; 
        margin-bottom: 8px;
    }
    .indicator-header { 
        display: flex; 
        justify-content: space-between; 
        font-weight: 600; /* 폰트 굵기 수정 */
        font-size: 1.05em;
        color: #212529; /* 폰트 색상 수정 */
    }
    .indicator-desc { 
        font-size: 0.85em; 
        color: #999999; /* 설명 텍스트 (진한 회색) */
        margin-top: 4px;
        line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)

    st.subheader(f"{info.get('longName', ticker_input)} ({info.get('symbol', '')})")

    # --- 가격 정보 ---
    st.markdown(f"""
    <div class="info-container">
        <div class="info-grid">
            <div class="info-row"><span class="info-label">현재가</span><span class="info-value">${info.get('currentPrice', 0):,.2f}</span></div>
            <div class="info-row"><span class="info-label">등락</span><span class="info-value">{info.get('regularMarketChange', 0):,.2f} ({info.get('regularMarketChangePercent', 0)*100:.2f}%)</span></div>
            <div class="info-row"><span class="info-label">고가</span><span class="info-value">${info.get('dayHigh', 0):,.2f}</span></div>
            <div class="info-row"><span class="info-label">저가</span><span class="info-value">${info.get('dayLow', 0):,.2f}</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # --- 지표 세트 ---
    st.subheader("지표 세트")
    
    hist_data = stock.history(period="1y")
    indicators = calculate_full_indicators(hist_data)
    
    st.write("**TradingView 요약**")
    summary_text = summary.get('RECOMMENDATION', 'N/A')
    st.markdown(f"**{summary_text}** (매수: {summary.get('BUY', 0)}, 중립: {summary.get('NEUTRAL', 0)}, 매도: {summary.get('SELL', 0)})")

    st.markdown('<div class="info-container" style="margin-top: 20px;">', unsafe_allow_html=True)
    
    # RSI
    st.markdown(f"""
        <div class="indicator-block">
            <div class="indicator-header"><span>RSI (14)</span><span>{indicators.get('RSI_14', 0):.2f}</span></div>
            <div class="indicator-desc">
                70 이상: 과매수 상태로, 매도 압력이 높아져 하락 전환 가능성.<br>
                30 이하: 과매도 상태로, 매수 압력이 높아져 상승 전환 가능성.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # MACD
    st.markdown(f"""
        <div class="indicator-block">
            <div class="indicator-header"><span>MACD (12, 26, 9)</span><span>{indicators.get('MACD_12_26_9', 0):.2f}</span></div>
            <div class="indicator-desc">
                MACD선이 Signal선 위로 교차(골든크로스) 시 상승 신호.<br>
                MACD선이 Signal선 아래로 교차(데드크로스) 시 하락 신호.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 볼린저 밴드
    st.markdown(f"""
        <div class="indicator-block">
            <div class="indicator-header"><span>볼린저 밴드 (20, 2)</span><span>{indicators.get('BBL_20_2.0', 0):.2f} ~ {indicators.get('BBU_20_2.0', 0):.2f}</span></div>
            <div class="indicator-desc">
                밴드 폭이 좁아지면(수축) 곧 큰 변동성 발생 가능성.<br>
                주가가 상단 밴드 터치 시 과매수, 하단 밴드 터치 시 과매도 경향.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ADX
    st.markdown(f"""
        <div class="indicator-block">
            <div class="indicator-header"><span>ADX (14)</span><span>{indicators.get('ADX_14', 0):.2f}</span></div>
            <div class="indicator-desc">
                수치가 높을수록(보통 25 이상) 현재 추세의 강도가 강함을 의미.<br>
                수치가 낮으면(보통 20 이하) 추세가 약하거나 횡보 상태.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # OBV
    st.markdown(f"""
        <div class="indicator-block">
            <div class="indicator-header"><span>OBV (On-Balance Volume)</span><span>{indicators.get('OBV', 0):,}</span></div>
            <div class="indicator-desc">
                주가와 함께 OBV가 상승하면 매집 에너지가 강함을 의미.<br>
                주가는 상승하는데 OBV가 하락하면 상승 동력이 약화됨을 시사.
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# --- 메인 실행 로직 (테스트용) ---
if __name__ == "__main__":
    render_stock_analysis_page()