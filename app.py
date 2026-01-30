import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import json

# ==============================================================================
# 1. 환경 설정 및 인증
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered")

try:
    FOLDER_ID = st.secrets["FOLDER_ID"]
    SCOPES = ['https://www.googleapis.com/auth/drive'] # 읽기/쓰기 권한 필요
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
# 2. 파일 자동 검색 및 유저 DB 관리 (핵심 변경 사항)
# ==============================================================================
def get_files_in_folder():
    service = get_drive_service()
    if not service: return None, None, []

    # 모든 파일 검색
    query = f"'{FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    all_files = results.get('files', [])

    monthly_files = []
    renewal_file_id = None
    user_db_file_id = None

    for f in all_files:
        name = f['name']
        if name == "user_db.json":
            user_db_file_id = f['id']
        elif "renewal" in name or "갱신" in name:
            renewal_file_id = f['id']
        elif ".xlsx" in name:
            monthly_files.append(f)
    
    monthly_files.sort(key=lambda x: x['name'], reverse=True)
    return user_db_file_id, renewal_file_id, monthly_files

# --- 유저 DB 읽기 ---
def load_user_db_from_drive(file_id):
    if not file_id: return {}
    service = get_drive_service()
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO(request.execute())
        return json.load(file_content)
    except Exception as e:
        st.error(f"유저 DB 로딩 실패: {e}")
        return {}

# --- 유저 DB 저장 (비밀번호 변경 시 호출) ---
def save_user_db_to_drive(file_id, data_dict):
    service = get_drive_service()
    try:
        # 딕셔너리를 JSON 문자열로 변환
        json_str = json.dumps(data_dict, indent=2, ensure_ascii=False)
        # 바이너리 스트림으로 변환
        media = MediaIoBaseUpload(io.BytesIO(json_str.encode('utf-8')), mimetype='application/json')
        # 구글 드라이브 파일 업데이트
        service.files().update(fileId=file_id, media_body=media).execute()
        return True
    except Exception as e:
        st.error(f"저장 실패: {e}")
        return False

# ==============================================================================
# 3. 엑셀 파싱 로직 (이전 버전 유지)
# ==============================================================================
def parse_attendance_excel(file_content):
    try:
        df_raw = pd.read_excel(file_content, header=None)
        name_row_idx = -1
        for i, row in df_raw.iterrows():
            if any("성명" in str(x).replace(" ", "") for x in row.astype(str).values):
                name_row_idx = i; break
        if name_row_idx == -1: return pd.DataFrame()

        remain_col_idx = -1
        rows_to_check = [name_row_idx, name_row_idx + 1]
        for r_idx in rows_to_check:
            if r_idx < len(df_raw):
                for c_idx, val in enumerate(df_raw.iloc[r_idx]):
                    if "연차잔여일" in str(val).replace(" ", ""):
                        remain_col_idx = c_idx; break
            if remain_col_idx != -1: break
        
        file_content.seek(0)
        df = pd.read_excel(file_content, header=name_row_idx)
        df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
        date_cols = [c for c in df.columns if c.isdigit() and 1 <= int(c) <= 31]
        
        parsed_data = []
        for i in range(len(df)):
            row = df.iloc[i]
            name = row.get('성명')
            if pd.notna(name) and str(name).strip() != "":
                clean_name = str(name).replace(" ", "").strip()
                usage_details = []
                used_count = 0.0
                for d_col in date_cols:
                    val = str(row[d_col]).strip()
                    if "연차" in val: usage_details.append(f"{d_col}일(연차)"); used_count += 1.0
                    elif "반차" in val: usage_details.append(f"{d_col}일(반차)"); used_count += 0.5
                usage_text = ", ".join(usage_details) if usage_details else "-"
                
                remain = 0.0
                if remain_col_idx != -1 and i + 1 < len(df):
                    try: remain = float(df.iloc[i+1, remain_col_idx])
                    except: remain = 0.0
                else:
                    remain_val = row.get('연차잔여일')
                    if pd.isna(remain_val) and (i+1 < len(df)): remain_val = df.iloc[i+1].get('연차잔여일')
                    try: remain = float(remain_val)
                    except: remain = 0.0
                if pd.isna(remain): remain = 0.0

                parsed_data.append({'이름': clean_name, '사용내역': usage_text, '이번달사용개수': used_count, '잔여연차': float(remain)})
        return pd.DataFrame(parsed_data)
    except: return pd.DataFrame()

@st.cache_data(ttl=600)
def load_excel_by_id(file_id, is_renewal=False):
    service = get_drive_service()
    if not service: return pd.DataFrame()
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO(request.execute())
        if is_renewal: return pd.read_excel(file_content)
        else: return parse_attendance_excel(file_content)
    except: return pd.DataFrame()

