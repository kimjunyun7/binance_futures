import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv() # .env 파일 로드

# --- 1. 설정 및 초기화 ---
st.set_page_config(
    page_title="모의 트레이딩 봇 대시보드",
    page_icon="🤖",
    layout="wide"
)

# 파일 경로 및 비밀번호 설정
DB_FILE = "/home/ubuntu/binance_futures/mock_trading.db"
PASSWORD_FILE = "/home/ubuntu/binance_futures/password.txt"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") # .env에서 2차 비밀번호 로드

# --- 2. 비밀번호 관리 함수 (기존과 동일) ---
def initialize_password():
    if not os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, "w") as f:
            f.write("admin123")

def get_password():
    with open(PASSWORD_FILE, "r") as f:
        return f.read().strip()

def set_password(new_password):
    with open(PASSWORD_FILE, "w") as f:
        f.write(new_password)

# --- 3. 데이터베이스 조회 함수 (기존과 동일) ---
def get_db_connection():
    return sqlite3.connect(DB_FILE, timeout=10)

def fetch_data():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    total_pnl = pd.read_sql_query("SELECT SUM(profit_loss) as total_pnl FROM mock_trades WHERE status = 'CLOSED'", conn).iloc[0]['total_pnl'] or 0
    closed_trades_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'CLOSED'", conn)
    total_trades = len(closed_trades_df)
    winning_trades = len(closed_trades_df[closed_trades_df['profit_loss'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    try:
        wallet_balance = pd.read_sql_query("SELECT usdt_balance FROM mock_wallet LIMIT 1", conn).iloc[0]['usdt_balance']
    except (IndexError, KeyError):
        wallet_balance = 0
    open_trade_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'OPEN' ORDER BY timestamp DESC LIMIT 1", conn)
    trade_history_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'CLOSED' ORDER BY exit_timestamp DESC LIMIT 20", conn)
    ai_log_df = pd.read_sql_query("SELECT * FROM mock_ai_analysis ORDER BY timestamp DESC LIMIT 20", conn)
    conn.close()
    return {
        "wallet_balance": wallet_balance, "total_pnl": total_pnl, "win_rate": win_rate,
        "total_trades": total_trades, "open_trade": open_trade_df,
        "trade_history": trade_history_df, "ai_log": ai_log_df
    }

# --- 4. 대시보드 UI를 그리는 함수 (기존과 동일) ---
def draw_dashboard():
    st.title("🤖 AI 모의 트레이딩 봇 대시보드")
    st.markdown(f"마지막 업데이트: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
    try:
        data = fetch_data()
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 현재 자산 (USDT)", f"${data['wallet_balance']:,.2f}")
    col2.metric("📈 총 손익 (USDT)", f"${data['total_pnl']:,.2f}", f"{data['total_pnl'] / 10000 * 100:.2f}%" if data['total_pnl'] != 0 else "0.00%")
    col3.metric("🎯 승률", f"{data['win_rate']:.2f}%")
    col4.metric("📊 총 거래 횟수", f"{data['total_trades']} 회")
    st.markdown("---")
    st.subheader("🚀 현재 포지션 (OPEN)")
    if not data['open_trade'].empty:
        trade = data['open_trade'].iloc[0]
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.info(f"**방향**: {trade['action'].upper()}")
        col1.info(f"**진입가**: ${trade['entry_price']:,.2f}")
        col1.info(f"**수량**: {trade['amount']:.4f} BTC")
        col1.warning(f"**손절가**: ${trade['sl_price']:,.2f}")
        col1.success(f"**익절가**: ${trade['tp_price']:,.2f}")
    else:
        st.info("현재 진행 중인 포지션이 없습니다.")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 최근 거래 내역 (CLOSED)")
        if not data['trade_history'].empty:
            display_trades = data['trade_history'][['exit_timestamp', 'action', 'entry_price', 'exit_price', 'profit_loss']]
            display_trades.columns = ['종료 시간', '방향', '진입가', '청산가', '손익(USDT)']
            st.dataframe(display_trades, use_container_width=True, hide_index=True)
        else:
            st.info("거래 내역이 없습니다.")
    with col2:
        st.subheader("🧠 AI 분석 로그")
        if not data['ai_log'].empty:
            display_logs = data['ai_log'][['timestamp', 'direction', 'reasoning']]
            display_logs.columns = ['분석 시간', '추천', '분석 근거']
            st.dataframe(display_logs, use_container_width=True, hide_index=True)
        else:
            st.info("AI 분석 로그가 없습니다.")
    st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)

# --- 5. 메인 실행 로직 ---

initialize_password()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔒 로그인")
    
    # --- 로그인 폼 ---
    with st.form("login_form"):
        password_input = st.text_input("비밀번호를 입력하세요.", type="password")
        submitted = st.form_submit_button("로그인")
        if submitted:
            correct_password = get_password()
            if password_input == correct_password:
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    
    # --- 비밀번호 재설정 기능 추가 ---
    with st.expander("비밀번호를 잊으셨나요?"):
        with st.form("reset_password_form", clear_on_submit=True):
            st.subheader("비밀번호 재설정")
            new_password = st.text_input("새 접속 비밀번호", type="password", key="new_pw")
            admin_password_input = st.text_input("2차 비밀번호", type="password", key="admin_pw")
            
            reset_submitted = st.form_submit_button("재설정하기")
            if reset_submitted:
                if admin_password_input == ADMIN_PASSWORD:
                    if new_password:
                        set_password(new_password)
                        st.success("비밀번호가 성공적으로 재설정되었습니다. 새 비밀번호로 로그인하세요.")
                    else:
                        st.warning("새 비밀번호를 입력해주세요.")
                else:
                    st.error("2차 비밀번호가 틀렸습니다.")
else:
    # --- 로그인 성공 시 ---
    with st.sidebar:
        st.header("⚙️ 설정")
        with st.form("password_change_form", clear_on_submit=True):
            st.subheader("비밀번호 변경")
            new_password_sidebar = st.text_input("새 접속 비밀번호", type="password", key="new_pw_sidebar")
            admin_password_input_sidebar = st.text_input("2차 비밀번호", type="password", key="admin_pw_sidebar")
            
            submitted_sidebar = st.form_submit_button("변경하기")
            if submitted_sidebar:
                if admin_password_input_sidebar == ADMIN_PASSWORD:
                    if new_password_sidebar:
                        set_password(new_password_sidebar)
                        st.success("접속 비밀번호가 성공적으로 변경되었습니다.")
                    else:
                        st.warning("새 비밀번호를 입력해주세요.")
                else:
                    st.error("2차 비밀번호가 틀렸습니다.")
        
        if st.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()
    
    # 메인 대시보드 그리기
    draw_dashboard()