# [Ver 2.9] 옥션원 서울지사 연차확인 시스템 (User Solution Applied)
# Update: 2026-02-01
# Changes: 
# - [Tab Fix] '월별', '설정' 탭에만 상단 스페이서(15px) 추가하여 높이 밸런스 맞춤 (User Idea)
# - [CSS] 관리자 토글 버튼 강제 중앙 정렬 코드 강화
# - [Settings] 저장/로그아웃 버튼 현상 유지

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
import calendar

# ==============================================================================
# 1. 페이지 설정 및 CSS (Ver 2.9)
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered", page_icon="🌸")

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    
    [data-testid="stAppViewContainer"] { background-color: #F8F9FA; font-family: 'Pretendard', sans-serif; }

    .block-container {
        max-width: 480px; padding-top: 4rem; padding-bottom: 5rem;
        padding-left: 1.0rem; padding-right: 1.0rem;
        margin: auto; background-color: #ffffff;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); border-radius: 24px; min-height: 95vh;
    }

    /* 로그인 화면 */
    .login-header { text-align: center; margin-top: 40px; margin-bottom: 30px; }
    .login-title { font-size: 2.2rem; font-weight: 800; color: #5D9CEC; line-height: 1.3; }
    .login-icon { font-size: 3rem; margin-bottom: 10px; display: block; }

    /* 프로필 카드 */
    .profile-card {
        display: grid; grid-template-columns: 1.4fr 1fr; 
        background-color: #F0F8FF; border-radius: 20px; overflow: hidden;
        margin-bottom: 15px; height: 160px; border: 1px solid #E1E8ED;
    }
    .card-text { padding: 20px; display: flex; flex-direction: column; justify-content: center; }
    .card-image img { width: 100%; height: 100%; object-fit: cover; object-position: top center; }
    .hello-text { font-size: 1rem; color: #555; margin-bottom: 4px; font-weight: 500; }
    .name-text { font-size: 1.6rem; color: #333; font-weight: 900; line-height: 1.3; word-break: keep-all; }
    .name-highlight { color: #5D9CEC; }
    .msg-text { font-size: 0.85rem; color: #777; margin-top: 5px;}

    /* [Ver 2.9 핵심] 관리자 토글 강제 중앙 정렬 CSS */
    /* 토글이 포함된 div를 찾아서 flex 중앙 정렬 강제 적용 */
    div.stToggle {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }
    /* 토글 내부의 라벨(글자)도 중앙 정렬 */
    div.stToggle > label {
        justify-content: center !important;
        width: 100% !important;
        text-align: center !important;
    }
    div.stToggle p {
        font-weight: 700; color: #555;
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

    .renewal-value { font-size: 3rem; color: #5D9CEC; font-weight: 900; text-align: center; margin-top: 10px; }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; margin-bottom: 0px; }
    .stTabs [data-baseweb="tab"] { height: 44px; border-radius: 12px; font-weight: 700; flex: 1; }
    .stTabs [aria-selected="true"] { color: #5D9CEC !important; background-color: #F0F8FF !important; }
    
    .tab-section-header {
        font-size: 1rem; font-weight: 700; color: #495057; margin-bottom: 15px;
        padding-left: 5px; border-left: 4px solid #5D9CEC; height: 24px; display: flex; align-items: center;
    }

    /* 버튼 스타일 */
    .stButton button {
        border-radius: 10px; font-weight: 700; font-size: 0.9rem; padding: 0.7rem 0; width: 100%;
    }
    /* 저장 버튼 */
    div[data-testid="column"]:nth-of-type(1) .stButton button {
        background-color: #5D9CEC !important; color: white !important; border: none;
    }
    /* 로그아웃 버튼 */
    div[data-testid="column"]:nth-of-type(2) .stButton button {
        background-color: #f1f3f5 !important; color: #868e96 !important; border: 1px solid #dee2e6 !important;
    }

    .version-badge { text-align: right; color: #adb5bd; font-size: 0.75rem; font-weight: 600; margin-bottom: 5px; }
    .realtime-badge { background-color: #FFF0F0; color: #FF6B6B; padding: 5px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 800; display: inline-block; margin-bottom: 10px; }
    .stTextInput input { text-align: center; }
    .viewing-alert {
        background-color: #fff3cd; color: #856404; padding: 8px; border-radius: 8px; 
        text-align: center; font-size: 0.85rem; font-weight: bold; margin-bottom: 15px; border: 1px solid #ffeeba;
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
# 4. 메인 로직 (Ver 2.9)
# ==============================================================================
user_db_id, renewal_id, realtime_id, monthly_files = get_all_files()

if not st.session_state.get('login_status'):
    st.markdown("""
        <div class="login-header">
            <span class="login-icon">🏢</span>
            <div class="login-title">옥션원 서울지사<br>연차확인</div>
        </div>
    """, unsafe_allow_html=True)
    
    with st.container():
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
    
    if 'admin_mode' not in st.session_state: st.session_state.admin_mode = False

    target_uid = login_uid
    if st.session_state.admin_mode and login_uinfo.get('role') == 'admin':
        target_uid = st.session_state.get('impersonate_user', login_uid)

    st.markdown('<div class="version-badge">Ver 2.9</div>', unsafe_allow_html=True)

    # 프로필 카드
    uinfo = st.session_state.user_db.get(target_uid, {})
    admin_uinfo = st.session_state.user_db.get(login_uid, {})

    st.markdown(f"""
    <div class="profile-card">
        <div class="card-text">
            <div class="hello-text">반갑습니다,</div>
            <div class="name-text"><span class="name-highlight" id="target_name_area">{login_uid} {admin_uinfo.get('title','')}</span>님</div>
            <div class="msg-text">오늘도 활기찬 하루 되세요!</div>
        </div>
        <div class="card-image"><img src="https://raw.githubusercontent.com/leramidkei/auction1-PTO-Check/main/character.png"></div>
    </div>
    """, unsafe_allow_html=True)

    # 관리자 토글 (중앙 정렬)
    if login_uinfo.get('role') == 'admin':
        st.markdown('<div class="admin-toggle-container">', unsafe_allow_html=True)
        # CSS 강제 정렬 적용됨
        is_admin = st.toggle("🔧 관리자 모드", key="admin_mode_toggle")
        st.session_state.admin_mode = is_admin
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.admin_mode:
            all_users = list(st.session_state.user_db.keys())
            st.selectbox("조회할 사용자 선택", all_users, index=all_users.index(login_uid), key="impersonate_user")
            
            if target_uid != login_uid:
                st.markdown(f'<div class="viewing-alert">👀 현재 <b>{target_uid}</b>님의 데이터를 조회 중입니다.</div>', unsafe_allow_html=True)
            st.markdown(f"<script>document.getElementById('target_name_area').innerText = '{target_uid} {uinfo.get('title','')}';</script>", unsafe_allow_html=True)

    renewal_df = fetch_excel(renewal_id, True) if renewal_id else pd.DataFrame()
    
    def get_smart_renewal_bonus(uid, base_filename):
        if renewal_df.empty or not base_filename: return 0.0
        me = renewal_df[renewal_df['이름'] == uid]
        if not me.empty:
            try:
                renew_date = pd.to_datetime(me.iloc[0]['갱신일']).date()
                today = datetime.date.today()
                match = re.search(r'(\d{4})_(\d+)', base_filename)
                if match:
                    f_year, f_month = int(match.group(1)), int(match.group(2))
                    last_day = calendar.monthrange(f_year, f_month)[1]
                    file_end_date = datetime.date(f_year, f_month, last_day)
                else: file_end_date = datetime.date(2000, 1, 1)

                if today >= renew_date and renew_date > file_end_date:
                    return float(me.iloc[0]['갱신개수'])
            except: pass
        return 0.0

    def format_leave_num(val):
        if pd.isna(val) or math.isnan(val): return "∞"
        if val % 1 == 0: return f"{int(val)}개" 
        return f"{val}개"

    tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
    
    def tab_header(text):
        st.markdown(f"""<div class="tab-section-header">{text}</div>""", unsafe_allow_html=True)
    
    # [Ver 2.9 핵심] 탭 상단 높이 조절용 스페이서 (15px)
    def tab_spacer():
        st.markdown('<div style="height: 15px;"></div>', unsafe_allow_html=True)

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
        # 잔여 탭: 스페이서 없음
        tab_header("현재 잔여 연차 확인")
        if monthly_files:
            latest_fname = monthly_files[0]['name']
            df = fetch_excel(monthly_files[0]['id'])
            st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}
            
            me = df[df['이름'] == target_uid]
            if not me.empty:
                base_remain = float(me.iloc[0]['잔여'])
                bonus = get_smart_renewal_bonus(target_uid, latest_fname)
                rt_used = 0.0
                rt_msg = ""
                try:
                    file_month = int(re.search(r'(\d+)월', latest_fname).group(1))
                    if datetime.date.today().month > file_month and target_uid in st.session_state.realtime_data:
                        rt_used = st.session_state.realtime_data[target_uid].get('used', 0.0)
                        rt_msg = st.session_state.realtime_data[target_uid].get('details', '')
                except: pass

                if pd.isna(base_remain): final_str = "∞"
                else:
                    total_calc = base_remain + bonus - rt_used
                    final_str = format_leave_num(total_calc)
                    if bonus > 0: st.success(f"🎊 갱신 연차 +{format_leave_num(bonus)} 자동 합산됨")
                    if rt_used > 0: st.markdown(f"<span class='realtime-badge'>📉 실시간 -{format_leave_num(rt_used)} 반영됨</span>", unsafe_allow_html=True)

                render_metric_card("현재 예상 잔여", final_str, "기준 파일", latest_fname, is_main=True)
                if rt_msg: st.info(f"📝 **추가 내역:** {rt_msg}")
            else: st.warning("데이터가 없습니다.")

    with tab2:
        # [Ver 2.9] 월별 탭: 스페이서 추가 (높이 낮추기)
        tab_spacer()
        tab_header("월별 사용 내역 조회")
        opts = {f['name']: f['id'] for f in monthly_files}
        sel = st.selectbox("월 선택", list(opts.keys()), label_visibility="collapsed")
        if sel:
            df = fetch_excel(opts[sel])
            me = df[df['이름'] == target_uid]
            if not me.empty:
                r = me.iloc[0]
                used_str = format_leave_num(float(r['사용개수']))
                remain_str = format_leave_num(float(r['잔여']))
                render_metric_card("이번달 사용", used_str, "당월 잔여", remain_str)
                st.info(f"내역: {r['사용내역']}")

    with tab3:
        # 갱신 탭: 스페이서 없음
        tab_header("연차 갱신 및 발생 내역")
        if not renewal_df.empty:
            me = renewal_df[renewal_df['이름'] == target_uid]
            if not me.empty:
                r = me.iloc[0]
                st.info(f"📅 갱신일: **{r['갱신일']}**")
                add_str = format_leave_num(float(r['갱신개수']))
                st.markdown(f"<div class='renewal-value'>+{add_str}</div>", unsafe_allow_html=True)
                st.markdown("<div style='text-align: center; color: #888; font-size: 0.9rem;'>추가 발생</div>", unsafe_allow_html=True)
        else: st.info("갱신 정보가 없습니다.")

    with tab4:
        # [Ver 2.9] 설정 탭: 스페이서 추가 (높이 낮추기)
        tab_spacer()
        tab_header("설정 및 로그아웃")
        if login_uid != target_uid:
             st.warning(f"⚠️ 관리자 권한으로 **{target_uid}**님의 비밀번호를 변경합니다.")
        
        p1 = st.text_input("새 비번", type="password")
        p2 = st.text_input("확인", type="password")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        c_save, c_logout = st.columns(2)
        with c_save:
            if st.button("저장", use_container_width=True):
                if p1 and p2:
                    if p1 == p2:
                        st.session_state.user_db[target_uid]['pw'] = p1
                        st.session_state.user_db[target_uid]['first_login'] = False
                        save_user_db(user_db_id, st.session_state.user_db)
                        st.success("완료")
                    else: st.error("불일치")
                else: st.error("입력 필요")
        
        with c_logout:
            if st.button("로그아웃", use_container_width=True):
                st.session_state.login_status = False
                st.session_state.admin_mode = False
                st.rerun()
