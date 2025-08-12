import streamlit as st
import ccxt
import pandas as pd
import pandas_ta as ta
import json
from openai import OpenAI
from ask_ai_crypto_prompt import ASK_AI_CRYPTO_PROMPT

# --- 설정 ---
client = OpenAI()
exchange = ccxt.binance({'options': {'defaultType': 'future'}})

# --- 백엔드 함수 ---
@st.cache_data(ttl=60)
def check_symbol_exists(symbol):
    try:
        exchange.load_markets()
        if symbol in exchange.markets:
            return True
    except Exception:
        return False
    return False

@st.cache_data(ttl=60)
def fetch_all_data(symbol):
    data = {}
    # 1. Ticker, 24h Stats
    ticker = exchange.fetch_ticker(symbol)
    data['ticker'] = {
        'price': ticker['last'],
        'change_24h': ticker['percentage'],
        'high_24h': ticker['high'],
        'low_24h': ticker['low'],
        'volume_24h': ticker['baseVolume']
    }
    # 2. Order Book
    order_book = exchange.fetch_order_book(symbol, limit=5)
    data['order_book'] = {'bids': order_book['bids'], 'asks': order_book['asks']}
    # 3. Recent Trades
    recent_trades = exchange.fetch_trades(symbol, limit=5)
    data['recent_trades'] = [{'price': t['price'], 'amount': t['amount'], 'side': t['side']} for t in recent_trades]
    # 4. Candlestick Data
    timeframes = ['30m', '1h', '4h', '6h', '12h', '1d', '1w']
    kline_data = {}
    for tf in timeframes:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=50)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        kline_data[tf] = df
    data['klines'] = kline_data
    return data

def calculate_indicators(kline_df):
    df = kline_df.copy()
    df.ta.rsi(length=14, append=True)
    df.ta.macd(fast=12, slow=26, signal=9, append=True)
    df.ta.bbands(length=20, std=2, append=True)
    return df[['RSI_14', 'MACD_12_26_9', 'MACDh_12_26_9', 'MACDs_12_26_9', 'BBL_20_2.0', 'BBM_20_2.0', 'BBU_20_2.0']].tail(1).to_dict(orient='records')[0]

def get_ai_advice(data):
    daily_klines = data['klines']['1d']
    indicators = calculate_indicators(daily_klines)
    
    # 데이터 요약
    prompt_data = {
        "ticker": data['ticker'],
        "order_book": data['order_book'],
        "recent_trades": data['recent_trades'],
        "klines_summary": {tf: df.tail(5).to_dict(orient='records') for tf, df in data['klines'].items()},
        "indicators": indicators
    }
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": ASK_AI_CRYPTO_PROMPT},
            {"role": "user", "content": json.dumps(prompt_data, indent=2)}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- UI 렌더링 함수 ---
def render_ask_ai_page():
    st.title("🙋 AI에게 물어보기")
    
    symbol_input = st.text_input("코인 심볼을 입력하세요 (예: BTC/USDT)", "BTC/USDT").upper()

    if st.button("분석 요청", type="primary"):
        if not check_symbol_exists(symbol_input):
            st.error(f"{symbol_input}은(는) 바이낸스 선물 시장에 존재하지 않는 심볼입니다.")
        else:
            with st.spinner(f"{symbol_input}의 데이터를 수집하고 AI가 분석하는 중입니다..."):
                try:
                    market_data = fetch_all_data(symbol_input)
                    ai_advice = get_ai_advice(market_data)
                    
                    st.subheader("🤖 AI 트레이딩 계획")
                    st.markdown(f"**시장 활성도:** {ai_advice.get('market_activity', 'N/A')}")
                    
                    cols = st.columns(4)
                    cols[0].metric("진입가", ai_advice.get('entry_price', 'N/A'))
                    cols[1].metric("예산", ai_advice.get('budget', 'N/A'))
                    cols[2].metric("레버리지", ai_advice.get('leverage', 'N/A'))
                    cols[3].metric("TP / SL", ai_advice.get('tp_sl', 'N/A'))
                    
                    with st.expander("분석 근거 보기"):
                        st.write(ai_advice.get('reasoning', 'No reasoning provided.'))

                except Exception as e:
                    st.error(f"분석 중 오류가 발생했습니다: {e}")

    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()