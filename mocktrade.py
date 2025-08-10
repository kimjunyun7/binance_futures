# mocktrade.py
"""
AI 비트코인 모의 트레이딩 봇
--------------------------------------------------------
기능:
- 바이낸스 실시간 가격 데이터 수집
- 모의 계좌 및 거래 기록 관리 (SQLite)
- 분리된 프롬프트 파일 사용
- AI 기반 거래 결정 (포지션, 레버리지, SL/TP)
- 실제 주문 없이 거래 시뮬레이션 및 성과 기록
--------------------------------------------------------
"""
# ===== 필요한 라이브러리 임포트 =====
import ccxt
import os
import math
import time
import pandas as pd
import requests
import json
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI
from datetime import datetime, timedelta # timedelta 추가
from prompts import SYSTEM_PROMPT_UPDATE # 수정용 프롬프트 추가

ACTIVE_PROMPT_FILE = "/home/ubuntu/binance_futures/active_prompt.txt"


# ===== 설정 및 초기화 =====
load_dotenv()

# Binance API (Public data only)
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    }
})

symbol = "BTC/USDT"

# OpenAI API
client = OpenAI()

# SERP API (Optional)
# serp_api_key = os.getenv("SERP_API_KEY")

# Mock Database
DB_FILE = "mock_trading.db"
INITIAL_BUDGET = 10000.0  # 모의 투자 초기 자본 (USDT)

# ===== 데이터베이스 관련 함수 =====
def setup_database():
    """
    모의 투자 데이터베이스 및 테이블 생성
    - mock_wallet: 가상 지갑 정보 (잔고)
    - mock_trades: 가상 거래 기록
    - mock_ai_analysis: AI 분석 결과
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 가상 지갑 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mock_wallet (
        id INTEGER PRIMARY KEY,
        usdt_balance REAL NOT NULL
    )''')

    # 초기 자본이 없는 경우 삽입
    cursor.execute("SELECT count(*) FROM mock_wallet")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO mock_wallet (id, usdt_balance) VALUES (?, ?)", (1, INITIAL_BUDGET))
        print(f"가상 지갑 생성. 초기 자본: ${INITIAL_BUDGET:,.2f} USDT")

    # 가상 거래 기록 테이블 (autotrade.py와 유사)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mock_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        entry_price REAL NOT NULL,
        amount REAL NOT NULL,
        leverage INTEGER NOT NULL,
        sl_price REAL NOT NULL,
        tp_price REAL NOT NULL,
        status TEXT DEFAULT 'OPEN',
        exit_price REAL,
        exit_timestamp TEXT,
        profit_loss REAL
    )''')

    # AI 분석 결과 테이블 (autotrade.py와 유사)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mock_ai_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        current_price REAL NOT NULL,
        direction TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        trade_id INTEGER,
        FOREIGN KEY (trade_id) REFERENCES mock_trades (id)
    )''')

    # AI의 현 포지션 조정 기록 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trade_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        action TEXT NOT NULL,
        new_tp_price REAL,
        new_sl_price REAL,
        reasoning TEXT,
        FOREIGN KEY (trade_id) REFERENCES mock_trades (id)
    )
    ''')

    conn.commit()
    conn.close()
    print("모의 투자 데이터베이스 설정 완료.")

def get_wallet_balance():
    """가상 지갑의 현재 USDT 잔고를 가져옵니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT usdt_balance FROM mock_wallet WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def update_wallet_balance(new_balance):
    """가상 지갑의 잔고를 업데이트합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE mock_wallet SET usdt_balance = ? WHERE id = 1", (new_balance,))
    conn.commit()
    conn.close()

def save_ai_analysis(analysis_data, trade_id=None):
    """AI 분석 결과를 DB에 저장합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO mock_ai_analysis (timestamp, current_price, direction, reasoning, trade_id) 
    VALUES (?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        analysis_data['current_price'],
        analysis_data['direction'],
        analysis_data['reasoning'],
        trade_id
    ))
    analysis_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return analysis_id

