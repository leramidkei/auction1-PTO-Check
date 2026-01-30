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
import os # 이미지 파일 확인을 위해 추가

# ==============================================================================
# 1. 페이지 설정 및 CSS (파스텔톤 UI & 모바일 최적화)
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered", page_icon="🌸") # 아이콘 추가

st.markdown("""
    <style>
    /* 1. 전체 배경: 화사한 파스텔 블루/핑크 그라데이션 & 폰트 설정 */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); /* 아주 연한 그라데이션 */
        background-color: #F0F8FF; /* 기본 배경색 (AliceBlue) */
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif; /* 깔끔한 폰트 적용 */
        color: #4A4A4A; /* 기본 글자색 */
    }

    /* 2. 메인 컨테이너 박스 디자인 (파스텔톤 & 둥근 모서리 & 그림자) */
    .block-container {
        max-width: 480px; /* 너비 약간 늘림 */
        padding: 3rem 1.5rem 2rem 1.5rem; /* 패딩 조정 */
        margin: auto;
        background-color: #ffffff;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08); /* 더 부드러운 그림자 */
        border-radius: 20px; /* 둥근 모서리 강조 */
        border: 1px solid #E1E1E1; /* 아주 연한 테두리 */
    }
    /* 모바일 환경 최적화 */
    @media (max-width: 480px) { 
        .block-container { 
            max-width: 100%; 
            box-shadow: none; 
            padding-top: 2rem;
            border-radius: 0;
            border: none;
        } 
        /* 모바일에서 폰트 크기 자동 조절 */
        html { font-size: 14px; } 
    }

    /* 3. 로그인 타이틀 스타일 (두 줄, 가운데 정렬, 파스텔톤) */
    .login-title {
        font-size: 1.8rem;
        font-weight: 800;
        color: #5D9CEC; /* 파스텔 블루 */
        text-align: center;
        line-height: 1.4;
        margin-bottom: 1.5rem;
    }
    /* 모바일에서 타이틀 폰트 크기 줄임 */
    @media (max-width: 480px) {
        .login-title {
            font-size: 1.5rem; 
        }
    }

    /* 4. 버튼 스타일 (파스텔 블루 & 둥근 모서리) */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        font-weight: bold;
        background-color: #5D9CEC; /* 파스텔 블루 */
        color: white;
        border: none;
        padding: 0.8rem 1rem;
        transition: background-color 0.3s; /* 부드러운 호버 효과 */
    }
    .stButton>button:hover {
        background-color: #4A89DC; /* 호버 시 약간 진해짐 */
        box-shadow: 0 4px 12px rgba(93, 156, 236, 0.3);
    }

    /* 5. 메트릭(숫자) 스타일 (파스텔톤) */
    [data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 800;
        color: #5D9CEC; /* 파스텔 블루 */
    }
    [data-testid="stMetricLabel"] {
        font-size: 1rem;
        color: #888;
        font-weight: 600;
    }

    /* 6. 실시간 배지 스타일 (파스텔 옐로우/레드) */
    .realtime-badge {
        background-color: #FFF0F0; /* 아주 연한 파스텔 레드 배경 */
        color: #FF6B6B; /* 파스텔 레드 글자 */
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: bold;
        margin-bottom: 8px;
        display: inline-block;
        box-shadow: 0 2px 4px rgba(255, 107, 107, 0.1);
    }

    /* 7. 탭 스타일 (파스텔톤 적용) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f0f2f5;
        padding: 8px;
        border-radius: 16px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 12px;
        color: #888;
        font-weight: 600;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #5D9CEC !important; /* 파스텔 블루 */
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }

    /* 8. 기타 요소 스타일 */
    .stTextInput>div>div>input {
        border-radius: 10px;
        border: 1px solid #E1E1E1;
        padding: 0.8rem;
    }
    .stTextInput>div>div>input:focus {
        border-color: #5D9CEC;
        box-shadow: 0 0 0 2px rgba(93, 156, 236, 0.2);
    }
    .greeting-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.5rem;
    }
    .greeting-text {
        font-size: 1.3rem;
        font-weight: bold;
        line-height: 1.4;
    }
    .user-name-highlight {
        color: #5D9CEC;
        font-size: 1.5rem;
        font-weight: 900;
    }
    .character-img {
        width: 100px;
        height: auto;
        object-fit: contain;
        /* filter: drop-shadow(2px 4px 6px rgba(0,0,0,0.1)); 캐릭터 그림자 추가 (선택) */
    }
    /* 모바일에서 캐릭터 이미지 크기 조절 */
    @media (max-width: 480px) {
        .character-img { width: 80px; }
        .greeting-text { font-size: 1.1rem; }
        .user-name-highlight { font-size: 1.3rem; }
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. 구글 드라이브 인증 및 파일 관리 (기존 코드 유지)
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
                elif name == "realtime_usage.json": realtime_id = f['id'] # 실시간 파일 식별
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
# 3. 데이터 파싱 로직 (기존 코드 유지)
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
# 4. 메인 로직 (UI 및 캐릭터 반영)
# ==============================================================================
user_db_id, renewal_id, realtime_id, monthly_files = get_all_files()

if not user_db_id:
    st.error("시스템 초기화 오류: user_db.json 없음")
    st.stop()

if 'user_db' not in st.session_state:
    st.session_state.user_db = load_json_file(user_db_id)
    # 실시간 데이터 로드
    st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}

if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    # [UI 수정] 로그인 타이틀: 두 줄, 가운데 정렬, 파스텔톤 적용
    st.markdown('<div class="login-title">옥션원 서울지사<br>연차확인</div>', unsafe_allow_html=True)
    with st.form("login"):
        uid = st.text_input("아이디", placeholder="예: 김상호").replace(" ", "") # 플레이스홀더 추가
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
                if p1 and p1 == p2:
                    st.session_state.user_db[uid].update({"pw": p1, "first_login": False})
                    save_user_db(user_db_id, st.session_state.user_db)
                    st.success("변경 완료. 재로그인 해주세요.")
                    for k in list(st.session_state.keys()): del st.session_state[k]
                    st.rerun()
                else: st.error("비밀번호 불일치")
    else:
        # [UI 수정] 메인 화면 헤더 (캐릭터 이미지 + 파스텔톤 인사말)
        # character.png 파일이 깃허브 저장소 루트에 있어야 합니다.
        
        # Flexbox를 사용한 레이아웃 (인사말 왼쪽, 캐릭터 오른쪽)
        header_html = f"""
        <div class="greeting-container">
            <div class="greeting-text">
                반갑습니다,<br>
                <span class="user-name-highlight">{uid} {uinfo.get('title','')}</span>님 👋<br>
                <span style="font-size: 1rem; color: #888; font-weight: normal;">오늘도 좋은 하루 되세요.</span>
            </div>
            <img src="https://raw.githubusercontent.com/leramidkei/auction1-PTO-Check/main/character.png" class="character-img" alt="캐릭터">
        </div>
        """
        # [중요] 위 img src 주소를 본인의 깃허브 저장소 주소로 꼭 맞춰주세요!
        # 만약 로컬 테스트 중이라면 st.image("character.png")를 사용해도 됩니다.
        
        # 깃허브 배포 환경을 고려하여 raw.githubusercontent.com 주소 사용을 권장합니다.
        # 만약 로컬에서만 테스트한다면 아래 코드를 주석 해제하고 위 header_html을 주석 처리하세요.
        
        # c1, c2 = st.columns([3, 1])
        # with c1: 
        #     st.markdown(f"""
        #     <div class="greeting-text">
        #         반갑습니다,<br>
        #         <span class="user-name-highlight">{uid} {uinfo.get('title','')}</span>님 👋<br>
        #         <span style="font-size: 1rem; color: #888; font-weight: normal;">오늘도 좋은 하루 되세요.</span>
        #     </div>
        #     """, unsafe_allow_html=True)
        # with c2:
        #     if os.path.exists("character.png"):
        #         st.image("character.png", width=100)
        #     else:
        #         st.write("😎") # 이미지 없을 시 대체
        
        st.markdown(header_html, unsafe_allow_html=True) # Flexbox 레이아웃 적용

        st.write("") # 간격 추가
        if st.button("로그아웃", key="logout_btn"): st.session_state.login_status = False; st.rerun()
        st.divider()
        
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
        
        with tab1:
            if monthly_files:
                latest_file = monthly_files[0]
                df = fetch_excel(latest_file['id'])
                
                # [핵심] 실시간 데이터 반영 로직 (기존 코드 유지)
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
                            # [UI 수정] 뱃지 스타일 적용 (파스텔 레드)
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
            if monthly_files:
                opts = {f['name']: f['id'] for f in monthly_files}
                sel = st.selectbox("월 선택", list(opts.keys()))
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

