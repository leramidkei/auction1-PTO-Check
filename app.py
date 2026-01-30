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
# 2. 파일 자동 검색 및 로딩 (이름 공백 무시 기능 추가)
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
    try:
        # 1. 일단 전체를 읽어서 '성명'이 있는 줄(Title Row) 찾기
        df_raw = pd.read_excel(file_content, header=None)
        
        name_row_idx = -1
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).values
            if any("성명" in str(x).replace(" ", "") for x in row_str):
                name_row_idx = i
                break
        
        if name_row_idx == -1: return pd.DataFrame()

        # 2. '연차잔여일'이 몇 번째 칸(Column)에 있는지 위치 찾기
        # (보통 '성명' 아랫줄에 숨어있음)
        remain_col_idx = -1
        
        # '성명' 줄과 그 아랫줄을 모두 검사
        rows_to_check = [name_row_idx, name_row_idx + 1]
        
        for r_idx in rows_to_check:
            if r_idx < len(df_raw):
                row_vals = df_raw.iloc[r_idx]
                for c_idx, val in enumerate(row_vals):
                    if "연차잔여일" in str(val).replace(" ", ""):
                        remain_col_idx = c_idx
                        break
            if remain_col_idx != -1: break
        
        # 3. 데이터프레임 제대로 읽기
        file_content.seek(0)
        df = pd.read_excel(file_content, header=name_row_idx)
        
        # 컬럼명 공백 제거
        df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
        date_cols = [c for c in df.columns if c.isdigit() and 1 <= int(c) <= 31]
        
        parsed_data = []
        for i in range(len(df)):
            row = df.iloc[i]
            name = row.get('성명')
            
            if pd.notna(name) and str(name).strip() != "":
                clean_name = str(name).replace(" ", "").strip()
                
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
                
                # B. 잔여 연차 (위치 기반으로 정확히 추출)
                remain = 0.0
                
                # '연차잔여일' 위치를 찾았다면 그 열(Column)을 참조
                if remain_col_idx != -1:
                    # 데이터는 보통 이름이 있는 줄의 '바로 아랫줄'에 있음
                    if i + 1 < len(df):
                        val = df.iloc[i+1, remain_col_idx]
                        # 숫자인지 확인 후 저장
                        try:
                            remain = float(val)
                        except:
                            remain = 0.0
                else:
                    # 못 찾았을 경우 기존 방식(컬럼명) 시도
                    remain_val = row.get('연차잔여일')
                    if pd.isna(remain_val) and (i + 1 < len(df)):
                        remain_val = df.iloc[i+1].get('연차잔여일')
                    try: remain = float(remain_val) 
                    except: remain = 0.0
                
                if pd.isna(remain): remain = 0.0
                
                parsed_data.append({
                    '이름': clean_name,
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
    
    try:
        request = service.files().get_media(fileId=file_id)
        file_content = io.BytesIO(request.execute())
        
        if is_renewal:
            return pd.read_excel(file_content)
        else:
            return parse_attendance_excel(file_content)
    except:
        return pd.DataFrame()

# ==============================================================================
# 3. 메인 앱 로직
# ==============================================================================
if 'user_db' not in st.session_state:
    st.session_state.user_db = {
        # 🔴 [중요] role 항목이 반드시 있어야 합니다!
        "김상호": {"pw": "1234", "과장": "role", "first_login": True},
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
            # 입력한 아이디 공백 제거 후 비교
            clean_uid = uid.replace(" ", "")
            if clean_uid in st.session_state.user_db and st.session_state.user_db[clean_uid]['pw'] == upw:
                st.session_state.login_status = True
                st.session_state.user_id = clean_uid
                st.rerun()
            else: st.error("로그인 정보가 올바르지 않습니다.")
else:
    user_id = st.session_state.user_id
    user_info = st.session_state.user_db[user_id]
    
    # [수정됨] role 정보가 없어도 에러 안 나게 처리
    user_role = user_info.get('role', 'user') 
    
    if user_info['first_login']:
        st.warning("초기 비밀번호를 변경해주세요.")
        new_pw = st.text_input("새 비밀번호", type="password")
        if st.button("변경"):
            st.session_state.user_db[user_id]['pw'] = new_pw
            st.session_state.user_db[user_id]['first_login'] = False
            st.session_state.login_status = False
            st.rerun()
    else:
        st.write(f"👋 **{user_id}**님 환영합니다.")
        if st.button("로그아웃"):
            st.session_state.login_status = False; st.rerun()
            
        renewal_id, monthly_files = get_files_in_folder()
        
        if not monthly_files:
            st.error("📂 폴더에 엑셀 파일이 없습니다.")
            st.stop()
            
        tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여 연차", "📅 월별 사용", "🔄 갱신 정보", "⚙️ 정보수정"])
        
        # --- 탭1: 잔여 연차 ---
        with tab1:
            latest_file = monthly_files[0]
            st.caption(f"기준 파일: {latest_file['name']}")
            df = load_excel_by_id(latest_file['id'])
            
            if not df.empty and '이름' in df.columns:
                # [수정됨] 이름 비교 시 공백 무시
                me = df[df['이름'] == user_id.replace(" ", "")]
                if not me.empty:
                    st.metric("현재 잔여 연차", f"{me.iloc[0]['잔여연차']}개")
                else:
                    st.warning(f"'{latest_file['name']}' 파일에서 '{user_id}'님의 정보를 찾지 못했습니다.")
            else:
                st.error("데이터를 읽지 못했습니다.")

        # --- 탭2: 월별 확인 ---
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
                    else:
                        st.warning("데이터가 없습니다.")

        # --- 탭3: 갱신 정보 ---
        with tab3:
            if renewal_id:
                df = load_excel_by_id(renewal_id, is_renewal=True)
                if not df.empty and '이름' in df.columns:
                    # 갱신 파일은 단순 엑셀이므로 공백처리 따로 필요할 수 있음
                    # 여기서는 간단히 이름 그대로 매칭 시도
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

        # 관리자 디버깅용 (에러 해결사!)
        if user_role == 'admin':
            st.divider()
            with st.expander("개발자용 데이터 확인 (이름 목록)"):
                if 'df' in locals() and not df.empty:
                    st.write("엑셀에서 읽어온 이름 목록:")
                    # 엑셀에서 컴퓨터가 인식한 이름들을 보여줍니다.
                    st.write(df['이름'].unique())
                    st.write("전체 데이터:")
                    st.dataframe(df)