def save_mock_trade(trade_data):
    """가상 거래 정보를 DB에 저장합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO mock_trades (timestamp, action, entry_price, amount, leverage, sl_price, tp_price) 
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        datetime.now().isoformat(),
        trade_data['action'],
        trade_data['entry_price'],
        trade_data['amount'],
        trade_data['leverage'],
        trade_data['sl_price'],
        trade_data['tp_price']
    ))
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def get_open_trade():
    """현재 열려있는 가상 거래 정보를 가져옵니다."""
    conn = sqlite3.connect(DB_FILE)
    # 결과를 dict 형태로 받기 위해 row_factory 설정
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mock_trades WHERE status = 'OPEN' ORDER BY timestamp DESC LIMIT 1")
    trade = cursor.fetchone()
    conn.close()
    return dict(trade) if trade else None

# mocktrade.py의 close_mock_trade 함수

def close_mock_trade(trade_id, exit_price):
    """가상 거래를 종료하고 손익을 계산하여 DB를 업데이트합니다."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM mock_trades WHERE id = ?", (trade_id,))
    trade = cursor.fetchone()
    if not trade:
        conn.close()
        return

    # 실제 투자 원금(margin) 계산
    investment_margin = (trade['entry_price'] * trade['amount']) / trade['leverage']

    # 손익(PNL) 계산
    if trade['action'] == 'long':
        profit_loss = (exit_price - trade['entry_price']) * trade['amount']
    else:  # short
        profit_loss = (trade['entry_price'] - exit_price) * trade['amount']
    
    # DB 업데이트
    cursor.execute('''
    UPDATE mock_trades
    SET status = 'CLOSED', exit_price = ?, exit_timestamp = ?, profit_loss = ?
    WHERE id = ?
    ''', (exit_price, datetime.now().isoformat(), profit_loss, trade_id))
    
    conn.commit()
    conn.close()

    # 지갑 잔고 업데이트
    current_balance = get_wallet_balance()
    new_balance = current_balance + profit_loss
    update_wallet_balance(new_balance)
    
    # 결과 출력
    pnl_percentage = (profit_loss / investment_margin) * 100 if investment_margin > 0 else 0
    print(f"\n{'='*10} MOCK POSITION CLOSED {'='*10}")
    print(f"Trade ID: {trade['id']} ({trade['action'].upper()})")
    print(f"Entry: ${trade['entry_price']:,.2f} | Exit: ${exit_price:,.2f}")
    print(f"P/L: ${profit_loss:,.2f} ({pnl_percentage:.2f}%)")
    print(f"Wallet Balance: ${new_balance:,.2f}")
    print("="*42)


def get_historical_trading_data(limit=10):
    """과거 거래 및 AI 분석 결과를 가져옵니다."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
    SELECT t.*, a.reasoning 
    FROM mock_trades t
    LEFT JOIN mock_ai_analysis a ON t.id = a.trade_id
    WHERE t.status = 'CLOSED' 
    ORDER BY t.timestamp DESC 
    LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ===== 데이터 수집 함수 (autotrade.py와 동일) =====
def fetch_multi_timeframe_data():
    timeframes = {"15m": 96, "1h": 48, "4h": 30}
    multi_tf_data = {}
    for tf, limit in timeframes.items():
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            multi_tf_data[tf] = df
        except Exception as e:
            print(f"Error fetching {tf} data: {e}")
    return multi_tf_data


def update_trade_exit_points(trade_id, new_tp, new_sl):
    """기존 거래의 TP/SL 가격을 업데이트합니다."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE mock_trades SET tp_price = ?, sl_price = ? WHERE id = ?", (new_tp, new_sl, trade_id))
    conn.commit()
    conn.close()


