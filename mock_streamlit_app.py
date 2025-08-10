import streamlit as st
import pandas as pd
import sqlite3
import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh

# --- 1. 설정 및 초기화 ---
load_dotenv()
st.set_page_config(page_title="트레이딩 봇 관리", page_icon="⚙️", layout="wide")

# 파일 경로 및 설정
DB_FILE = "/home/ubuntu/binance_futures/mock_trading.db"
PASSWORD_FILE = "/home/ubuntu/binance_futures/password.txt"
ACTIVE_PROMPT_FILE = "/home/ubuntu/binance_futures/active_prompt.txt"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# --- 2. 백엔드 함수 (데이터베이스, 파일 관리) ---

def setup_files_and_db():
    """실행에 필요한 파일과 DB 테이블을 준비합니다."""
    # 비밀번호 파일 생성
    if not os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, "w") as f: f.write("admin123")
    
    # DB 테이블 생성
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prompt_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        is_favorite INTEGER DEFAULT 0
    )
    """)
    # active_prompt.txt 파일이 없으면 prompts.py에서 가져와 생성
    if not os.path.exists(ACTIVE_PROMPT_FILE):
        try:
            from prompts import INITIAL_SYSTEM_PROMPT
            with open(ACTIVE_PROMPT_FILE, "w") as f: f.write(INITIAL_SYSTEM_PROMPT)
            # DB에도 첫 기록 삽입
            cursor.execute(
                "INSERT INTO prompt_history (content, start_time) VALUES (?, ?)",
                (INITIAL_SYSTEM_PROMPT, datetime.now().isoformat())
            )
        except ImportError:
            st.error("prompts.py 파일이 없거나 INITIAL_SYSTEM_PROMPT 변수가 없습니다.")

    conn.commit()
    conn.close()

def get_password():
    with open(PASSWORD_FILE, "r") as f: return f.read().strip()

def set_password(new_password):
    with open(PASSWORD_FILE, "w") as f: f.write(new_password)

def get_active_prompt():
    with open(ACTIVE_PROMPT_FILE, "r") as f: return f.read()

def update_active_prompt(new_prompt_content):
    now_iso = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE prompt_history SET end_time = ? WHERE end_time IS NULL", (now_iso,))
    cursor.execute("INSERT INTO prompt_history (content, start_time) VALUES (?, ?)", (new_prompt_content, now_iso))
    conn.commit()
    conn.close()
    with open(ACTIVE_PROMPT_FILE, "w") as f: f.write(new_prompt_content)

def get_prompt_history():
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT * FROM prompt_history ORDER BY is_favorite DESC, start_time DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def toggle_favorite(prompt_id, current_status):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    new_status = 1 if current_status == 0 else 0
    cursor.execute("UPDATE prompt_history SET is_favorite = ? WHERE id = ?", (new_status, prompt_id))
    conn.commit()
    conn.close()
    st.rerun()

def delete_prompt(prompt_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM prompt_history WHERE id = ?", (prompt_id,))
    conn.commit()
    conn.close()

def fetch_data():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        total_pnl = pd.read_sql_query("SELECT SUM(profit_loss) as total_pnl FROM mock_trades WHERE status = 'CLOSED'", conn).iloc[0]['total_pnl'] or 0
        closed_trades_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'CLOSED'", conn)
        wallet_balance = pd.read_sql_query("SELECT usdt_balance FROM mock_wallet LIMIT 1", conn).iloc[0]['usdt_balance']
        open_trade_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'OPEN' ORDER BY timestamp DESC LIMIT 1", conn)
        trade_history_df = pd.read_sql_query("SELECT * FROM mock_trades WHERE status = 'CLOSED' ORDER BY exit_timestamp DESC LIMIT 20", conn)
        ai_log_df = pd.read_sql_query("SELECT * FROM mock_ai_analysis ORDER BY timestamp DESC LIMIT 20", conn)
        total_trades = len(closed_trades_df)
        winning_trades = len(closed_trades_df[closed_trades_df['profit_loss'] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    except Exception:
        # DB가 비어있을 때를 대비한 기본값 설정
        return {
            "wallet_balance": 10000, "total_pnl": 0, "win_rate": 0, "total_trades": 0,
            "open_trade": pd.DataFrame(), "trade_history": pd.DataFrame(), "ai_log": pd.DataFrame()
        }
    finally:
        conn.close()
    
    return {
        "wallet_balance": wallet_balance, "total_pnl": total_pnl, "win_rate": win_rate,
        "total_trades": total_trades, "open_trade": open_trade_df,
        "trade_history": trade_history_df, "ai_log": ai_log_df
    }

# --- 3. UI 페이지 렌더링 함수 ---

def render_dashboard_page():
    st_autorefresh(interval=30000, key="dashboard_refresher")
    st.title("🤖 AI 모의 트레이딩 봇 대시보드")
    st.markdown(f"마지막 업데이트: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

    data = fetch_data()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💰 현재 자산 (USDT)", f"${data['wallet_balance']:,.2f}")
    col2.metric("📈 총 손익 (USDT)", f"${data['total_pnl']:,.2f}", f"{data['total_pnl'] / 10000 * 100:.2f}%" if data['total_pnl'] != 0 else "0.00%")
    col3.metric("🎯 승률", f"{data['win_rate']:.2f}%")
    col4.metric("📊 총 거래 횟수", f"{data['total_trades']} 회")
    st.markdown("---")
    
    st.subheader("🚀 현재 포지션 (OPEN)")
    if not data['open_trade'].empty:
        trade = data['open_trade'].iloc[0]
        cols = st.columns(5)
        cols[0].info(f"**방향**: {trade['action'].upper()}")
        cols[1].info(f"**진입가**: ${trade['entry_price']:,.2f}")
        cols[2].info(f"**수량**: {trade['amount']:.4f} BTC")
        cols[3].warning(f"**손절가**: ${trade['sl_price']:,.2f}")
        cols[4].success(f"**익절가**: ${trade['tp_price']:,.2f}")
    else:
        st.info("현재 진행 중인 포지션이 없습니다.")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 최근 거래 내역 (CLOSED)")
        if not data['trade_history'].empty:
            display_trades = data['trade_history'][['exit_timestamp', 'action', 'entry_price', 'exit_price', 'profit_loss']].copy()
            display_trades.columns = ['종료 시간', '방향', '진입가', '청산가', '손익(USDT)']
            st.dataframe(display_trades, use_container_width=True, hide_index=True)
        else:
            st.info("거래 내역이 없습니다.")
    with col2:
        st.subheader("🧠 AI 분석 로그")
        if not data['ai_log'].empty:
            for _, row in data['ai_log'].iterrows():
                try:
                    log_time = datetime.fromisoformat(row['timestamp'])
                    formatted_time = log_time.strftime('%Y-%m-%d %H:%M')
                except (ValueError, TypeError):
                    formatted_time = row['timestamp']

                # 1. expander에는 간단한 텍스트 라벨을 사용합니다.
                expander_label = f"{formatted_time} | 추천: {row['direction']}"

                with st.expander(expander_label, expanded=False):
                    # 2. HTML 형식의 제목과 분석 근거를 expander 내부에 그립니다.
                    st.markdown(
                        f"""
                        <div style="font-size: 1.1em; line-height: 1.4; margin-bottom: 10px;">
                            {formatted_time}<br>
                            <strong style="font-size: 1.2em;">{row['direction']}</strong>
                        </div>
                        <div style="height: 6em; overflow-y: auto; border: 1px solid #e6e6e6; padding: 10px; border-radius: 5px;">
                            {row['reasoning']}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
        else:
            st.info("AI 분석 로그가 없습니다.")

