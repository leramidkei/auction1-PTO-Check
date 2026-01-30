# [Ver 1.1] 옥션원 서울지사 연차확인 시스템
# Update: 2026-01-31
# Changes: 
# - 관리자 메뉴 위치 변경 (프로필 카드 하단 이동)
# - 로그아웃 버튼과 관리자 모드 토글 가로 정렬
# - 관리자 사용자 전환 시 '최초 비밀번호 변경' 강제 화면 건너뛰기 적용

import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import json
import time
import datetime
import re
import os
import math

# ==============================================================================
# 1. 페이지 설정 및 CSS (Ver 1.1)
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered", page_icon="🌸")

st.markdown("""
    <style>
    /* 1. 폰트 및 기본 배경 */
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    
    [data-testid="stAppViewContainer"] {
        background-color: #F8F9FA;
        font-family: 'Pretendard', sans-serif;
    }

    /* 2. 메인 컨테이너 */
    .block-container {
        max-width: 480px;
        padding-top: 3rem; 
        padding-bottom: 5rem;
        padding-left: 1.2rem;
        padding-right: 1.2rem;
        margin: auto;
        background-color: #ffffff;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border-radius: 24px;
        min-height: 95vh;
    }

    /* 3. 버전 배지 */
    .version-badge-container {
        width: 100%;
        display: flex;
        justify-content: flex-end; 
        margin-bottom: 5px; 
    }
    .version-badge {
        background-color: #f1f3f5;
        color: #adb5bd;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        font-family: monospace;
    }

    /* 4. 프로필 카드 */
    .profile-card {
        display: grid;
        grid-template-columns: 1.4fr 1fr; 
        background-color: #fff;
        border-radius: 20px;
        overflow: hidden;
        margin-bottom: 15px; /* 하단 여백 확보 */
        height: 160px; 
        border: 1px solid #f0f0f0;
    }

    .card-text {
        padding: 20px;
        display: flex;
        flex-direction: column;
        justify-content: center; 
        align-items: flex-start;
    }

    .card-image {
        position: relative;
        width: 100%;
        height: 100%;
        background-color: #F0F8FF;
    }

    .card-image img {
        width: 100%;
        height: 100%;
        object-fit: cover; 
        object-position: top center; 
    }

    /* 텍스트 스타일 */
    .hello-text { font-size: 1rem; color: #666; margin-bottom: 4px; font-weight: 500; }
    .name-text { 
        font-size: 1.6rem; 
        color: #333; 
        font-weight: 900; 
        line-height: 1.3; 
        margin-bottom: 8px; 
        word-break: keep-all; 
    }
    .name-highlight { color: #5D9CEC; }
    .msg-text { font-size: 0.85rem; color: #999; }

    /* 5. 탭 스타일링 */
    .stTabs { margin-top: 10px; }
    .stTabs [data-baseweb="tab-list"] { 
        gap: 8px; 
        margin-bottom: 15px; 
        background-color: #fff;
        position: sticky;
        top: 0;
        z-index: 10;
        padding-top: 5px;
    }
    .stTabs [data-baseweb="tab"] { 
        height: 44px; 
        border-radius: 12px; 
        font-weight: 700; 
        font-size: 0.95rem; 
        flex: 1; 
    }
    .stTabs [aria-selected="true"] { 
        color: #5D9CEC !important; 
        background-color: #F0F8FF !important; 
    }

    .tab-section-header {
        font-size: 1rem;
        font-weight: 700;
        color: #495057;
        margin-bottom: 15px;
        padding-left: 5px;
        border-left: 4px solid #5D9CEC;
        line-height: 1.2;
        height: 24px;
        display: flex;
        align-items: center;
    }

    /* 6. UI 요소 */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        background-color: #5D9CEC; 
        color: white;
        border: none;
        padding: 0.8rem 0;
        transition: 0.2s;
    }
    .stButton>button:hover { background-color: #4A89DC; }

    /* 로그아웃 버튼 (회색, 작게) */
    div[data-testid="column"] .stButton>button {
        background-color: #f1f3f5 !important;
        color: #868e96 !important;
        font-size: 0.8rem !important;
        padding: 0.5rem !important;
        border-radius: 8px !important;
        height: auto !important;
    }
    div[data-testid="column"] .stButton>button:hover {
        background-color: #e9ecef !important;
        color: #495057 !important;
    }

    .login-title {
        font-size: 1.8rem; font-weight: 800; color: #5D9CEC;
        text-align: center; margin-bottom: 3rem; margin-top: 2rem;
    }

    [data-testid="stMetricValue"] { font-size: 2.2rem; font-weight: 800; color: #5D9CEC; }
    
    .realtime-badge {
        background-color: #FFF0F0; color: #FF6B6B;
        padding: 5px 12px; border-radius: 20px;
        font-size: 0.8rem; font-weight: 800;
        display: inline-block; margin-bottom: 10px;
    }
    
    .info-box-spacer {
        height: 20px;
        width: 100%;
        display: block;
    }
    
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. 구글 드라이브 인증 (기존 로직)
# ==============================================================================
try:
    FOLDER_ID = st.secrets["FOLDER_ID"]
    SCOPES = ['https://www.googleapis.com/auth/drive']
except:
    st.error("Secrets 설정 확인 필요")
    st.stop()

@st.cache_resource
def get_drive_service():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except Exception as e:
        st.error(f"인증 실패: {e}")
        return None

def get_file_sort_key(filename):
    match = re.search(r'(\d{4})_(\d+)', filename)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (0, 0)

def get_all_files():
    service = get_drive_service()
    if not service: return None, None, None, []
    for _ in range(2):
        try:
            query = f"'{FOLDER_ID}' in parents and trashed=false"
            results = service.files().list(q=query, fields="files(id, name)").execute()
            all_files = results.get('files', [])
            user_db_id, renewal_id, realtime_id = None, None, None
            monthly_files = []
            for f in all_files:
                name = f['name']
                if name == "user_db.json": user_db_id = f['id']
                elif name == "realtime_usage.json": realtime_id = f['id']
                elif "renewal" in name or "갱신" in name: renewal_id = f['id']
                elif ".xlsx" in name: monthly_files.append(f)
            monthly_files.sort(key=lambda x: get_file_sort_key(x['name']), reverse=True)
            return user_db_id, renewal_id, realtime_id, monthly_files
        except: time.sleep(1); continue
    return None, None, None, []

def load_json_file(file_id):
    service = get_drive_service()
    if not file_id: return {}
    try:
        request = service.files().get_media(fileId=file_id)
        return json.load(io.BytesIO(request.execute()))
    except: return {}

def save_user_db(file_id, data):
    service = get_drive_service()
    try:
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        media = MediaIoBaseUpload(io.BytesIO(json_str.encode('utf-8')), mimetype='application/json')
        service.files().update(fileId=file_id, media_body=media).execute()
        return True
    except: return False

# ==============================================================================
# 3. 데이터 파싱 로직 (기존 로직)
# ==============================================================================
def parse_attendance(file_content):
    try:
        df_raw = pd.read_excel(file_content, header=None)
        name_row_idx = -1
        for i, row in df_raw.iterrows():
            if any("성명" in str(x).replace(" ", "") for x in row.astype(str).values):
                name_row_idx = i; break
        if name_row_idx == -1: return pd.DataFrame()

        remain_col_idx = -1
        for r_idx in [name_row_idx, name_row_idx + 1]:
            if r_idx < len(df_raw):
                for c_idx, val in enumerate(df_raw.iloc[r_idx]):
                    if "연차잔여일" in str(val).replace(" ", ""):
                        remain_col_idx = c_idx; break
            if remain_col_idx != -1: break
        
        file_content.seek(0)
        df = pd.read_excel(file_content, header=name_row_idx)
        df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
        date_cols = [c for c in df.columns if str(c).isdigit() and 1 <= int(str(c)) <= 31]
        
        parsed = []
        for i in range(len(df)):
            row = df.iloc[i]
            name = str(row.get('성명', '')).replace(" ", "").strip()
            if name and name != "nan":
                usage, count = [], 0.0
                for d in date_cols:
                    val = str(row[d])
                    if "연차" in val: usage.append(f"{d}일(연차)"); count += 1.0
                    elif "반차" in val: usage.append(f"{d}일(반차)"); count += 0.5
                remain = 0.0
                if remain_col_idx != -1 and i + 1 < len(df):
                    try: remain = float(df.iloc[i+1, remain_col_idx])
                    except: remain = 0.0
                parsed.append({'이름': name, '사용내역': ", ".join(usage) if usage else "-", '사용개수': count, '잔여': remain})
        return pd.DataFrame(parsed)
    except: return pd.DataFrame()

def parse_renewal_excel(file_content):
    try:
        df_meta = pd.read_excel(file_content, header=None, nrows=3)
        try: target_year = int(df_meta.iloc[1, 0])
        except: target_year = datetime.datetime.now().year
        file_content.seek(0)
        df = pd.read_excel(file_content, header=3)
        df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
        parsed = []
        for i, row in df.iterrows():
            name = str(row.iloc[0]).replace(" ", "").strip()
            if name and name != "nan" and name != "이름":
                try:
                    month = int(row['월']); day = int(row['일'])
                    renewal_date = f"{target_year}-{month:02d}-{day:02d}"
                    count = row.get('올해발생연차개수', 0)
                    parsed.append({'이름': name, '갱신일': renewal_date, '갱신개수': count})
                except: continue
        return pd.DataFrame(parsed)
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_excel(file_id, is_renewal=False):
    service = get_drive_service()
    try:
        request = service.files().get_media(fileId=file_id)
        content = io.BytesIO(request.execute())
        if is_renewal: return parse_renewal_excel(content)
        return parse_attendance(content)
    except: return pd.DataFrame()

# ==============================================================================
# 4. 메인 로직 (Ver 1.1)
# ==============================================================================
user_db_id, renewal_id, realtime_id, monthly_files = get_all_files()

if not user_db_id:
    st.error("시스템 오류: user_db.json 파일을 찾을 수 없습니다.")
    st.stop()

if 'user_db' not in st.session_state:
    st.session_state.user_db = load_json_file(user_db_id)
    st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}

if 'login_status' not in st.session_state: st.session_state.login_status = False

# A. 로그인 화면
if not st.session_state.login_status:
    st.markdown('<div class="login-title">옥션원 서울지사<br>연차확인</div>', unsafe_allow_html=True)
    with st.form("login"):
        uid = st.text_input("아이디").replace(" ", "")
        upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if uid in st.session_state.user_db and st.session_state.user_db[uid]['pw'] == upw:
                st.session_state.login_status = True; st.session_state.user_id = uid; st.rerun()
            else: st.error("로그인 정보를 확인해주세요.")

# B. 메인 화면
else:
    # 1. 실제 로그인 사용자 정보
    login_uid = st.session_state.user_id
    login_uinfo = st.session_state.user_db.get(login_uid, {})
    
    # 2. [Ver 1.1 수정] 사용자 전환(Admin) 로직 - 상단에서 결정
    target_uid = login_uid # 기본은 본인
    
    # 세션 상태에 관리자 모드 관련 키가 있으면 읽어옴
    if st.session_state.get('admin_mode_toggle') and login_uinfo.get('role') == 'admin':
        # 선택된 사용자가 있으면 그 사용자로, 없으면 본인으로
        target_uid = st.session_state.get('impersonate_user', login_uid)

    # 3. 데이터 기준 설정 (target_uid 기준)
    uinfo = st.session_state.user_db.get(target_uid, {})
    
    # 4. 초기 비번 변경 로직 (Ver 1.1: 관리자 모드일 땐 무조건 패스)
    # 조건: (최초로그인 대상) AND (본인 로그인일 경우)에만 비번 변경 강제
    is_first_login = uinfo.get('first_login', True)
    is_impersonating = (login_uid != target_uid) # 관리자가 다른 사람 보는 중인가?

    if is_first_login and not is_impersonating:
        st.info(f"👋 {target_uid}님, 최초 1회 비밀번호를 변경해주세요.")
        with st.form("fc"):
            p1 = st.text_input("새 비밀번호", type="password")
            p2 = st.text_input("비밀번호 확인", type="password")
            if st.form_submit_button("변경하기"):
                if p1 == p2 and p1:
                    st.session_state.user_db[target_uid].update({"pw": p1, "first_login": False})
                    save_user_db(user_db_id, st.session_state.user_db)
                    st.success("변경 완료. 다시 로그인해주세요.")
                    for k in list(st.session_state.keys()): del st.session_state[k]
                    st.rerun()
                else: st.error("비밀번호가 일치하지 않습니다.")
    else:
        # [Ver 1.1] 배지 및 프로필 카드
        st.markdown("""
        <div class="version-badge-container">
            <div class="version-badge">Ver 1.1</div>
        </div>
        """, unsafe_allow_html=True)

        # 프로필 카드
        st.markdown(f"""
        <div class="profile-card">
            <div class="card-text">
                <div class="hello-text">반갑습니다,</div>
                <div class="name-text"><span class="name-highlight">{target_uid} {uinfo.get('title','')}</span>님</div>
                <div class="msg-text">오늘도 활기찬 하루 되세요!</div>
            </div>
            <div class="card-image">
                <img src="https://raw.githubusercontent.com/leramidkei/auction1-PTO-Check/main/character.png">
            </div>
        </div>
        """, unsafe_allow_html=True)

        # [Ver 1.1 수정] 컨트롤 패널 (로그아웃 | 관리자 모드) - 카드 하단 배치
        # 관리자일 경우
        if login_uinfo.get('role') == 'admin':
            c_logout, c_toggle = st.columns([1, 2])
            with c_logout:
                if st.button("로그아웃"): 
                    st.session_state.login_status = False
                    st.rerun()
            with c_toggle:
                # 관리자 모드 토글 (key를 사용하여 상태 유지)
                st.checkbox("🔧 관리자 모드", key="admin_mode_toggle")
            
            # 관리자 모드 켜졌을 때만 선택창 보임 (바로 아래에 배치)
            if st.session_state.get("admin_mode_toggle"):
                all_users = list(st.session_state.user_db.keys())
                # 선택 시 바로 target_uid에 반영되도록 key 설정
                st.selectbox("조회할 사용자 선택", all_users, 
                             index=all_users.index(target_uid) if target_uid in all_users else 0,
                             key="impersonate_user")
        else:
            # 일반 사용자일 경우 (로그아웃만)
            if st.button("로그아웃"): 
                st.session_state.login_status = False
                st.rerun()
        
        # 탭 영역
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
        
        def tab_header(text):
            st.markdown(f'<div class="tab-section-header">{text}</div>', unsafe_allow_html=True)

        def display_remain(val):
            if pd.isna(val) or math.isnan(val): return "∞"
            return f"{val}개"

        with tab1:
            tab_header("현재 잔여 연차 확인") 
            if monthly_files:
                latest_file = monthly_files[0]
                df = fetch_excel(latest_file['id'])
                
                realtime_applied = False
                realtime_usage = 0.0
                realtime_msg = ""
                
                try:
                    file_month = int(re.search(r'(\d+)월', latest_file['name']).group(1))
                    current_month = datetime.datetime.now().month
                    # 실시간 데이터도 target_uid 기준
                    if current_month > file_month and target_uid in st.session_state.realtime_data:
                        rt_info = st.session_state.realtime_data[target_uid]
                        realtime_usage = rt_info.get('used', 0.0)
                        realtime_msg = rt_info.get('details', '')
                        realtime_applied = True
                except: pass

                if not df.empty:
                    me = df[df['이름'] == target_uid]
                    if not me.empty:
                        excel_remain = float(me.iloc[0]['잔여'])
                        
                        if pd.isna(excel_remain):
                            final_str = "∞"
                        else:
                            if realtime_applied and realtime_usage > 0:
                                final_remain = excel_remain - realtime_usage
                                final_str = f"{final_remain}개"
                                st.markdown(f"<span class='realtime-badge'>📉 실시간 사용 -{realtime_usage}개 반영됨</span>", unsafe_allow_html=True)
                            else:
                                final_str = f"{excel_remain}개"

                        st.metric("현재 예상 잔여 연차", final_str)
                        st.caption(f"기준 파일: {latest_file['name']}")
                        
                        st.markdown('<div class="info-box-spacer"></div>', unsafe_allow_html=True)
                        
                        if realtime_msg: st.info(f"📝 **추가 내역:** {realtime_msg}")
                    else: st.warning("데이터가 없습니다.")
            else: st.error("엑셀 파일이 없습니다.")
            
            st.markdown("<br><br>", unsafe_allow_html=True)

        with tab2:
            tab_header("월별 사용 내역 조회") 
            if monthly_files:
                opts = {f['name']: f['id'] for f in monthly_files}
                sel = st.selectbox("월 선택", list(opts.keys()), label_visibility="collapsed")
                if sel:
                    df = fetch_excel(opts[sel])
                    me = df[df['이름'] == target_uid]
                    if not me.empty:
                        r = me.iloc[0]
                        c1, c2 = st.columns(2)
                        
                        remain_val = display_remain(float(r['잔여']))
                        
                        c1.metric("사용", f"{r['사용개수']}개")
                        c2.metric("잔여", remain_val)
                        
                        st.markdown('<div class="info-box-spacer"></div>', unsafe_allow_html=True)
                        
                        st.info(f"내역: {r['사용내역']}")
            
            st.markdown("<br><br>", unsafe_allow_html=True)

        with tab3:
            tab_header("연차 갱신 및 발생 내역") 
            if renewal_id:
                df = fetch_excel(renewal_id, True)
                me = df[df['이름'] == target_uid]
                if not me.empty:
                    r = me.iloc[0]
                    try:
                        rdt = pd.to_datetime(r['갱신일'])
                        now = pd.to_datetime(datetime.datetime.now().strftime("%Y-%m-%d"))
                        if rdt > now: st.info(f"📅 **{r['갱신일']}** 갱신 예정")
                        else: st.success(f"✅ **{r['갱신일']}** 갱신 완료")
                    except: st.write(f"📅 {r['갱신일']}")
                    st.metric("추가 발생", f"+{r['갱신개수']}개")
            else: st.info("갱신 정보가 없습니다.")
            
            st.markdown("<br><br>", unsafe_allow_html=True)

        with tab4:
            tab_header("비밀번호 변경") 
            
            # 관리자 모드일 경우 안내 문구 변경
            if is_impersonating:
                st.warning(f"⚠️ 현재 관리자 권한으로 **{target_uid}**님의 비밀번호를 변경합니다.")
            
            with st.form("pw_chg"):
                p1 = st.text_input("새 비번", type="password")
                p2 = st.text_input("확인", type="password")
                if st.form_submit_button("저장"):
                    if p1 == p2 and p1:
                        st.session_state.user_db[target_uid].update({"pw": p1, "first_login": False})
                        save_user_db(user_db_id, st.session_state.user_db)
                        st.success("저장되었습니다.")
                    else: st.error("비밀번호가 일치하지 않습니다.")
            
            st.markdown("<br><br>", unsafe_allow_html=True)
        
        if uinfo.get('role') == 'admin':
            with st.expander("🔐 관리자 데이터 확인"): st.json(st.session_state.user_db)