def fetch_bitcoin_news():
    # if not serp_api_key:
    #     return []
    # try:
    #     url = "https://serpapi.com/search.json"
    #     params = {"engine": "google_news", "q": "bitcoin", "gl": "us", "hl": "en", "api_key": serp_api_key}
    #     response = requests.get(url, params=params)
    #     if response.status_code == 200:
    #         news_results = response.json().get("news_results", [])
    #         return [{"title": n.get("title", ""), "date": n.get("date", "")} for n in news_results[:10]]
    #     else:
    #         return []
    # except Exception as e:
    #     print(f"Error fetching news: {e}")
    #     return []

    """
    Serper API를 사용해 비트코인 관련 최신 뉴스를 가져옵니다.
    """
    # .env 파일에서 Serper API 키를 가져옵니다.
    # .env 파일에 SERPER_API_KEY="your_key" 형태로 저장해두세요.
    serper_api_key = os.getenv("SERPER_API_KEY")

    if not serper_api_key:
        print("SERPER_API_KEY가 .env 파일에 설정되지 않았습니다.")
        return []

    # 1. API URL이 변경되었습니다.
    url = "https://google.serper.dev/news"

    # 2. 파라미터는 JSON 형태로 구성합니다.
    payload = json.dumps({
        "q": "bitcoin", # 검색어
        "gl": "us",     # 국가
        "hl": "en",      # 언어
        "num": 10        # 뉴스 개수
    })

    # 3. API 키는 헤더(headers)에 추가됩니다.
    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    try:
        # 4. POST 방식으로 요청을 보냅니다.
        response = requests.post(url, headers=headers, data=payload)
        response.raise_for_status() # 오류가 발생하면 예외를 발생시킴

        data = response.json()
        news_results = data.get("news", []) # 결과는 'news' 키 안에 들어있습니다.

        # print(f"Serper API로 {len(news_results)}개의 뉴스를 가져왔습니다.")
        return news_results

    except requests.exceptions.RequestException as e:
        print(f"Serper API 요청 중 오류가 발생했습니다: {e}")
        return []

