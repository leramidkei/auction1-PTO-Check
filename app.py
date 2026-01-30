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

# ==============================================================================
# 1. 페이지 설정 및 CSS (캐릭터 비율 해제 & 탭 높이 강력 고정)
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered", page_icon="🌸")

st.markdown("""
    <style>
    /* 1. 기본 폰트 및 배경 */
    [data-testid="stAppViewContainer"] {
        background-color: #FDFDFD;
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    }

    /* 2. 메인 컨테이너 (상단 여백 더 확보) */
    .block-container {
        max-width: 480px;
        padding-top: 5rem; /* 탭 잘림 방지를 위해 넉넉히 */
        padding-bottom: 2rem;
        padding-left: 1.2rem;
        padding-right: 1.2rem;
        margin: auto;
        background-color: #ffffff;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        border-radius: 24px;
        min-height: 95vh;
    }
    @media (max-width: 480px) { 
        .block-container { 
            max-width: 100%; 
            box-shadow: none; 
            padding-top: 4rem !important; /* 모바일에서도 충분히 확보 */
            padding-left: 1rem;
            padding-right: 1rem;
            border-radius: 0;
        } 
    }

    /* 3. 로그인 타이틀 */
    .login-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #5D9CEC;
        text-align: center;
        line-height: 1.35;
        margin-bottom: 2.5rem;
        margin-top: 2rem;
    }

    /* 4. [핵심] 헤더 레이아웃 (55:45 분할 & 완전 중앙 정렬) */
    .header-wrapper {
        display: flex;
        flex-direction: row;
        align-items: center; /* 세로 중앙 정렬 (이미지가 길어져도 텍스트는 가운데) */
        width: 100%;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 1.5rem;
    }

    /* 왼쪽 텍스트 영역 (55%) */
    .header-text-part {
        width: 55%;
        padding-right: 5px;
        display: flex;
        flex-direction: column;
        justify-content: center; /* 세로 중앙 */
        align-items: center;     /* [요청반영] 가로 중앙 */
        text-align: center;      /* 글자 자체도 가운데 정렬 */
    }

    /* 오른쪽 이미지 영역 (45%) */
    .header-img-part {
        width: 45%;
        display: flex;
        justify-content: center;
        align-items: center;
    }

    /* 이미지 스타일: 너비 100% (높이는 자동 증가) */
    .custom-char-img {
        width: 100%;  /* 부모(45%)를 꽉 채움 */
        height: auto; /* 비율대로 세로로 길어짐 */
        object-fit: contain;
        display: block;
    }

    /* 텍스트 스타일 */
    .greeting-main { 
        font-size: 1.1rem; 
        font-weight: bold; 
        color: #333; 
        line-height: 1.3; 
        white-space: nowrap; 
    }
    .name-highlight { 
        color: #5D9CEC; 
        font-size: 1.5rem; 
        font-weight: 900; 
        margin-bottom: 6px;
        white-space: nowrap;
    }
    .greeting-sub { 
        font-size: 0.85rem; 
        color: #999; 
        font-weight: normal; 
    }

    /* 로그아웃 버튼 스타일 */
    .logout-btn-custom button {
        margin-top: 12px;
        padding: 0.5rem 1.2rem !important;
        font-size: 0.85rem !important;
        width: auto !important;
        background-color: #888 !important;
        border-radius: 20px !important;
    }
    .logout-btn-custom button:hover {
        background-color: #666 !important;
    }

    /* 5. [핵심] 탭 높이 고정용 투명 쿠션 (높이 30px) */
    .tab-spacer {
        height: 30px; /* 충분한 높이 확보 */
        width: 100%;
        display: block;
        margin-bottom: 10px;
    }

    /* 6. 기타 UI 요소 */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        background-color: #5D9CEC; 
        color: white;
        border: none;
        padding: 0.8rem 0;
    }
    .stButton>button:hover { background-color: #4A89DC; }

    [data-testid="stMetricValue"] { font-size: 2.4rem; font-weight: 800; color: #5D9CEC; }
    
    .realtime-badge {
        background-color: #FFF0F0; color: #FF6B6B;
        padding: 5px 10px; border-radius: 8px;
        font-size: 0.8rem; font-weight: 700;
        display: inline-block;
        margin-bottom: 5px;
    }

    .stTabs [data-baseweb="tab-list"] { gap: 5px; margin-bottom: 0px; }
    .stTabs [data-baseweb="tab"] { height: 45px; border-radius: 10px 10px 0 0; font-weight: 700; font-size: 0.9rem; }
    .stTabs [aria-selected="true"] { color: #5D9CEC !important; background-color: #F0F8FF !important; }
    
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. 구글 드라이브 인증 (기존 유지)
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
            
            monthly_files.sort(key=lambda x: x['name'], reverse=True)
            return user_db_id, renewal_id, realtime_id, monthly_files
        except:
            time.sleep(1)
            continue
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
# 3. 데이터 파싱 (기존 유지)
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
# 4. 메인 로직
# ==============================================================================
user_db_id, renewal_id, realtime_id, monthly_files = get_all_files()

if not user_db_id:
    st.error("시스템 초기화 오류: user_db.json 없음")
    st.stop()

if 'user_db' not in st.session_state:
    st.session_state.user_db = load_json_file(user_db_id)
    st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}

if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    st.markdown('<div class="login-title">옥션원 서울지사<br>연차확인</div>', unsafe_allow_html=True)
    with st.form("login"):
        uid = st.text_input("아이디").replace(" ", "")
        upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if uid in st.session_state.user_db and st.session_state.user_db[uid]['pw'] == upw:
                st.session_state.login_status = True; st.session_state.user_id = uid; st.rerun()
            else: st.error("로그인 정보 확인")
else:
    uid = st.session_state.user_id
    uinfo = st.session_state.user_db.get(uid, {})
    
    if uinfo.get('first_login', True):
        st.info(f"👋 {uid}님, 비밀번호를 변경해주세요.")
        with st.form("fc"):
            p1 = st.text_input("새 비밀번호", type="password")
            p2 = st.text_input("확인", type="password")
            if st.form_submit_button("변경"):
                if p1 == p2 and p1:
                    st.session_state.user_db[uid].update({"pw": p1, "first_login": False})
                    save_user_db(user_db_id, st.session_state.user_db)
                    st.success("변경 완료. 재로그인 해주세요.")
                    for k in list(st.session_state.keys()): del st.session_state[k]
                    st.rerun()
                else: st.error("비밀번호 불일치")
    else:
        # [레이아웃] 텍스트 55% (중앙정렬), 이미지 45% (높이 제한 없음)
        st.markdown(f"""
        <div class="header-wrapper">
            <div class="header-text-part">
                <div class="greeting-main">반갑습니다,</div>
                <div class="name-highlight">{uid} {uinfo.get('title','')}님 👋</div>
                <span class="greeting-sub">오늘도 좋은 하루 되세요.</span>
                <div class="logout-btn-custom">
                    </div>
            </div>
            <div class="header-img-part">
                <img src="https://raw.githubusercontent.com/leramidkei/auction1-PTO-Check/main/character.png" class="custom-char-img">
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("로그아웃", key="logout_top"): 
            st.session_state.login_status = False
            st.rerun()
        
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
        
        # [탭 고정용] 모든 탭의 맨 위에 30px 투명 쿠션을 깔아줌
        spacer_html = '<div class="tab-spacer"></div>'

        with tab1:
            st.markdown(spacer_html, unsafe_allow_html=True)
            if monthly_files:
                latest_file = monthly_files[0]
                df = fetch_excel(latest_file['id'])
                
                realtime_applied = False
                realtime_usage = 0.0
                realtime_msg = ""
                
                try:
                    file_month = int(re.search(r'(\d+)월', latest_file['name']).group(1))
                    current_month = datetime.datetime.now().month
                    
                    if current_month > file_month and uid in st.session_state.realtime_data:
                        rt_info = st.session_state.realtime_data[uid]
                        realtime_usage = rt_info.get('used', 0.0)
                        realtime_msg = rt_info.get('details', '')
                        realtime_applied = True
                except: pass

                if not df.empty:
                    me = df[df['이름'] == uid]
                    if not me.empty:
                        excel_remain = float(me.iloc[0]['잔여'])
                        
                        if realtime_applied and realtime_usage > 0:
                            final_remain = excel_remain - realtime_usage
                            st.markdown(f"<span class='realtime-badge'>📉 실시간 사용 -{realtime_usage}개 반영됨</span>", unsafe_allow_html=True)
                            st.metric("현재 예상 잔여 연차", f"{final_remain}개")
                            st.caption(f"기준: {latest_file['name']} 잔여 ({excel_remain}) - 이번달 사용 ({realtime_usage})")
                            if realtime_msg: st.info(f"📝 **이번달 추가 내역:** {realtime_msg}")
                        else:
                            st.metric("현재 잔여 연차", f"{excel_remain}개")
                            st.caption(f"기준 파일: {latest_file['name']}")
                    else: st.warning("데이터 없음")
            else: st.error("파일 없음")

        with tab2:
            st.markdown(spacer_html, unsafe_allow_html=True)
            if monthly_files:
                opts = {f['name']: f['id'] for f in monthly_files}
                # 라벨 숨겨서 높이 절약 + 스페이서로 높이 맞춤
                sel = st.selectbox("월 선택", list(opts.keys()), label_visibility="collapsed")
                if sel:
                    df = fetch_excel(opts[sel])
                    me = df[df['이름'] == uid]
                    if not me.empty:
                        r = me.iloc[0]
                        c1, c2 = st.columns(2)
                        c1.metric("사용", f"{r['사용개수']}개")
                        c2.metric("잔여", f"{r['잔여']}개")
                        st.info(f"내역: {r['사용내역']}")

        with tab3:
            st.markdown(spacer_html, unsafe_allow_html=True)
            if renewal_id:
                df = fetch_excel(renewal_id, True)
                me = df[df['이름'] == uid]
                if not me.empty:
                    r = me.iloc[0]
                    try:
                        rdt = pd.to_datetime(r['갱신일'])
                        now = pd.to_datetime(datetime.datetime.now().strftime("%Y-%m-%d"))
                        if rdt > now: st.info(f"📅 **{r['갱신일']}** 갱신 예정")
                        else: st.success(f"✅ **{r['갱신일']}** 갱신 완료")
                    except: st.write(f"📅 {r['갱신일']}")
                    st.metric("추가 발생", f"+{r['갱신개수']}개")
            else: st.info("정보 없음")

        with tab4:
            st.markdown(spacer_html, unsafe_allow_html=True)
            st.write("비밀번호 변경")
            with st.form("pw_chg"):
                p1 = st.text_input("새 비번", type="password")
                p2 = st.text_input("확인", type="password")
                if st.form_submit_button("저장"):
                    if p1 == p2 and p1:
                        st.session_state.user_db[uid]['pw'] = p1
                        save_user_db(user_db_id, st.session_state.user_db)
                        st.success("저장 완료")
                    else: st.error("불일치")
        
        if uinfo.get('role') == 'admin':
            with st.expander("🔐 관리자"): st.json(st.session_state.user_db)
