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
    FOLDER_ID = st.secrets["FOLDER_ID"]
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
except:
    st.error("Secrets 설정 오류: FOLDER_ID가 설정되지 않았습니다.")
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
# 2. 파일 자동 검색 및 로딩 (스마트 파싱 적용됨)
# ==============================================================================
@st.cache_data(ttl=600)
def get_files_in_folder():
    service = get_drive_service()
    if not service: return None, []

    query = f"'{FOLDER_ID}' in parents and trashed=false and name contains '.xlsx'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    all_files = results.get('files', [])

    monthly_files = []
    renewal_file_id = None

    for f in all_files:
        if "renewal" in f['name'] or "갱신" in f['name']:
            renewal_file_id = f['id']
        else:
            monthly_files.append(f)
    
    monthly_files.sort(key=lambda x: x['name'], reverse=True)
    return renewal_file_id, monthly_files

def parse_attendance_excel(file_content):
    """
    [개선된 로직] '성명' 칸을 자동으로 찾아서 파싱
    """
    try:
        # 1. 일단 헤더 없이 읽어서 '성명'이 있는 줄 찾기
        df_raw = pd.read_excel(file_content, header=None)
        
        header_row_idx = -1
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).values
            # '성명' 또는 '성 명'이 포함된 줄을 찾음
            if any("성명" in str(x).replace(" ", "") for x in row_str):
                header_row_idx = i
                break
        
        if header_row_idx == -1:
            st.error("엑셀 파일에서 '성명' 칸을 찾을 수 없습니다. 양식을 확인해주세요.")
            return pd.DataFrame()

        # 2. 찾은 줄을 헤더로 다시 읽기
        file_content.seek(0) # 파일 커서 초기화
        df = pd.read_excel(file_content, header=header_row_idx)
        
        # 3. 컬럼 이름 공백 제거 (예: "성 명" -> "성명", " 1 " -> "1")
        df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
        
        # 날짜 컬럼(1~31) 찾기
        date_cols = [c for c in df.columns if c.isdigit() and 1 <= int(c) <= 31]
        
        parsed_data = []
        for i in range(len(df)):
            row = df.iloc[i]
            name = row.get('성명') # 이제 공백 없는 '성명' 키 사용
            
            if pd.notna(name) and str(name).strip() != "":
                # A. 사용 내역
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
                
                # B. 잔여 연차 (아랫줄 확인 로직)
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
        
        result_df = pd.DataFrame(parsed_data)
        
        # 결과가 비어있지 않은지 확인
        if result_df.empty:
            st.error("데이터를 추출했으나 비어있습니다. '성명' 열 아래에 데이터가 있는지 확인하세요.")
            
        return result_df

    except Exception as e:
        st.error(f"엑셀 처리 중 오류: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_excel_by_id(file_id, is_renewal=False):
    service = get_drive_service()
    if not service: return pd.DataFrame()
    
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO(request.execute())
        
        if is_renewal:
            return pd.read_excel(file_content)
        else:
            return parse_attendance_excel(file_content)
    except Exception as e:
        st.error(f"파일 다운로드 오류: {e}")
        return pd.DataFrame()

# ==============================================================================
# 3. 메인 앱 로직 (안전장치 추가됨)
# ==============================================================================
if 'user_db' not in st.session_state:
    st.session_state.user_db = {
        # 🔴 여기에 실제 직원 정보를 다시 입력해주세요!
        "김상호": {"pw": "1234", "role": "admin", "first_login": True},
        "정다은": {"pw": "1234", "role": "s-user", "first_login": True},
        "고정융": {"pw": "1234", "role": "user", "first_login": True},
        "강원길": {"pw": "1234", "role": "user", "first_login": True},
        "김사길": {"pw": "1234", "role": "user", "first_login": True},
        "문경남": {"pw": "1234", "role": "user", "first_login": True},
        "최향자": {"pw": "1234", "role": "user", "first_login": True},
        "김강민": {"pw": "1234", "role": "user", "first_login": True},
        "김동준": {"pw": "1234", "role": "user", "first_login": True},
    }

if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    st.title("🏢 옥션원 연차확인")
    with st.form("login"):
        uid = st.text_input("아이디")
        upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            if uid in st.session_state.user_db and st.session_state.user_db[uid]['pw'] == upw:
                st.session_state.login_status = True; st.session_state.user_id = uid; st.rerun()
            else: st.error("로그인 정보가 올바르지 않습니다.")
else:
    user_id = st.session_state.user_id
    user_info = st.session_state.user_db[user_id]
    
    # 1. 비번 변경
    if user_info['first_login']:
        st.warning("초기 비밀번호를 변경해주세요.")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("변경"):
            st.session_state.user_db[user_id]['pw'] = new_pw
            st.session_state.user_db[user_id]['first_login'] = False
            st.session_state.login_status = False
            st.rerun()
    
    # 2. 메인 화면
    else:
        st.write(f"👋 **{user_id}**님 환영합니다.")
        if st.button("로그아웃"):
            st.session_state.login_status = False; st.rerun()
            
        renewal_id, monthly_files = get_files_in_folder()
        
        if not monthly_files:
            st.error("📂 폴더에 엑셀 파일이 없습니다.")
            st.stop()
            
        # 탭 구성
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여 연차", "📅 월별 사용", "🔄 갱신 정보", "⚙️ 정보수정"])
        
        # --- 탭1: 잔여 연차 ---
        with tab1:
            latest_file = monthly_files[0]
            st.caption(f"기준 파일: {latest_file['name']}")
            df = load_excel_by_id(latest_file['id'])
            
            # [안전장치] 데이터프레임에 '이름' 컬럼이 있는지 확인
            if not df.empty and '이름' in df.columns:
                me = df[df['이름'] == user_id]
                if not me.empty:
                    st.metric("현재 잔여 연차", f"{me.iloc[0]['잔여연차']}개")
                else:
                    st.warning(f"'{latest_file['name']}' 파일에 '{user_id}'님의 데이터가 없습니다.")
            else:
                st.error("엑셀 파일 형식을 읽지 못했습니다. (헤더 '성명' 확인 필요)")

        # --- 탭2: 월별 확인 ---
        with tab2:
            opts = {f['name']: f['id'] for f in monthly_files}
            sel = st.selectbox("월 선택", list(opts.keys()))
            if sel:
                df = load_excel_by_id(opts[sel])
                if not df.empty and '이름' in df.columns:
                    me = df[df['이름'] == user_id]
                    if not me.empty:
                        row = me.iloc[0]
                        c1, c2 = st.columns(2)
                        c1.metric("사용 개수", f"{row['이번달사용개수']}개")
                        c2.metric("월말 잔여", f"{row['잔여연차']}개")
                        st.info(f"내역: {row['사용내역']}")
                    else:
                        st.warning("데이터가 없습니다.")
                else:
                    st.warning("데이터를 읽어올 수 없습니다.")

        # --- 탭3: 갱신 정보 ---
        with tab3:
            if renewal_id:
                df = load_excel_by_id(renewal_id, is_renewal=True)
                if not df.empty and '이름' in df.columns:
                    me = df[df['이름'] == user_id]
                    if not me.empty:
                        st.metric("갱신 개수", f"{me.iloc[0]['갱신개수']}개")
            else:
                st.info("갱신 정보 파일이 없습니다.")

        # --- 탭4: 비번 변경 ---
        with tab4:
            new_p = st.text_input("새로운 비밀번호", type="password", key="new_p")
            if st.button("변경하기"):
                st.session_state.user_db[user_id]['pw'] = new_p
                st.success("변경 완료")

        # 관리자 디버깅용 (문제가 계속되면 이 부분을 확인하세요)
        if user_info['role'] == 'admin':
            st.divider()
            with st.expander("개발자용 데이터 확인"):
                if 'df' in locals() and not df.empty:
                    st.write("읽어온 데이터 컬럼:", df.columns.tolist())
                    st.dataframe(df)