# ==============================================================================
# 4. 메인 앱 로직
# ==============================================================================

# 파일 정보 먼저 로드 (user_db 파일 ID 필요)
user_db_id, renewal_id, monthly_files = get_files_in_folder()

if not user_db_id:
    st.error("🚨 'user_db.json' 파일이 구글 드라이브 폴더에 없습니다. 파일을 업로드해주세요.")
    st.stop()

# 세션에 user_db 로드 (최초 1회 또는 업데이트 필요 시)
if 'user_db' not in st.session_state:
    st.session_state.user_db = load_user_db_from_drive(user_db_id)

if 'login_status' not in st.session_state: st.session_state.login_status = False

if not st.session_state.login_status:
    st.title("🏢 옥션원 연차확인")
    with st.form("login"):
        uid = st.text_input("아이디")
        upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인"):
            clean_uid = uid.replace(" ", "")
            if clean_uid in st.session_state.user_db and st.session_state.user_db[clean_uid]['pw'] == upw:
                st.session_state.login_status = True
                st.session_state.user_id = clean_uid
                st.rerun()
            else: st.error("로그인 정보가 올바르지 않습니다.")
else:
    user_id = st.session_state.user_id
    user_info = st.session_state.user_db[user_id]
    user_role = user_info.get('role', 'user')
    # [변경점] 직급 정보 가져오기 (없으면 공란)
    user_title = user_info.get('title', '') 
    
    # 1. 초기 비밀번호 변경 (변경 시 구글 드라이브에 저장)
    if user_info.get('first_login', False):
        st.warning("초기 비밀번호를 변경해주세요.")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("변경"):
            # 세션 업데이트
            st.session_state.user_db[user_id]['pw'] = new_pw
            st.session_state.user_db[user_id]['first_login'] = False
            
            # [중요] 구글 드라이브 파일 업데이트
            if save_user_db_to_drive(user_db_id, st.session_state.user_db):
                st.success("비밀번호가 안전하게 저장되었습니다. 다시 로그인해주세요.")
                st.session_state.login_status = False
                st.rerun()
            else:
                st.error("저장 중 오류가 발생했습니다.")
    
    # 2. 메인 화면
    else:
        # [변경점] 환영 메시지에 직급 표시
        st.markdown(f"### 👋 **{user_id} {user_title}**님 환영합니다.")
        
        if st.button("로그아웃"):
            st.session_state.login_status = False; st.rerun()
        
        if not monthly_files:
            st.error("📂 폴더에 월별 엑셀 파일이 없습니다.")
            st.stop()
            
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여 연차", "📅 월별 사용", "🔄 갱신 정보", "⚙️ 정보수정"])
        
        with tab1:
            latest_file = monthly_files[0]
            st.caption(f"기준 파일: {latest_file['name']}")
            df = load_excel_by_id(latest_file['id'])
            if not df.empty and '이름' in df.columns:
                me = df[df['이름'] == user_id.replace(" ", "")]
                if not me.empty: st.metric("현재 잔여 연차", f"{me.iloc[0]['잔여연차']}개")
                else: st.warning(f"데이터 없음 ({user_id})")
            else: st.error("데이터 읽기 실패")

        with tab2:
            opts = {f['name']: f['id'] for f in monthly_files}
            sel = st.selectbox("월 선택", list(opts.keys()))
            if sel:
                df = load_excel_by_id(opts[sel])
                if not df.empty and '이름' in df.columns:
                    me = df[df['이름'] == user_id.replace(" ", "")]
                    if not me.empty:
                        row = me.iloc[0]
                        c1, c2 = st.columns(2)
                        c1.metric("사용 개수", f"{row['이번달사용개수']}개")
                        c2.metric("월말 잔여", f"{row['잔여연차']}개")
                        st.info(f"내역: {row['사용내역']}")
                    else: st.warning("데이터 없음")

        with tab3:
            if renewal_id:
                df = load_excel_by_id(renewal_id, is_renewal=True)
                if not df.empty and '이름' in df.columns:
                    me = df[df['이름'] == user_id]
                    if not me.empty: st.metric("갱신 개수", f"{me.iloc[0]['갱신개수']}개")
            else: st.info("갱신 파일 없음")

        with tab4:
            new_p = st.text_input("새로운 비밀번호", type="password", key="new_p")
            if st.button("변경하기"):
                st.session_state.user_db[user_id]['pw'] = new_p
                # [중요] 변경 시 드라이브에 저장
                if save_user_db_to_drive(user_db_id, st.session_state.user_db):
                    st.success("변경 및 저장 완료")
                else:
                    st.error("저장 실패")

        if user_role == 'admin':
            st.divider()
            with st.expander("개발자용: 현재 유저 DB 확인"):
                st.json(st.session_state.user_db)
