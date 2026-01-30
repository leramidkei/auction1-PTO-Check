# [Ver 1.4] 옥션원 서울지사 연차확인 시스템
# Update: 2026-01-31
# Changes: 
# - 로그인 UI 디자인 원복 (깔끔한 중앙 정렬)
# - 프로필 카드 배경색 복구 (은은한 하늘색)
# - 연차 갱신 로직 고도화 (기준 파일 날짜 vs 갱신일 비교 -> 중복 합산 방지)

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
from dateutil.relativedelta import relativedelta # 날짜 계산용

# ==============================================================================
# 1. 페이지 설정 및 CSS (Ver 1.4)
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered", page_icon="🌸")

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    
    [data-testid="stAppViewContainer"] { background-color: #F8F9FA; font-family: 'Pretendard', sans-serif; }

    /* 메인 컨테이너 */
    .block-container {
        max-width: 480px; padding-top: 3rem; padding-bottom: 5rem;
        padding-left: 1.2rem; padding-right: 1.2rem;
        margin: auto; background-color: #ffffff;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); border-radius: 24px; min-height: 95vh;
    }

    /* [Ver 1.4 복구] 로그인 화면 전용 스타일 */
    .login-container {
        padding: 40px 20px; text-align: center;
    }
    .login-title {
        font-size: 2rem; font-weight: 800; color: #5D9CEC;
        margin-bottom: 40px; margin-top: 20px;
    }

    /* [Ver 1.4 복구] 프로필 카드 (배경색 하늘색) */
    .profile-card {
        display: grid; grid-template-columns: 1.4fr 1fr; 
        background-color: #F0F8FF; /* [복구] 은은한 하늘색 */
        border-radius: 20px; overflow: hidden;
        margin-bottom: 15px; height: 160px; border: 1px solid #E1E8ED;
    }
    .card-text { padding: 20px; display: flex; flex-direction: column; justify-content: center; }
    .card-image img { width: 100%; height: 100%; object-fit: cover; object-position: top center; }
    
    .hello-text { font-size: 1rem; color: #555; margin-bottom: 4px; font-weight: 500; }
    .name-text { font-size: 1.6rem; color: #333; font-weight: 900; line-height: 1.3; word-break: keep-all; }
    .name-highlight { color: #5D9CEC; }
    .msg-text { font-size: 0.85rem; color: #777; margin-top: 5px;}

    /* 관리자 도구 */
    .admin-flex-row {
        display: flex; align-items: center; justify-content: space-between;
        gap: 10px; margin-bottom: 15px;
    }

    /* 메트릭 박스 */
    .metric-box {
        display: flex; justify-content: space-between; align-items: center;
        background-color: #fff; border: 1px solid #eee; border-radius: 16px;
        padding: 22px 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.03); margin-bottom: 20px;
    }
    .metric-item { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .metric-label { font-size: 0.9rem; color: #888; font-weight: 600; margin-bottom: 8px; }
    .metric-value-large { font-size: 2.6rem; color: #5D9CEC; font-weight: 900; line-height: 1; }
    .metric-value-sub { font-size: 1.1rem; color: #000; font-weight: 700; text-align: center; }
    .metric-divider { width: 1px; height: 50px; background-color: #eee; margin: 0 5px; }

    /* 탭 및 기타 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; margin-bottom: 15px; }
    .stTabs [data-baseweb="tab"] { height: 44px; border-radius: 12px; font-weight: 700; flex: 1; }
    .stTabs [aria-selected="true"] { color: #5D9CEC !important; background-color: #F0F8FF !important; }
    .tab-section-header {
        font-size: 1rem; font-weight: 700; color: #495057; margin-bottom: 15px;
        padding-left: 5px; border-left: 4px solid #5D9CEC; height: 24px; display: flex; align-items: center;
    }
    .version-badge { text-align: right; color: #adb5bd; font-size: 0.75rem; font-weight: 600; margin-bottom: 5px; }
    
    .realtime-badge {
        background-color: #FFF0F0; color: #FF6B6B; padding: 5px 12px; border-radius: 20px;
        font-size: 0.8rem; font-weight: 800; display: inline-block; margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==============================================================================
# 2. 구글 드라이브 & 유틸리티
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
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds, cache_discovery=False)
    except: return None

def get_file_sort_key(filename):
    match = re.search(r'(\d{4})_(\d+)', filename)
    if match: return (int(match.group(1)), int(match.group(2)))
    return (0, 0)

def get_all_files():
    service = get_drive_service()
    if not service: return None, None, None, []
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
    except: return None, None, None, []

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

def fetch_excel(file_id, is_renewal=False):
    service = get_drive_service()
    try:
        request = service.files().get_media(fileId=file_id)
        content = io.BytesIO(request.execute())
        if is_renewal:
            df_meta = pd.read_excel(content, header=None, nrows=3)
            try: target_year = int(df_meta.iloc[1, 0])
            except: target_year = datetime.datetime.now().year
            content.seek(0)
            df = pd.read_excel(content, header=3)
            df.columns = df.columns.astype(str).str.replace(" ", "").str.replace("\n", "")
            parsed = []
            for i, row in df.iterrows():
                name = str(row.iloc[0]).replace(" ", "").strip()
                if name and name != "nan" and name != "이름":
                    try:
                        month = int(row['월']); day = int(row['일'])
                        renewal_date = f"{target_year}-{month:02d}-{day:02d}"
                        count = row.get('올해발생연차개수', 0)
                        parsed.append({'이름': name, '갱신일': renewal_date, '갱신개수': float(count)})
                    except: continue
            return pd.DataFrame(parsed)
        else:
            df_raw = pd.read_excel(content, header=None)
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
            content.seek(0)
            df = pd.read_excel(content, header=name_row_idx)
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

# ==============================================================================
# 4. 메인 로직 (Ver 1.4)
# ==============================================================================
user_db_id, renewal_id, realtime_id, monthly_files = get_all_files()

if not st.session_state.get('login_status'):
    # [Ver 1.4] 로그인 화면 디자인 복구
    st.markdown('<div class="login-title">옥션원 서울지사<br>연차확인</div>', unsafe_allow_html=True)
    
    with st.container():
        # 컨테이너 안에서 깔끔하게 정렬
        with st.form("login"):
            uid = st.text_input("아이디", placeholder="이름을 입력하세요").replace(" ", "")
            upw = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button("로그인", use_container_width=True)
            
            if submitted:
                db = load_json_file(user_db_id)
                if uid in db and db[uid]['pw'] == upw:
                    st.session_state.login_status = True; st.session_state.user_id = uid; st.session_state.user_db = db; st.rerun()
                else: st.error("정보를 확인해주세요.")
else:
    login_uid = st.session_state.user_id
    login_uinfo = st.session_state.user_db.get(login_uid, {})
    target_uid = login_uid
    st.markdown('<div class="version-badge">Ver 1.4</div>', unsafe_allow_html=True)

    # 프로필 카드
    uinfo = st.session_state.user_db.get(target_uid, {})
    temp_uinfo = uinfo

    st.markdown(f"""
    <div class="profile-card">
        <div class="card-text">
            <div class="hello-text">반갑습니다,</div>
            <div class="name-text"><span class="name-highlight" id="target_name_area">{target_uid} {temp_uinfo.get('title','')}</span>님</div>
            <div class="msg-text">오늘도 활기찬 하루 되세요!</div>
        </div>
        <div class="card-image"><img src="https://raw.githubusercontent.com/leramidkei/auction1-PTO-Check/main/character.png"></div>
    </div>
    """, unsafe_allow_html=True)

    # 관리자 컨트롤
    if login_uinfo.get('role') == 'admin':
        st.markdown('<div class="admin-flex-row">', unsafe_allow_html=True)
        col_btn, col_tgl = st.columns([1, 1])
        with col_btn:
            if st.button("로그아웃", key="lo"): st.session_state.login_status = False; st.rerun()
        with col_tgl:
            st.toggle("🔧 관리자 모드", key="admin_mode_toggle")
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.get("admin_mode_toggle"):
            all_users = list(st.session_state.user_db.keys())
            target_uid = st.selectbox("사용자 선택", all_users, index=all_users.index(login_uid), key="impersonate_user")
            uinfo = st.session_state.user_db.get(target_uid, {})
            st.markdown(f"<script>document.getElementById('target_name_area').innerText = '{target_uid} {uinfo.get('title','')}';</script>", unsafe_allow_html=True)
    else:
        if st.button("로그아웃"): st.session_state.login_status = False; st.rerun()

    renewal_df = fetch_excel(renewal_id, True) if renewal_id else pd.DataFrame()
    
    # [Ver 1.4 핵심] 연차 중복 방지 로직 (Logic V2)
    def get_smart_renewal_bonus(uid, base_filename):
        if renewal_df.empty or not base_filename: return 0.0
        me = renewal_df[renewal_df['이름'] == uid]
        if not me.empty:
            try:
                # 1. 갱신일 파싱
                renew_date = pd.to_datetime(me.iloc[0]['갱신일']).date()
                today = datetime.date.today()
                
                # 2. 기준 파일 날짜 파싱 (예: 2026_1월 -> 2026-01-31로 간주)
                match = re.search(r'(\d{4})_(\d+)', base_filename)
                if match:
                    f_year, f_month = int(match.group(1)), int(match.group(2))
                    # 해당 월의 마지막 날 계산
                    next_month = datetime.date(f_year, f_month, 28) + datetime.timedelta(days=4)
                    file_end_date = next_month - datetime.timedelta(days=next_month.day)
                else:
                    file_end_date = datetime.date(2000, 1, 1) # 알 수 없음

                # 3. 로직 판정: 
                # (오늘이 갱신일 지남?) AND (기준 파일이 갱신일보다 과거인가?)
                # 예: 갱신 2/1, 파일 1/31 -> True (아직 파일에 반영 안됨 -> 추가)
                # 예: 갱신 1/1, 파일 1/31 -> False (이미 파일에 반영됨 -> 추가 안 함)
                if today >= renew_date and renew_date > file_end_date:
                    return float(me.iloc[0]['갱신개수'])
            except: pass
        return 0.0

    tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
    
    def tab_header(text): st.markdown(f'<div class="tab-section-header">{text}</div>', unsafe_allow_html=True)
    
    def render_metric_card(label1, val1, label2, val2, is_main=False):
        val1_class = "metric-value-large" if is_main else "metric-value-large"
        val2_style = "metric-value-sub" if is_main else "metric-value-large"
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-item"><span class="metric-label">{label1}</span><span class="{val1_class}">{val1}</span></div>
            <div class="metric-divider"></div>
            <div class="metric-item"><span class="metric-label">{label2}</span><span class="{val2_style}">{val2}</span></div>
        </div>
        """, unsafe_allow_html=True)

    with tab1:
        tab_header("현재 잔여 연차 확인")
        if monthly_files:
            latest_fname = monthly_files[0]['name']
            df = fetch_excel(monthly_files[0]['id'])
            st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}
            
            me = df[df['이름'] == target_uid]
            if not me.empty:
                base_remain = float(me.iloc[0]['잔여'])
                
                # [Ver 1.4] 스마트 중복 방지 로직 적용
                bonus = get_smart_renewal_bonus(target_uid, latest_fname)
                
                rt_used = 0.0
                rt_msg = ""
                try:
                    file_month = int(re.search(r'(\d+)월', latest_fname).group(1))
                    if datetime.date.today().month > file_month and target_uid in st.session_state.realtime_data:
                        rt_used = st.session_state.realtime_data[target_uid].get('used', 0.0)
                        rt_msg = st.session_state.realtime_data[target_uid].get('details', '')
                except: pass

                if pd.isna(base_remain):
                    final_str = "∞"
                else:
                    total_calc = base_remain + bonus - rt_used
                    final_str = f"{total_calc}개"
                    if bonus > 0: st.success(f"🎊 갱신 연차 +{bonus}개가 자동 합산되었습니다!")
                    if rt_used > 0: st.markdown(f"<span class='realtime-badge'>📉 실시간 사용 -{rt_used}개 반영됨</span>", unsafe_allow_html=True)

                render_metric_card("현재 예상 잔여", final_str, "기준 파일", latest_fname, is_main=True)
                if rt_msg: st.info(f"📝 **추가 내역:** {rt_msg}")
            else: st.warning("데이터가 없습니다.")

    with tab2:
        tab_header("월별 사용 내역 조회")
        opts = {f['name']: f['id'] for f in monthly_files}
        sel = st.selectbox("월 선택", list(opts.keys()), label_visibility="collapsed")
        if sel:
            df = fetch_excel(opts[sel])
            me = df[df['이름'] == target_uid]
            if not me.empty:
                r = me.iloc[0]
                rem = "∞" if pd.isna(r['잔여']) else f"{r['잔여']}개"
                render_metric_card("이번달 사용", f"{r['사용개수']}개", "당월 잔여", rem)
                st.info(f"내역: {r['사용내역']}")

    with tab3:
        tab_header("연차 갱신 및 발생 내역")
        if not renewal_df.empty:
            me = renewal_df[renewal_df['이름'] == target_uid]
            if not me.empty:
                r = me.iloc[0]
                st.info(f"📅 갱신일: **{r['갱신일']}**")
                st.metric("추가 발생 연차", f"+{r['갱신개수']}개")
        else: st.info("갱신 정보가 없습니다.")

    with tab4:
        tab_header("비밀번호 변경")
        with st.form("pw"):
            p1, p2 = st.text_input("새 비번", type="password"), st.text_input("확인", type="password")
            if st.form_submit_button("저장"):
                if p1 == p2 and p1:
                    st.session_state.user_db[target_uid]['pw'] = p1
                    st.session_state.user_db[target_uid]['first_login'] = False
                    save_user_db(user_db_id, st.session_state.user_db)
                    st.success("변경 완료")