# ===== 메인 모의 트레이딩 루프 =====
def main():
    print("\n" + "="*15 + " MOCK TRADING BOT STARTED " + "="*15)
    setup_database()

    # 포지션 진입 후 재분석을 위한 시간 추적 변수
    last_in_position_analysis = None

    while True:
        try:
            current_price = exchange.fetch_ticker(symbol)['last']
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Current BTC Price: ${current_price:,.2f}")

            open_trade = get_open_trade()

            # --- 1. 포지션이 있는 경우: SL/TP 확인 ---
            if open_trade:
                print(f"Monitoring OPEN position: {open_trade['action'].upper()} | Entry: ${open_trade['entry_price']:,.2f} | SL: ${open_trade['sl_price']:,.2f} | TP: ${open_trade['tp_price']:,.2f}")
                
                is_closed = False
                # --- A. 기본적인 SL/TP 확인 ---
                # 롱 포지션의 손절/익절 확인
                if open_trade['action'] == 'long':
                    if current_price <= open_trade['sl_price']:
                        print(f"Stop Loss triggered for LONG position at ${current_price:,.2f}")
                        close_mock_trade(open_trade['id'], open_trade['sl_price'])
                        is_closed = True
                    elif current_price >= open_trade['tp_price']:
                        print(f"Take Profit triggered for LONG position at ${current_price:,.2f}")
                        close_mock_trade(open_trade['id'], open_trade['tp_price'])
                        is_closed = True
                
                # 숏 포지션의 손절/익절 확인
                elif open_trade['action'] == 'short':
                    if current_price >= open_trade['sl_price']:
                        print(f"Stop Loss triggered for SHORT position at ${current_price:,.2f}")
                        close_mock_trade(open_trade['id'], open_trade['sl_price'])
                        is_closed = True
                    elif current_price <= open_trade['tp_price']:
                        print(f"Take Profit triggered for SHORT position at ${current_price:,.2f}")
                        close_mock_trade(open_trade['id'], open_trade['tp_price'])
                        is_closed = True
                
                # --- B. 10분마다 재분석하여 TP/SL 업데이트 ---
                # 10분 간격 설정 (timedelta(minutes=10))
                re_analysis_interval = timedelta(minutes=0.3) 
                
                
                if not is_closed and (last_in_position_analysis is None or (datetime.now() - last_in_position_analysis) > re_analysis_interval):
                    print("\n" + "="*10 + " Performing In-Position Re-Analysis " + "="*10)
                    
                    margin = (open_trade['entry_price'] * open_trade['amount']) / open_trade['leverage']
                    pnl = (current_price - open_trade['entry_price']) * open_trade['amount'] if open_trade['action'] == 'long' else (open_trade['entry_price'] - current_price) * open_trade['amount']
                    pnl_percent = (pnl / margin) * 100 if margin > 0 else 0
                    
                    market_data = fetch_multi_timeframe_data()
                    news_data = fetch_bitcoin_news()
                    
                    prompt_for_update = SYSTEM_PROMPT_UPDATE.format(
                        side=open_trade['action'].upper(),
                        entry_price=open_trade['entry_price'],
                        current_price=current_price,
                        pnl_percentage=f"{pnl_percent:.2f}"
                    )
                    
                    analysis_input_update = { "timeframes": {}, "recent_news": news_data }
                    if market_data:
                        for tf, df in market_data.items():
                            analysis_input_update["timeframes"][tf] = df.to_dict(orient="records")

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": prompt_for_update},
                            {"role": "user", "content": json.dumps(analysis_input_update)}
                        ],
                        response_format={"type": "json_object"}
                    )
                    
                    # .strip() 추가하여 JSON 파싱 오류 방지
                    response_content = response.choices[0].message.content.strip()
                    decision = json.loads(response_content)
                    ai_action = decision.get('action', 'HOLD')
                    
                    print(f"AI Re-Analysis Decision: {ai_action} | Reason: {decision.get('reasoning')}")


                    # AI 판단 기록을 DB에 저장
                    if ai_action == "CLOSE" or ai_action == "ADJUST":
                        new_tp_price_val = decision.get('new_tp_percentage')
                        new_sl_price_val = decision.get('new_sl_percentage')

                        # new_tp_price와 new_sl_price 계산 (ADJUST 시에만)
                        if ai_action == "ADJUST" and new_tp_price_val is not None and new_sl_price_val is not None:
                            if open_trade['action'] == 'long':
                                new_tp_price = current_price * (1 + float(new_tp_price_val))
                                new_sl_price = current_price * (1 - float(new_sl_price_val))
                            else: # short
                                new_tp_price = current_price * (1 - float(new_tp_price_val))
                                new_sl_price = current_price * (1 + float(new_sl_price_val))
                        else:
                            new_tp_price, new_sl_price = None, None
                        
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO trade_adjustments (trade_id, timestamp, action, new_tp_price, new_sl_price, reasoning)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            open_trade['id'],
                            datetime.now().isoformat(),
                            ai_action,
                            new_tp_price,
                            new_sl_price,
                            decision.get('reasoning')
                        ))
                        conn.commit()
                        conn.close()

                    if ai_action == "CLOSE":
                        print("AI recommends closing position. Closing now.")
                        close_mock_trade(open_trade['id'], current_price)
                        is_closed = True
                    
                    elif ai_action == "ADJUST":
                        new_tp_pct = float(decision.get('new_tp_percentage', 0))
                        new_sl_pct = float(decision.get('new_sl_percentage', 0))

                        if new_tp_pct > 0 and new_sl_pct > 0:
                            # 현재 가격 기준으로 새로운 TP/SL 계산
                            if open_trade['action'] == 'long':
                                new_tp_price = current_price * (1 + new_tp_pct)
                                new_sl_price = current_price * (1 - new_sl_pct)
                            else: # short
                                new_tp_price = current_price * (1 - new_sl_pct)
                                new_sl_price = current_price * (1 + new_sl_pct)
                            
                            # DB에 새로운 TP/SL 업데이트
                            update_trade_exit_points(open_trade['id'], new_tp_price, new_sl_price)
                            print(f"TP/SL Updated. New TP: ${new_tp_price:,.2f}, New SL: ${new_sl_price:,.2f}")
                    
                    # 마지막 분석 시간 기록
                    last_in_position_analysis = datetime.now()

                # 포지션이 종료되었다면, 잠시 대기 후 루프의 처음으로 돌아감
                if is_closed:
                    last_in_position_analysis = None # 포지션 종료 시 분석 시간 초기화
                    time.sleep(10)
                    continue
                

            # --- 2. 포지션이 없는 경우: 새로운 거래 분석 ---
            else:
                print("No open position. Analyzing market for new trade...")
                last_in_position_analysis = None # 포지션 없을 때도 분석 시간 초기화

                market_data = fetch_multi_timeframe_data()
                if not market_data:
                    print("Could not fetch market data. Retrying in 1 minute.")
                    time.sleep(60)
                    continue

                news_data = fetch_bitcoin_news()
                historical_data = get_historical_trading_data(limit=10)
                wallet_balance = get_wallet_balance()

                timeframes_data_for_json = {}
                for tf, df in market_data.items():
                    df['timestamp'] = df['timestamp'].astype(str)
                    timeframes_data_for_json[tf] = df.to_dict(orient="records")
                
                analysis_input = {
                    "current_price": current_price,
                    "wallet_balance_usd": wallet_balance,
                    "timeframes": timeframes_data_for_json,
                    "recent_news": news_data,
                    "historical_trading_data": historical_data
                }

                # active_prompt.txt 파일의 내용을 읽어옴
                with open(ACTIVE_PROMPT_FILE, "r") as f:
                    system_prompt_content = f.read()

                print("Asking AI for trading advice...")
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": system_prompt_content},
                        {"role": "user", "content": json.dumps(analysis_input, indent=2)}
                    ],
                    response_format={"type": "json_object"}
                )
                
                response_content = response.choices[0].message.content.strip()
                decision = json.loads(response_content)
                
                action = decision.get('direction', 'NO_POSITION').lower()
                reasoning = decision.get('reasoning', 'No specific reason provided.')
                print(f"AI Decision: {action.upper()} | Reason: {reasoning}")

                # 거래를 실행할 때만 AI 분석 로그를 저장하도록 수정
                if action in ["long", "short"]:
                    analysis_data_to_save = {
                        'current_price': current_price,
                        'direction': action.upper(),
                        'reasoning': reasoning
                    }
                    analysis_id = save_ai_analysis(analysis_data_to_save)

                    leverage = int(decision.get('recommended_leverage', 1))
                    position_size_pct = float(decision.get('recommended_position_size', 0))
                    sl_pct = float(decision.get('stop_loss_percentage', 0))
                    tp_pct = float(decision.get('take_profit_percentage', 0))

                    if position_size_pct <= 0 or sl_pct <= 0 or tp_pct <= 0:
                        print("AI recommendation is missing key values (size, sl, tp). Skipping trade.")
                        time.sleep(60)
                        continue
                    
                    investment_amount_usd = wallet_balance * position_size_pct
                    if investment_amount_usd < 5:
                        print("Calculated investment is too small. Skipping trade.")
                        time.sleep(60)
                        continue
                    
                    total_position_value = investment_amount_usd * leverage
                    amount_btc = total_position_value / current_price
                    
                    if action == 'long':
                        sl_price = current_price * (1 - sl_pct)
                        tp_price = current_price * (1 + tp_pct)
                    else: # short
                        sl_price = current_price * (1 + sl_pct)
                        tp_price = current_price * (1 - sl_pct)

                    mock_trade_data = {
                        'action': action, 'entry_price': current_price, 'amount': amount_btc,
                        'leverage': leverage, 'sl_price': sl_price, 'tp_price': tp_price
                    }
                    trade_id = save_mock_trade(mock_trade_data)
                    
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE mock_ai_analysis SET trade_id = ? WHERE id = ?", (trade_id, analysis_id))
                    conn.commit()
                    conn.close()
                    
                    print(f"\n{'='*10} NEW MOCK POSITION OPENED {'='*9}")
                    print(f"Trade ID: {trade_id} | Action: {action.upper()}")
                    print(f"Entry Price: ${current_price:,.2f}")
                    print(f"Amount: {amount_btc:.4f} BTC (${total_position_value:,.2f})")
                    print(f"Leverage: {leverage}x (Margin: ${investment_amount_usd:,.2f})")
                    print(f"Stop Loss: ${sl_price:,.2f} (-{sl_pct*100:.2f}%)")
                    print(f"Take Profit: ${tp_price:,.2f} (+{tp_pct*100:.2f}%)")
                    print("="*42)
                
                else: # NO_POSITION
                    print("AI recommends NO POSITION. Waiting for the next opportunity.")
            
             # 대기 시간: 포지션 있으면 1분, 없으면 1분
            sleep_time = 60
            print(f"Waiting for {sleep_time} seconds...")
            time.sleep(sleep_time)

        except Exception as e:
            print(f"\nAn error occurred in the main loop: {e}")
            print("Retrying in 5 minutes...")
            time.sleep(300)

if __name__ == "__main__":
    main()