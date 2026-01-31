# [Ver 4.3] 옥션원 서울지사 연차확인 시스템 (UI Background Fix & Date Format)
# Update: 2026-02-01
# Changes: 
# - [UI Fix] 갱신 탭 숫자(+15개)를 HTML 카드 박스로 감싸서 배경 잘림 현상 완벽 해결
# - [Feature] 월별 사용 내역 날짜 표기 수정: "2일(연차)" -> "1월 2일(연차)"
# - [Text] 월별 탭 제목: "월별 사용 내역 조회 (월말 기준)" 적용
# - [Logic] 김동준 님 특수 규칙 및 기존 보안/시간 기능 유지

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
import hashlib
from dateutil import parser

# ==============================================================================
# 1. 페이지 설정 및 CSS (Ver 4.3)
# ==============================================================================
st.set_page_config(page_title="옥션원 서울지사 연차확인", layout="centered", page_icon="🌸")

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    
    [data-testid="stAppViewContainer"] { background-color: #F8F9FA; font-family: 'Pretendard', sans-serif; }

    .block-container {
        max-width: 480px; 
        padding-top: 3rem; padding-bottom: 5rem;
        padding-left: 1.0rem; padding-right: 1.0rem;
        margin: auto; background-color: #ffffff;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08); border-radius: 24px; min-height: 95vh;
    }

    /* 갱신 연차 숫자 전용 카드 박스 (잘림 방지) */
    .renewal-card {
        background-color: #F0F8FF;
        border: 2px dashed #5D9CEC;
        border-radius: 20px;
        padding: 30px 10px;
        text-align: center;
        margin: 20px 0;
    }
    .renewal-value-text {
        font-size: 3.5rem;
        color: #5D9CEC;
        font-weight: 900;
        line-height: 1;
        display: block;
    }
    .renewal-sub-text {
        font-size: 1rem;
        color: #888;
        font-weight: 600;
        margin-top: 10px;
        display: block;
    }

    /* 탭 헤더 및 레이아웃 */
    .tab-section-header {
        font-size: 1rem; font-weight: 700; color: #495057; margin-bottom: 15px;
        padding-left: 5px; border-left: 4px solid #5D9CEC; height: 24px; display: flex; align-items: center;
    }
    .bottom-spacer { width: 100%; height: 100px !important; display: block; visibility: hidden; }
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

    /* 관리자 토글 및 버튼 */
    .stToggle { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 12px; padding: 12px 0px; margin: 10px 0; display: flex !important; justify-content: center !important; align-items: center !important; }
    .stButton button { border-radius: 10px; font-weight: 700; font-size: 0.9rem; padding: 0.7rem 0; width: 100% !important; }
    div[data-testid="column"]:nth-of-type(1) .stButton button { background-color: #5D9CEC !important; color: white !important; border: none; }
    div[data-testid="column"]:nth-of-type(2) .stButton button { background-color: #f1f3f5 !important; color: #868e96 !important; border: 1px solid #dee2e6; }

    /* 프로필 카드 */
    .profile-card { display: grid; grid-template-columns: 1.4fr 1fr; background-color: #F0F8FF; border-radius: 20px; overflow: hidden; margin-bottom: 15px; height: 160px; border: 1px solid #E1E8ED; }
    .card-text { padding: 20px; display: flex; flex-direction: column; justify-content: center; }
    .card-image img { width: 100%; height: 100%; object-fit: cover; object-position: top center; }
    .hello-text { font-size: 1rem; color: #555; margin-bottom: 4px; font-weight: 500; }
    .name-text { font-size: 1.6rem; color: #333; font-weight: 900; line-height: 1.3; word-break: keep-all; }
    .name-highlight { color: #5D9CEC; }

    .version-badge { text-align: right; color: #adb5bd; font-size: 0.75rem; font-weight: 600; margin-bottom: 5px; }
    .special-rule-box { color: #5D9CEC; font-weight: 800; margin-top: 15px; background-color: #F0F8FF; padding: 15px; border-radius: 12px; border: 1px solid #5D9CEC; text-align: center; line-height: 1.5; font-size: 0.95rem; }
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
    if not service: return None, None, None, [], None
    try:
        query = f"'{FOLDER_ID}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id, name, modifiedTime)").execute()
        all_files = results.get('files', [])
        user_db_id, renewal_id, realtime_id = None, None, None
        realtime_meta = None
        monthly_files = []
        for f in all_files:
            name = f['name']
            if name == "user_db.json": user_db_id = f['id']
            elif name == "realtime_usage.json": 
                realtime_id = f['id']
                realtime_meta = f
            elif "renewal" in name or "갱신" in name: renewal_id = f['id']
            elif ".xlsx" in name: monthly_files.append(f)
        monthly_files.sort(key=lambda x: get_file_sort_key(x['name']), reverse=True)
        return user_db_id, renewal_id, realtime_id, monthly_files, realtime_meta
    except: return None, None, None, [], None

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
            # 월별 엑셀 파일명에서 월 추출 (예: 2026_1월 -> 1)
            file_info = service.files().get(fileId=file_id, fields="name").execute()
            f_name = file_info.get('name', '')
            match_m = re.search(r'(\d+)월', f_name)
            current_f_month = match_m.group(1) if match_m else ""

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
                        if "연차" in val or "휴가" in val: 
                            # [Ver 4.3] 월 정보를 포함하여 표시
                            usage.append(f"{current_f_month}월 {d}일({val.strip()})")
                            count += 1.0
                        elif "반차" in val: 
                            usage.append(f"{current_f_month}월 {d}일(반차)")
                            count += 0.5
                    remain = 0.0
                    if remain_col_idx != -1 and i + 1 < len(df):
                        try: remain = float(df.iloc[i+1, remain_col_idx])
                        except: remain = 0.0
                    parsed.append({'이름': name, '사용내역': ", ".join(usage) if usage else "-", '사용개수': count, '잔여': remain})
            return pd.DataFrame(parsed)
    except: return pd.DataFrame()

# ==============================================================================
# 3. 유틸리티 함수 & 보안
# ==============================================================================
def hash_password(password):
    return hashlib.sha256(str(password).encode()).hexdigest()

def verify_password(stored_password, input_password):
    if stored_password == hash_password(input_password): return True
    if stored_password == input_password: return True
    return False

def get_kst_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=9)

def get_kst_today():
    return get_kst_now().date()

def get_kim_special_calc(uid, mode='total', base_file_date=None):
    if uid != "김동준": return 0.0
    bonus = 0.0
    monthly_dates = [
        datetime.date(2025, 8, 1), datetime.date(2025, 9, 1), datetime.date(2025, 10, 1),
        datetime.date(2025, 11, 1), datetime.date(2025, 12, 1), datetime.date(2026, 1, 1),
        datetime.date(2026, 2, 1), datetime.date(2026, 3, 1), datetime.date(2026, 4, 1),
        datetime.date(2026, 5, 1), datetime.date(2026, 6, 1)
    ]
    today = get_kst_today()
    for d in monthly_dates:
        if today >= d:
            if mode == 'total': bonus += 1.0
            elif mode == 'incremental' and base_file_date and d > base_file_date: bonus += 1.0
    if today >= datetime.date(2026, 7, 1): bonus += 15.0
    return bonus

# ==============================================================================
# 4. 메인 로직 (Ver 4.3)
# ==============================================================================
user_db_id, renewal_id, realtime_id, monthly_files, realtime_meta = get_all_files()

if user_db_id:
    user_db = load_json_file(user_db_id)
    db_changed = False
    for u in user_db:
        pw = user_db[u].get('pw', '')
        if len(pw) != 64:
            user_db[u]['pw'] = hash_password(pw)
            db_changed = True
    if db_changed: save_user_db(user_db_id, user_db)

if not st.session_state.get('login_status'):
    st.markdown("""<div class="login-header"><span class="login-icon">🏢</span><div class="login-title">옥션원 서울지사<br>연차확인</div></div>""", unsafe_allow_html=True)
    with st.form("login"):
        uid = st.text_input("아이디", placeholder="이름을 입력하세요").replace(" ", "")
        upw = st.text_input("비밀번호", type="password")
        if st.form_submit_button("로그인", use_container_width=True):
            db = load_json_file(user_db_id)
            if uid in db and verify_password(db[uid]['pw'], upw):
                st.session_state.login_status = True; st.session_state.user_id = uid; st.session_state.user_db = db; st.rerun()
            else: st.error("정보를 확인해주세요.")
else:
    login_uid = st.session_state.user_id
    login_uinfo = st.session_state.user_db.get(login_uid, {})
    if 'admin_mode' not in st.session_state: st.session_state.admin_mode = False
    target_uid = st.session_state.get('impersonate_user', login_uid) if st.session_state.admin_mode else login_uid

    st.markdown('<div class="version-badge">Ver 4.3</div>', unsafe_allow_html=True)
    admin_uinfo = st.session_state.user_db.get(login_uid, {})
    st.markdown(f"""<div class="profile-card"><div class="card-text"><div class="hello-text">반갑습니다,</div><div class="name-text"><span class="name-highlight">{login_uid} {admin_uinfo.get('title','')}</span>님</div><div class="msg-text">오늘도 활기찬 하루 되세요!</div></div><div class="card-image"><img src="https://raw.githubusercontent.com/leramidkei/auction1-PTO-Check/main/character.png"></div></div>""", unsafe_allow_html=True)

    if login_uinfo.get('role') == 'admin':
        st.session_state.admin_mode = st.toggle("🔧 관리자 모드", value=st.session_state.admin_mode)
        if st.session_state.admin_mode:
            all_users = list(st.session_state.user_db.keys())
            st.selectbox("조회할 사용자 선택", all_users, index=all_users.index(login_uid), key="impersonate_user")
            if target_uid != login_uid: st.markdown(f'<div class="viewing-alert">👀 현재 <b>{target_uid}</b>님의 데이터를 조회 중입니다.</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📌 잔여", "📅 월별", "🔄 갱신", "⚙️ 설정"])
    
    def render_metric_card(label1, val1, label2, val2, is_main=False):
        st.markdown(f"""<div class="metric-box"><div class="metric-item"><span class="metric-label">{label1}</span><span class="metric-value-large">{val1}</span></div><div class="metric-divider"></div><div class="metric-item"><span class="metric-label">{label2}</span><span class="metric-value-sub">{val2}</span></div></div>""", unsafe_allow_html=True)

    renewal_df = fetch_excel(renewal_id, True) if renewal_id else pd.DataFrame()

    with tab1:
        st.markdown('<div class="tab-section-header">현재 잔여 연차 확인</div>', unsafe_allow_html=True)
        if monthly_files:
            latest_fname = monthly_files[0]['name']
            df = fetch_excel(monthly_files[0]['id'])
            st.session_state.realtime_data = load_json_file(realtime_id) if realtime_id else {}
            me = df[df['이름'] == target_uid]
            if not me.empty:
                base_remain = float(me.iloc[0]['잔여'])
                match = re.search(r'(\d{4})_(\d+)', latest_fname)
                f_date = datetime.date(int(match.group(1)), int(match.group(2)), calendar.monthrange(int(match.group(1)), int(match.group(2)))[1]) if match else datetime.date(2000, 1, 1)
                bonus = (get_kim_special_calc(target_uid, 'incremental', f_date) if target_uid == "김동준" else 0.0)
                rt_used = 0.0
                if st.session_state.realtime_data.get(target_uid):
                    rt_used = float(st.session_state.realtime_data[target_uid].get('used', 0.0))
                
                final_val = base_remain + bonus - rt_used
                final_str = f"{int(final_val) if final_val%1==0 else final_val}개"
                if bonus > 0: st.success(f"👶 근속 1년 미만 발생분 +{bonus}개 합산됨")
                render_metric_card("현재 예상 잔여", final_str, "기준 파일", latest_fname, True)
            else: st.warning("데이터가 없습니다.")

    with tab2:
        # [Ver 4.3] 제목 변경
        st.markdown('<div class="tab-section-header">월별 사용 내역 조회 (월말 기준)</div>', unsafe_allow_html=True)
        opts = {f['name']: f['id'] for f in monthly_files}
        sel = st.selectbox("월 선택", list(opts.keys()), label_visibility="collapsed")
        if sel:
            df = fetch_excel(opts[sel])
            me = df[df['이름'] == target_uid]
            if not me.empty:
                r = me.iloc[0]
                render_metric_card("이번달 사용", f"{r['사용개수']}개", "당월 잔여", f"{r['잔여']}개")
                st.info(f"내역: {r['사용내역']}")

    with tab3:
        st.markdown('<div class="tab-section-header">연차 갱신 및 발생 내역</div>', unsafe_allow_html=True)
        if target_uid == "김동준":
            total_special = get_kim_special_calc("김동준", 'total')
            st.info("📅 **2026-07-01** 1년 근속 갱신 예정 (입사일: 2025-07-01)")
            # [Ver 4.3] HTML 카드 박스로 배경 잘림 해결
            st.markdown(f"""<div class="renewal-card"><span class="renewal-value-text">+15개</span><span class="renewal-sub-text">추가 발생 예정</span></div>""", unsafe_allow_html=True)
            if get_kst_today() < datetime.date(2026, 7, 1):
                st.markdown(f"""<div class="special-rule-box">[근속 1년 미만 근로자 연차 갱신규칙]<br>2026년 6월 1일까지 매월 1일 연차 1개 발생<br>(현재까지 발생분: +{int(total_special)}개)</div>""", unsafe_allow_html=True)
        elif not renewal_df.empty:
            me = renewal_df[renewal_df['이름'] == target_uid]
            if not me.empty:
                r = me.iloc[0]
                st.info(f"📅 **{r['갱신일']}** 갱신 {'완료' if pd.to_datetime(r['갱신일']).date() <= get_kst_today() else '예정'}")
                st.markdown(f"""<div class="renewal-card"><span class="renewal-value-text">+{int(r['갱신개수']) if float(r['갱신개수'])%1==0 else r['갱신개수']}개</span><span class="renewal-sub-text">추가 발생</span></div>""", unsafe_allow_html=True)
        st.markdown('<div class="bottom-spacer"></div>', unsafe_allow_html=True)

    with tab4:
        st.markdown('<div class="tab-section-header">설정 및 로그아웃</div>', unsafe_allow_html=True)
        p1 = st.text_input("새 비번", type="password")
        p2 = st.text_input("확인", type="password")
        c1, c2 = st.columns(2)
        if c1.button("저장", use_container_width=True):
            if p1 and p1 == p2:
                st.session_state.user_db[target_uid]['pw'] = hash_password(p1)
                save_user_db(user_db_id, st.session_state.user_db); st.success("완료")
            else: st.error("확인 필요")
        if c2.button("로그아웃", use_container_width=True):
            st.session_state.login_status = False; st.rerun()