def render_prompt_page():
    st.title("⚙️ 프롬프트 관리")
    st.subheader("📝 현재 활성 프롬프트")
    current_prompt = get_active_prompt()
    new_prompt = st.text_area("프롬프트 내용", value=current_prompt, height=400, label_visibility="collapsed")
    
    if st.button("프롬프트 업데이트", type="primary"):
        if new_prompt != current_prompt:
            update_active_prompt(new_prompt)
            st.success("프롬프트가 성공적으로 업데이트되었습니다! 다음 거래부터 적용됩니다.")
            st.rerun()
        else:
            st.warning("변경된 내용이 없습니다.")

    st.markdown("---")
    st.subheader("📚 최근 프롬프트 목록")
    history_df = get_prompt_history()

    if 'delete_confirm_id' not in st.session_state:
        st.session_state['delete_confirm_id'] = None

    for _, row in history_df.iterrows():
        is_favorite = row['is_favorite'] == 1
        start_dt = datetime.fromisoformat(row['start_time']).strftime('%y-%m-%d %H:%M')
        end_dt = datetime.fromisoformat(row['end_time']).strftime('%y-%m-%d %H:%M') if pd.notna(row['end_time']) else "현재 사용 중"
        first_line = row['content'].strip().split('\n')[0]
        
        col1, col2, col3 = st.columns([0.1, 0.7, 0.2])

        with col1:
            st.button("★" if is_favorite else "☆", key=f"fav_{row['id']}", on_click=toggle_favorite, args=(row['id'], row['is_favorite']))
        with col2:
            with st.expander(f"`{first_line}`"):
                st.markdown(f"**사용 기간:** {start_dt} ~ {end_dt}")
                st.code(row['content'], language='markdown')
        with col3:
            st.write("")
            if st.button("삭제", key=f"del_{row['id']}", type="secondary"):
                st.session_state['delete_confirm_id'] = row['id']
                st.rerun()

        if st.session_state['delete_confirm_id'] == row['id']:
            fav_text = "⭐ 즐겨찾기된 프롬프트입니다." if is_favorite else ""
            st.warning(f"{fav_text} 정말로 이 프롬프트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.", icon="⚠️")
            col_confirm, col_cancel, _ = st.columns([1, 1, 3])
            if col_confirm.button("예, 삭제합니다", key=f"confirm_del_{row['id']}", type="primary"):
                delete_prompt(row['id'])
                st.session_state['delete_confirm_id'] = None
                st.rerun()
            if col_cancel.button("아니요, 취소합니다", key=f"cancel_del_{row['id']}"):
                st.session_state['delete_confirm_id'] = None
                st.rerun()

