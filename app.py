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

# ==============================================================================
# 1. 페이지 설정 및 CSS
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered")

st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f0f2f5; }
    .block-container {
        max-width: 450px;
        padding: 5rem 1rem 2rem 1rem;
        margin: auto;
        background-color: #ffffff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        min-height: 100vh;
    }
    @media (max-width: 450px) { 
        .block-container { max-width: 100%; box-shadow: none; padding-top: 4rem; } 
    }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    [data-testid="stMetricValue"] { font-size: 32px; color: #1f77b4; }
    /* 실시간 배지 스타일 */
    .realtime-badge {
        background-color: #ffeeba;
        color: #856404;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
        margin-bottom: 5px;
        display: inline-block;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. 구글 드라이브 인증 및 파일 관리
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
# 3. 데이터 파싱 로직
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
    # 실시간 데이터 로드
    st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}

if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    st.title("🏢 옥션원 서울지사")
    st.subheader("연차 확인 시스템")
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
                if p1 and p1 == p2:
                    st.session_state.user_db[uid].update({"pw": p1, "first_login": False})
                    save_user_db(user_db_id, st.session_state.user_db)
                    st.success("변경 완료. 재로그인 해주세요.")
                    for k in list(st.session_state.keys()): del st.session_state[k]
                    st.rerun()
                else: st.error("비밀번호 불일치")
    else:
        st.write("")
        c1, c2 = st.columns([3, 1])
        with c1: st.markdown(f"#### 👋 반갑습니다,\n### **{uid} {uinfo.get('title','')}**님")
        with c2: 
            st.write("")
            if st.button("로그아웃"): st.session_state.login_status = False; st.rerun()
        st.divider()
        
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
        
        with tab1:
            if monthly_files:
                latest_file = monthly_files[0]
                df = fetch_excel(latest_file['id'])
                
                # [핵심] 실시간 데이터 반영 로직
                realtime_applied = False
                realtime_usage = 0.0
                realtime_msg = ""
                
                # 파일명에서 월 추출 (예: '2026_1월' -> 1)
                try:
                    file_month = int(re.search(r'(\d+)월', latest_file['name']).group(1))
                    current_month = datetime.datetime.now().month
                    
                    # 현재 월이 파일 월보다 크고, 실시간 데이터가 있으면 반영
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
