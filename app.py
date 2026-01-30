import streamlit as st
import pandas as pd
import datetime
import json
import os

# -----------------------------------------------------------------------------
# 1. 페이지 설정 (탭 이름, 아이콘)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="서울지사 연차 현황",
    page_icon="📅",
    layout="centered"
)

# -----------------------------------------------------------------------------
# 2. 커스텀 CSS (파스텔톤 디자인 & 모바일 최적화)
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* 1. 전체 배경: 화사한 파스텔 블루 그라데이션 */
    .stApp {
        background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); /* 깔끔한 화이트톤 */
        background-color: #F0F8FF; /* 혹은 아주 연한 하늘색 */
    }

    /* 2. 로그인 타이틀 (모바일 줄바꿈 방지 & 폰트 조정) */
    .login-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #4A4A4A;
        text-align: center;
        white-space: nowrap; /* 줄바꿈 금지 */
        margin-bottom: 20px;
    }
    
    /* 모바일 화면에서만 폰트 크기 살짝 더 줄임 */
    @media (max-width: 480px) {
        .login-title {
            font-size: 1.4rem; 
        }
    }

    /* 3. 메인 인사말 스타일 */
    .greeting-text {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        margin-top: 20px;
    }
    .sub-text {
        font-size: 1rem;
        color: #666;
    }

    /* 4. 카드 스타일 (연차 보여주는 박스) */
    .metric-card {
        background-color: #ffffff;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); /* 부드러운 그림자 */
        text-align: center;
        border: 1px solid #E1E1E1;
        margin-bottom: 10px;
    }
    .metric-label {
        font-size: 1rem;
        color: #888;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #5D9CEC; /* 파스텔 블루 포인트 컬러 */
    }
    .metric-delta {
        font-size: 0.9rem;
        color: #FF6B6B; /* 파스텔 레드 (차감 표시) */
        background-color: #FFF0F0;
        padding: 3px 8px;
        border-radius: 10px;
        font-weight: bold;
    }

    /* 5. 버튼 스타일 꾸미기 */
    .stButton>button {
        background-color: #5D9CEC;
        color: white;
        border-radius: 10px;
        border: none;
        width: 100%;
        padding: 10px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #4A89DC;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 3. 데이터 로딩 함수 (기존 로직 유지)
# -----------------------------------------------------------------------------
# [주의] 봇이 수집한 파일(realtime_usage.json)이 있으면 그걸 우선으로 봅니다.
# 엑셀 파일은 'base_data.xlsx'라고 가정합니다. (없으면 0으로 처리)
def load_data(user_name):
    # 1. 엑셀 기준 데이터 (지난달 마감)
    base_vacation = 15.0 # (예시) 실제로는 엑셀에서 읽어오게 구현 가능
    base_source = "2026_1월 서울지사 출근부"
    
    # 2. 봇이 가져온 실시간 데이터 확인
    realtime_usage = 0.0
    realtime_details = []
    
    if os.path.exists("realtime_usage.json"):
        try:
            with open("realtime_usage.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                if user_name in data:
                    realtime_usage = data[user_name].get("used", 0.0)
                    detail_str = data[user_name].get("details", "")
                    if detail_str: realtime_details.append(detail_str)
        except:
            pass
            
    # 3. 최종 계산
    final_vacation = base_vacation - realtime_usage
    
    return {
        "total": base_vacation,
        "used_realtime": realtime_usage,
        "remain": final_vacation,
        "source": base_source,
        "details": ", ".join(realtime_details)
    }

# -----------------------------------------------------------------------------
# 4. 화면 구성 (로그인 vs 메인)
# -----------------------------------------------------------------------------

# 세션 상태 초기화 (로그인 여부)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""

# A. 로그인 화면
if not st.session_state['logged_in']:
    # [UI 수정] 타이틀을 HTML로 직접 그려서 줄바꿈 방지
    st.markdown('<div class="login-title">🏢 서울지사 연차 조회</div>', unsafe_allow_html=True)
    
    with st.container():
        name_input = st.text_input("성함", placeholder="예: 김상호")
        pw_input = st.text_input("비밀번호", type="password")
        
        if st.button("로그인"):
            # (간이 로그인 로직 - 실제로는 DB 연동 필요)
            if name_input and pw_input == "1234": # 테스트용 비번 1234
                st.session_state['logged_in'] = True
                st.session_state['user_name'] = name_input
                st.rerun()
            else:
                st.error("성함 혹은 비밀번호를 확인해주세요.")

# B. 메인 대시보드
else:
    user_name = st.session_state['user_name']
    data = load_data(user_name)
    
    # --- 상단 헤더 영역 (캐릭터 + 인사말) ---
    col1, col2 = st.columns([2.5, 1]) # 왼쪽 글씨(2.5), 오른쪽 이미지(1) 비율
    
    with col1:
        st.markdown(f"""
        <div class="greeting-text">반갑습니다,<br>
        <span style="color:#5D9CEC;">{user_name} 과장님!</span> 👋</div>
        <div class="sub-text">오늘도 좋은 하루 되세요.</div>
        """, unsafe_allow_html=True)
        
    with col2:
        # 캐릭터 이미지 표시 (파일이 없으면 에러 안 나게 처리)
        if os.path.exists("character.png"):
            st.image("character.png", width=110) # 사이즈 조절
        else:
            st.write("😎") # 이미지가 없으면 이모지로 대체

    st.markdown("---")

    # --- 연차 카드 영역 ---
    # 커스텀 HTML로 카드 디자인 적용
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">현재 잔여 연차</div>
        <div class="metric-value">{data['remain']}개</div>
        {'<div class="metric-delta">📉 실시간 -' + str(data['used_realtime']) + '개 반영됨</div>' if data['used_realtime'] > 0 else ''}
    </div>
    """, unsafe_allow_html=True)

    # --- 상세 정보 (캡션) ---
    st.info(f"""
    **ℹ️ 계산 기준**
    * **기초 데이터:** {data['source']} ({data['total']}개)
    * **실시간 차감:** {data['used_realtime']}개 ({data['details'] if data['details'] else '내역 없음'})
    """)

    # --- 로그아웃 버튼 ---
    if st.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()

# -----------------------------------------------------------------------------
# (Tip) 터미널 실행: streamlit run app.py