def render_log_viewer_page():
    """실시간 로그 뷰어 페이지를 그립니다."""
    st.title("실시간 로그 뷰어")

    # selectbox를 사용하여 어떤 로그를 볼지 선택
    log_choice = st.selectbox("확인할 로그를 선택하세요:", ("자동매매 봇 (tradingbot)", "웹 대시보드 (dashboard)"))
    
    service_name = "tradingbot" if "자동매매 봇" in log_choice else "dashboard"

    log_lines = st.number_input("가져올 최근 로그 줄 수:", min_value=10, max_value=1000, value=100, step=10)

    try:
        # journalctl 명령어를 실행하여 로그를 가져옴
        # --no-pager 옵션은 출력이 잘리지 않도록 함
        command = f"sudo journalctl -u {service_name} -n {log_lines} --no-pager"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            log_content = result.stdout
            st.text_area("Log Output", log_content, height=500, key="log_output_area")
        else:
            st.error(f"로그를 가져오는 데 실패했습니다:\n{result.stderr}")

    except Exception as e:
        st.error(f"로그 조회 중 예외가 발생했습니다: {e}")
    
    st_autorefresh(interval=3000, key="log_refresher") # 로그 페이지는 3초마다 새로고침

# --- 4. 메인 실행 로직 ---

setup_files_and_db()

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🔒 로그인")
    with st.form("login_form"):
        password_input = st.text_input("비밀번호", type="password", label_visibility="collapsed")
        submitted = st.form_submit_button("로그인")
        if submitted:
            if password_input == get_password():
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    with st.expander("비밀번호를 잊으셨나요?"):
        with st.form("reset_password_form", clear_on_submit=True):
            st.subheader("비밀번호 재설정")
            new_pw = st.text_input("새 접속 비밀번호", type="password", key="new_pw")
            admin_pw = st.text_input("2차 비밀번호", type="password", key="admin_pw")
            if st.form_submit_button("재설정하기"):
                if admin_pw == ADMIN_PASSWORD:
                    if new_pw:
                        set_password(new_pw)
                        st.success("비밀번호가 재설정되었습니다. 새 비밀번호로 로그인하세요.")
                    else:
                        st.warning("새 비밀번호를 입력해주세요.")
                else:
                    st.error("2차 비밀번호가 틀렸습니다.")
else:
    with st.sidebar:
        st.header("메뉴")
        page = st.radio("페이지 선택", ["대시보드", "프롬프트 관리", "실시간 로그"], label_visibility="collapsed")
        st.markdown("---")
        with st.expander("⚙️ 설정"):
            with st.form("password_change_form", clear_on_submit=True):
                st.subheader("비밀번호 변경")
                new_pw_sb = st.text_input("새 접속 비밀번호", type="password", key="new_pw_sb")
                admin_pw_sb = st.text_input("2차 비밀번호", type="password", key="admin_pw_sb")
                if st.form_submit_button("변경하기"):
                    if admin_pw_sb == ADMIN_PASSWORD:
                        if new_pw_sb:
                            set_password(new_pw_sb)
                            st.success("비밀번호가 변경되었습니다.")
                        else:
                            st.warning("새 비밀번호를 입력해주세요.")
                    else:
                        st.error("2차 비밀번호가 틀렸습니다.")
        if st.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

    if page == "대시보드":
        render_dashboard_page()
    elif page == "프롬프트 관리":
        render_prompt_page()
    elif page == "실시간 로그":
        render_log_viewer_page()