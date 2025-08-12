import streamlit as st
import os

# --- 설정 ---
PASSWORD_FILE = "/home/ubuntu/binance_futures/password.txt"

# --- 비밀번호 관리 함수 ---
def initialize_password():
    """비밀번호 파일이 없으면 초기 비밀번호(admin123)로 생성합니다."""
    if not os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, "w") as f:
            f.write("admin123")

def get_password():
    """파일에서 현재 접속 비밀번호를 읽어옵니다."""
    with open(PASSWORD_FILE, "r") as f:
        return f.read().strip()

def set_password(new_password):
    """파일에 새로운 접속 비밀번호를 저장합니다."""
    with open(PASSWORD_FILE, "w") as f:
        f.write(new_password)

# --- 로그인 UI 렌더링 함수 ---
def render_login_page(admin_password):
    """로그인 페이지 전체 UI를 그립니다."""
    st.title("🔒 로그인")

    # st.session_state에 mode가 없으면 '자동매매'로 초기화
    if 'mode' not in st.session_state:
        st.session_state.mode = '자동매매'

    # 라디오 버튼 추가
    mode = st.radio(
        "실행할 모드를 선택하세요:",
        ('자동매매', '물어보기'),
        horizontal=True,
        key='mode_selection'
    )
    
    # '물어보기'를 선택하면 다른 페이지로 리디렉션 (실제로는 다른 스크립트 실행)
    if mode == '물어보기':
        st.info("'물어보기' 모드로 전환합니다. 해당 기능은 별도의 페이지에서 제공될 예정입니다.")
        # 추후 ask_ai_crypto_page.py를 실행하는 로직을 여기에 추가할 수 있습니다.
        # 예: st.switch_page("pages/ask_ai_crypto_page.py") (Streamlit 1.28+ 버전)
        st.stop() # '물어보기' 선택 시 아래 로그인 폼은 보이지 않음

    # --- '자동매매' 선택 시에만 보이는 로그인 폼 ---
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
    
    with st.expander("비밀번호를 잊으셨나요?"):
        with st.form("reset_password_form", clear_on_submit=True):
            st.subheader("비밀번호 재설정")
            new_password = st.text_input("새 접속 비밀번호", type="password", key="new_pw")
            admin_password_input = st.text_input("2차 비밀번호", type="password", key="admin_pw")
            
            reset_submitted = st.form_submit_button("재설정하기")
            if reset_submitted:
                if admin_password_input == admin_password:
                    if new_password:
                        set_password(new_password)
                        st.success("비밀번호가 성공적으로 재설정되었습니다. 새 비밀번호로 로그인하세요.")
                    else:
                        st.warning("새 비밀번호를 입력해주세요.")
                else:
                    st.error("2차 비밀번호가 틀렸습니다.")