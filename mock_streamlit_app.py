import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(
    page_title="모의 트레이딩 봇 대시보드",
    page_icon="🤖",
    layout="wide"
)

# --- 데이터베이스 연결 ---
DB_FILE = "mock_trading.db"

def get_db_connection():
    """데이터베이스 커넥션을 반환합니다."""
    return sqlite3.connect(DB_FILE, timeout=10)

# --- 데이터 조회 함수 ---
def fetch_data():
    """데이터베이스에서 모든 필요한 데이터를 조회합니다."""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row # 컬럼명으로 접근 가능하게 설정

    # 요약 데이터 조회
    total_pnl = pd.read_sql_query("SELECT SUM(profit_loss) as total_pnl FROM mock_trades WHERE status = 'CLOSED'", conn).iloc[0]['total_pnl'] or 0
    closed_trades_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'CLOSED'", conn)
    total_trades = len(closed_trades_df)
    winning_trades = len(closed_trades_df[closed_trades_df['profit_loss'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # 지갑 잔고 조회
    try:
        wallet_balance = pd.read_sql_query("SELECT usdt_balance FROM mock_wallet LIMIT 1", conn).iloc[0]['usdt_balance']
    except (IndexError, KeyError):
        wallet_balance = 0 # 지갑 정보가 없을 경우 기본값

    # 현재 진행 중인 거래
    open_trade_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'OPEN' ORDER BY timestamp DESC LIMIT 1", conn)

    # 거래 내역 (최근 20개)
    trade_history_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'CLOSED' ORDER BY exit_timestamp DESC LIMIT 20", conn)

    # AI 분석 로그 (최근 20개)
    ai_log_df = pd.read_sql_query("SELECT * FROM mock_ai_analysis ORDER BY timestamp DESC LIMIT 20", conn)

    conn.close()

    return {
        "wallet_balance": wallet_balance,
        "total_pnl": total_pnl,
        "win_rate": win_rate,
        "total_trades": total_trades,
        "open_trade": open_trade_df,
        "trade_history": trade_history_df,
        "ai_log": ai_log_df
    }

# --- 대시보드 UI 구성 ---

# 1. 제목
st.title("🤖 AI 모의 트레이딩 봇 대시보드")
st.markdown(f"마지막 업데이트: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

# 데이터 로드
try:
    data = fetch_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()


# 2. 핵심 지표 (KPI)
col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 현재 자산 (USDT)", f"${data['wallet_balance']:,.2f}")
col2.metric("📈 총 손익 (USDT)", f"${data['total_pnl']:,.2f}", f"{data['total_pnl'] / 10000 * 100:.2f}%" if data['total_pnl'] != 0 else "0.00%")
col3.metric("🎯 승률", f"{data['win_rate']:.2f}%")
col4.metric("📊 총 거래 횟수", f"{data['total_trades']} 회")

st.markdown("---")

# 3. 현재 진행 중인 포지션
st.subheader("🚀 현재 포지션 (OPEN)")
if not data['open_trade'].empty:
    trade = data['open_trade'].iloc[0]
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.info(f"**방향**: {trade['action'].upper()}")
    col2.info(f"**진입가**: ${trade['entry_price']:,.2f}")
    col3.info(f"**수량**: {trade['amount']:.4f} BTC")
    col4.warning(f"**손절가**: ${trade['sl_price']:,.2f}")
    col5.success(f"**익절가**: ${trade['tp_price']:,.2f}")
else:
    st.info("현재 진행 중인 포지션이 없습니다.")

st.markdown("---")

# 4. 최근 거래 내역 및 AI 분석 로그
col1, col2 = st.columns(2)

with col1:
    st.subheader("📋 최근 거래 내역 (CLOSED)")
    if not data['trade_history'].empty:
        # 보여줄 컬럼만 선택하고 이름 변경
        display_trades = data['trade_history'][['exit_timestamp', 'action', 'entry_price', 'exit_price', 'profit_loss']]
        display_trades.columns = ['종료 시간', '방향', '진입가', '청산가', '손익(USDT)']
        st.dataframe(display_trades, use_container_width=True, hide_index=True)
    else:
        st.info("거래 내역이 없습니다.")

with col2:
    st.subheader("🧠 AI 분석 로그")
    if not data['ai_log'].empty:
        # 보여줄 컬럼만 선택하고 이름 변경
        display_logs = data['ai_log'][['timestamp', 'direction', 'reasoning']]
        display_logs.columns = ['분석 시간', '추천', '분석 근거']
        st.dataframe(display_logs, use_container_width=True, hide_index=True)
    else:
        st.info("AI 분석 로그가 없습니다.")

# 30초마다 페이지 자동 새로고침
st.markdown('<meta http-equiv="refresh" content="30">', unsafe_allow_html=True)