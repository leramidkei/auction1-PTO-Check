import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import json

# ==============================================================================
# 1. 페이지 설정 및 모바일 최적화 UI
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered")

st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] { background-color: #f0f2f5; }
    .block-container {
        max-width: 450px;
        padding: 2rem 1rem;
        margin: auto;
        background-color: #ffffff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        min-height: 100vh;
    }
    @media (max-width: 450px) { .block-container { max-width: 100%; box-shadow: none; } }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
    [data-testid="stMetricValue"] { font-size: 32px; color: #1f77b4; }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. 구글 드라이브 인증 및 파일 관리
# ==============================================================================
try:
    FOLDER_ID = st.secrets["FOLDER_ID"]
    SCOPES = ['https://www.googleapis.com/auth/drive']
except:
    st.error("Secrets 설정(FOLDER_ID 등)이 필요합니다.")
    st.stop()

@st.cache_resource
def get_drive_service():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"구글 인증 실패: {e}")
        return None

def get_all_files():
    service = get_drive_service()
    if not service: return None, None, []
    query = f"'{FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    all_files = results.get('files', [])
    
    user_db_id, renewal_id, monthly_files = None, None, []
    for f in all_files:
        name = f['name']
        if name == "user_db.json": user_db_id = f['id']
        elif "renewal" in name or "갱신" in name: renewal_id = f['id']
        elif ".xlsx" in name: monthly_files.append(f)
    
    monthly_files.sort(key=lambda x: x['name'], reverse=True)
    return user_db_id, renewal_id, monthly_files

def load_user_db(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    return json.load(io.BytesIO(request.execute()))

def save_user_db(file_id, data):
    service = get_drive_service()
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    media = MediaIoBaseUpload(io.BytesIO(json_str.encode('utf-8')), mimetype='application/json')
    service.files().update(fileId=file_id, media_body=media).execute()

# ==============================================================================
# 3. 데이터 파싱 로직 (출근부 및 연차계산표 전용)
# ==============================================================================

# A. 월별 출근부 파서
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

# B. 갱신 연차계산표 파서 (수식 및 연/월/일 조립)
def parse_renewal_excel(file_content):
    try:
        # 케이님의 파일 구조: 4번째 줄(인덱스 3)이 헤더
        df = pd.read_excel(file_content, header=3)
        df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
        
        parsed_renewal = []
        for i, row in df.iterrows():
            # 첫 번째 컬럼(성명) 추출
            name = str(row.iloc[0]).replace(" ", "").strip()
            
            if name and name != "nan" and name != "이름":
                try:
                    # 연, 월, 일 조립하여 갱신일 생성
                    year = int(row['연'])
                    month = int(row['월'])
                    day = int(row['일'])
                    renewal_date = f"{year}-{month:02d}-{day:02d}"
                    
                    # '올해발생연차개수' 컬럼에서 값 추출
                    count = row.get('올해발생연차개수', 0)
                    
                    parsed_renewal.append({
                        '이름': name,
                        '갱신일': renewal_date,
                        '갱신개수': count
                    })
                except:
                    continue
        return pd.DataFrame(parsed_renewal)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_excel(file_id, is_renewal=False):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    content = io.BytesIO(request.execute())
    if is_renewal: return parse_renewal_excel(content)
    return parse_attendance(content)

# ==============================================================================
# 4. 메인 애플리케이션
# ==============================================================================
user_db_id, renewal_id, monthly_files = get_all_files()

if not user_db_id:
    st.error("'user_db.json' 파일이 구글 드라이브 폴더에 없습니다.")
    st.stop()

if 'user_db' not in st.session_state:
    st.session_state.user_db = load_user_db(user_db_id)

if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    st.title("🏢 옥션원 서울지사")
    st.subheader("연차 확인 시스템")
    with st.form("login"):
        uid = st.text_input("아이디 (이름)").replace(" ", "")
        upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if uid in st.session_state.user_db and st.session_state.user_db[uid]['pw'] == upw:
                st.session_state.login_status = True; st.session_state.user_id = uid; st.rerun()
            else: st.error("로그인 정보를 확인하세요.")
else:
    uid = st.session_state.user_id
    uinfo = st.session_state.user_db[uid]
    
    if uinfo.get('first_login', True):
        st.info(f"👋 {uid}님, 비밀번호를 변경해주세요.")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("변경 완료"):
            st.session_state.user_db[uid].update({"pw": new_pw, "first_login": False})
            save_user_db(user_db_id, st.session_state.user_db)
            st.success("변경되었습니다. 다시 로그인해주세요."); st.session_state.login_status = False; st.rerun()
    else:
        st.markdown(f"### 👋 **{uid} {uinfo.get('title','')}**님")
        if st.button("로그아웃"): st.session_state.login_status = False; st.rerun()
        
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
        
        with tab1:
            if monthly_files:
                df = fetch_excel(monthly_files[0]['id'])
                me = df[df['이름'] == uid]
                if not me.empty: st.metric("현재 잔여 연차", f"{me.iloc[0]['잔여']}개")
                else: st.warning("데이터를 찾을 수 없습니다.")
            else: st.error("파일이 없습니다.")

        with tab2:
            opts = {f['name']: f['id'] for f in monthly_files}
            sel = st.selectbox("조회 월 선택", list(opts.keys()))
            if sel:
                df_sel = fetch_excel(opts[sel])
                me_sel = df_sel[df_sel['이름'] == uid]
                if not me_sel.empty:
                    row = me_sel.iloc[0]
                    c1, c2 = st.columns(2)
                    c1.metric("이번달 사용", f"{row['사용개수']}개")
                    c2.metric("말일 기준 잔여", f"{row['잔여']}개")
                    st.info(f"**상세 내역:** {row['사용내역']}")

        with tab3:
            if renewal_id:
                # 케이님의 '연차계산표.xlsx' 구조를 읽어옴
                df_rn = fetch_excel(renewal_id, True)
                me_rn = df_rn[df_rn['이름'] == uid]
                if not me_rn.empty:
                    r = me_rn.iloc[0]
                    st.success(f"📅 **{r['갱신일']}** 갱신 예정")
                    st.metric("추가 발생 연차", f"+{r['갱신개수']}개")
                else: st.info("올해 갱신 정보가 없습니다.")
            else: st.info("갱신 정보 파일이 없습니다.")

        with tab4:
            new_p = st.text_input("비밀번호 변경", type="password")
            if st.button("저장"):
                st.session_state.user_db[uid]['pw'] = new_p
                save_user_db(user_db_id, st.session_state.user_db)
                st.success("비밀번호가 안전하게 저장되었습니다.")
        
        if uinfo.get('role') == 'admin':
            with st.expander("🔐 관리자 전용"):
                st.json(st.session_state.user_db)
