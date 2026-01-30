import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io

# ==============================================================================
# 1. 환경 설정 및 인증
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered")

try:
    # Secrets에서 폴더 ID만 가져오면 됩니다. (갱신 파일 ID는 자동 검색)
    FOLDER_ID = st.secrets["FOLDER_ID"]
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
except:
    st.error("Secrets 설정 오류: FOLDER_ID 또는 gcp_service_account가 없습니다.")
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

# ==============================================================================
# 2. 파일 자동 검색 및 로딩 (업그레이드됨)
# ==============================================================================
@st.cache_data(ttl=600)
def get_files_in_folder():
    """지정된 폴더 안의 모든 엑셀 파일을 스캔하여 분류합니다."""
    service = get_drive_service()
    if not service: return None, []

    # 폴더 안의 엑셀 파일 검색
    query = f"'{FOLDER_ID}' in parents and trashed=false and name contains '.xlsx'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    all_files = results.get('files', [])

    monthly_files = []
    renewal_file_id = None

    for f in all_files:
        # 파일명이 'renewal' 또는 '갱신'을 포함하면 갱신 정보 파일로 인식
        if "renewal" in f['name'] or "갱신" in f['name']:
            renewal_file_id = f['id']
        else:
            # 나머지는 월별 데이터로 간주
            monthly_files.append(f)
    
    # 월별 파일은 이름 역순 정렬 (최신 날짜가 위로)
    monthly_files.sort(key=lambda x: x['name'], reverse=True)
    
    return renewal_file_id, monthly_files

# ... (parse_attendance_excel 함수는 이전과 동일하므로 생략 - 그대로 사용하세요) ...
# (전체 코드를 복사하실 때 이전에 드린 parse_attendance_excel 함수를 여기에 꼭 넣어주세요!)
def parse_attendance_excel(file_content):
    # [이전 답변의 V3.0 코드에 있는 파싱 로직을 그대로 사용]
    try:
        df = pd.read_excel(file_content, header=2)
        date_cols = [c for c in df.columns if str(c).isdigit() and 1 <= int(str(c)) <= 31]
        parsed_data = []
        for i in range(len(df)):
            row = df.iloc[i]
            name = row.get('성명')
            if pd.notna(name) and str(name).strip() != "":
                usage_details = []
                used_count = 0.0
                for d_col in date_cols:
                    val = str(row[d_col]).strip()
                    if "연차" in val:
                        usage_details.append(f"{d_col}일(연차)")
                        used_count += 1.0
                    elif "반차" in val:
                        usage_details.append(f"{d_col}일(반차)")
                        used_count += 0.5
                usage_text = ", ".join(usage_details) if usage_details else "-"
                remain = row.get('연차잔여일')
                if pd.isna(remain) and (i + 1 < len(df)):
                    next_row = df.iloc[i+1]
                    remain = next_row.get('연차잔여일')
                if pd.isna(remain): remain = 0.0
                parsed_data.append({
                    '이름': str(name).strip(),
                    '사용내역': usage_text,
                    '이번달사용개수': used_count,
                    '잔여연차': float(remain)
                })
        return pd.DataFrame(parsed_data)
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_excel_by_id(file_id, is_renewal=False):
    service = get_drive_service()
    if not service: return pd.DataFrame()
    
    request = service.files().get_media(fileId=file_id)
    file_content = io.BytesIO(request.execute())
    
    if is_renewal:
        # 갱신 파일은 1번째 줄(header=0)이 헤더
        return pd.read_excel(file_content, header=0)
    else:
        return parse_attendance_excel(file_content)

# ==============================================================================
# 3. 메인 앱 로직
# ==============================================================================
# (로그인 및 사용자 DB 부분은 이전과 동일)
if 'user_db' not in st.session_state:
    st.session_state.user_db = {
        "김상호": {"pw": "1234", "과장": "admin", "first_login": True},
        "정다은": {"pw": "1234", "관리이사": "s-user", "first_login": True},
        "고정융": {"pw": "1234", "관리이사": "user", "first_login": True},
        "강원길": {"pw": "1234", "팀장": "user", "first_login": True},
        "김사길": {"pw": "1234", "팀장": "user", "first_login": True},
        "문경남": {"pw": "1234", "과장": "user", "first_login": True},
        "최향자": {"pw": "1234", "과장": "user", "first_login": True},
        "김강민": {"pw": "1234", "사원": "user", "first_login": True},
        "김동준": {"pw": "1234", "사원": "user", "first_login": True},
        # ... 추가
    }
if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    # (로그인 UI 코드 동일)
    st.title("🏢 옥션원 연차확인")
    with st.form("login"):
        uid = st.text_input("아이디"); upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if uid in st.session_state.user_db and st.session_state.user_db[uid]['pw'] == upw:
                st.session_state.login_status = True; st.session_state.user_id = uid; st.rerun()
            else: st.error("로그인 실패")

else:
    user_id = st.session_state.user_id
    # (비밀번호 변경 로직 동일 - 생략)
    
    # --- 파일 가져오기 ---
    renewal_id, monthly_files = get_files_in_folder()
    
    if not monthly_files:
        st.error("폴더에 월별 데이터 파일이 없습니다.")
        st.stop()
        
    latest_file = monthly_files[0]
    
    # 탭 메뉴
    tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여 연차", "📅 월별 사용", "🔄 갱신 정보", "⚙️ 설정"])
    
    with tab1:
        st.caption(f"기준: {latest_file['name']}")
        df = load_excel_by_id(latest_file['id'])
        if not df.empty:
            me = df[df['이름'] == user_id]
            if not me.empty:
                st.metric("현재 잔여 연차", f"{me.iloc[0]['잔여연차']}개")
            else: st.warning("정보 없음")
            
    with tab2:
        opts = {f['name']: f['id'] for f in monthly_files}
        sel = st.selectbox("월 선택", list(opts.keys()))
        if sel:
            df = load_excel_by_id(opts[sel])
            me = df[df['이름'] == user_id]
            if not me.empty:
                row = me.iloc[0]
                st.metric("해당 월 사용", f"{row['이번달사용개수']}개")
                st.info(f"내역: {row['사용내역']}")
    
    with tab3:
        if renewal_id:
            df = load_excel_by_id(renewal_id, is_renewal=True)
            me = df[df['이름'] == user_id]
            if not me.empty:
                st.metric("갱신 개수", f"{me.iloc[0]['갱신개수']}개")
        else:
            st.info("갱신 정보 파일(renewal_info.xlsx)이 폴더에 없습니다.")
            
    with tab4:

        st.write("정보수정 탭")
