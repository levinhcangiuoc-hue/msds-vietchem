import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
import json
import time
import io
import os
import base64

# ==========================================
# CẤU HÌNH & LƯU TRỮ API KEY (WEB)
# ==========================================
if 'logs' not in st.session_state: st.session_state.logs = "Hệ thống sẵn sàng...\n"
if 'available_models' not in st.session_state: st.session_state.available_models = []
if 'api_key_valid' not in st.session_state: st.session_state.api_key_valid = False
if 'api_key' not in st.session_state: st.session_state.api_key = ""

def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

st.set_page_config(page_title="MSDS Pro - VIETCHEM", page_icon="🧪", layout="wide")

# ==========================================
# CSS TỐI GIẢN & TÙY CHỈNH KÍCH THƯỚC CHỮ
# ==========================================
st.markdown("""
<style>
    :root { --primary: #1e40af; --primary-dark: #1e3a8a; --dark: #1e293b; --gray: #64748b; --border: #e2e8f0; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} [data-testid="collapsedControl"] { display: none; }
    
    .stMarkdown p, .stText, label { font-size: 15px !important; }
    .streamlit-expanderHeader { font-size: 16px !important; font-weight: 700 !important; color: var(--dark) !important; }
    
    .stButton>button[kind="primary"] { 
        border-radius: 6px; height: 48px; font-size: 16px !important; font-weight: 800; 
        background-color: var(--primary); color: white; border: none; width: 100%;
        text-transform: uppercase; letter-spacing: 1px; transition: all 0.2s;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: var(--primary-dark); transform: translateY(-2px); box-shadow: 0 6px 12px rgba(30, 64, 175, 0.15);
    }
    
    .footer-grid {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 40px;
        padding-top: 25px; border-top: 2px solid var(--border);
    }
    @media (max-width: 900px) { .footer-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 600px) { .footer-grid { grid-template-columns: 1fr; } }
    
    .footer-card { background: #f8fafc; padding: 15px; border-radius: 6px; border: 1px solid var(--border); border-left: 3px solid var(--gray); }
    .footer-card.main-hq { border-left-color: var(--primary); background: #f0f9ff; }
    .footer-card strong { display: flex; align-items: center; gap: 6px; color: var(--dark); margin-bottom: 6px; font-size: 14px; text-transform: uppercase; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
    .footer-card p { display: flex; align-items: flex-start; gap: 6px; margin: 0; font-size: 13px; color: var(--gray); line-height: 1.4; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# BACKEND XỬ LÝ DỮ LIỆU
# ==========================================
def quet_model(api_key):
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for m in client.models.list():
            ten = getattr(m, 'name', '').replace('models/', '')
            if 'gemini' in ten.lower(): models.append(ten)
        models.sort(key=lambda x: ('pro' in x.lower(), x), reverse=True)
        return models, True
    except Exception as e:
        return str(e), False

def phan_tich_file(client, model_name, file_path, log_box):
    prompt = """Trích xuất JSON từ MSDS:
1. Tên Sản Phẩm (Mục 1).
2. Thành Phần & Mã CAS (Mục 3).
Format bắt buộc: {"Ten_San_Pham": "...", "Thanh_Phan": [{"Ten_Chat": "...", "Ma_CAS": "..."}]}"""

    tai_lieu = None
    try:
        tai_lieu = client.files.upload(file=file_path)
        time.sleep(2) 
    except Exception as e:
        return None, f"Lỗi tải file: {e}"

    for lan in range(1, 4):
        try:
            response = client.models.generate_content(
                model=model_name, contents=[prompt, tai_lieu],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
            )
            try: client.files.delete(name=tai_lieu.name)
            except: pass
            
            raw = response.text.strip()
            if raw.startswith("```json"): raw = raw[7:]
            if raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            return json.loads(raw.strip()), "OK"
            
        except Exception as e:
            err = str(e)
            if any(x in err for x in ["503", "429", "ResourceExhausted", "Quota"]):
                wait_time = 3 * lan
                st.session_state.logs += f"   [Chờ {wait_time}s do server Google bận...]\n"
                log_box.code(st.session_state.logs, language="bash")
                time.sleep(wait_time)
            else:
                try: client.files.delete(name=tai_lieu.name)
                except: pass
                return None, f"{err}"
                
    try: client.files.delete(name=tai_lieu.name)
    except: pass
    return None, "Bị Google từ chối do quá tải"

# ==========================================
# GIAO DIỆN CHÍNH (FRONTEND)
# ==========================================
b64_logo = get_base64_image("logo.jpg")
img_html = f'<img src="data:image/jpeg;base64,{b64_logo}" style="height: 85px; object-fit: contain;">' if b64_logo else ""

st.markdown(f"""
<div style="display: flex; align-items: center; justify-content: flex-start; gap: 20px; padding-bottom: 20px; border-bottom: 2px solid #1e40af; margin-bottom: 25px;">
    {img_html}
    <div style="display: flex; flex-direction: column; justify-content: center; gap: 4px;">
        <div style="color: #1e3a8a; font-size: clamp(20px, 3vw, 32px); font-weight: 900; white-space: nowrap; letter-spacing: 0.5px; line-height: 1.1;">CÔNG TY CỔ PHẦN DỊCH VỤ TƯ VẤN THƯƠNG MẠI VIETCHEM</div>
        <div style="color: #64748b; font-size: clamp(14px, 1.5vw, 16px); font-weight: 500; line-height: 1.1;">Hệ thống Tự động hóa Trích xuất Dữ liệu Hóa chất MSDS</div>
    </div>
</div>
""", unsafe_allow_html=True)

with st.expander("⚙️ BẢNG ĐIỀU KHIỂN & CẤU HÌNH API", expanded=not st.session_state.api_key_valid):
    c1, c2, c3 = st.columns([3, 1, 3])
    with c1:
        api_key_input = st.text_input("Google API Key:", type="password", value=st.session_state.api_key, label_visibility="collapsed", placeholder="Nhập API Key...")
        if api_key_input: st.session_state.api_key = api_key_input
    with c2:
        if st.button("🔄 Quét Model", use_container_width=True):
            if api_key_input:
                with st.spinner("Đang quét..."):
                    models, ok = quet_model(api_key_input)
                    if ok:
                        st.session_state.available_models = models
                        st.session_state.api_key_valid = True
                        st.toast("✅ Kết nối thành công!")
                    else:
                        st.session_state.api_key_valid = False
                        st.error("Lỗi API")
            else:
                st.warning("Nhập API Key!")
    with c3:
        selected_model = None
        if st.session_state.api_key_valid and st.session_state.available_models:
            selected_model = st.selectbox("Model", options=st.session_state.available_models, label_visibility="collapsed")
        else:
            st.selectbox("Model", options=["Chưa kết nối API"], disabled=True, label_visibility="collapsed")

# 3. KÉO THẢ TẢI FILE (THAY THẾ CHỌN THƯ MỤC)
st.markdown("<div style='color:#1e293b; font-size: 18px; font-weight: 700; margin-top:20px; margin-bottom: 10px;'>📁 TẢI LÊN CÁC FILE DỮ LIỆU PDF</div>", unsafe_allow_html=True)
uploaded_files = st.file_uploader("Kéo thả hoặc chọn nhiều file PDF MSDS vào đây", type=['pdf'], accept_multiple_files=True, label_visibility="collapsed")

if uploaded_files: 
    st.info(f"✅ Đã tải lên **{len(uploaded_files)}** file PDF. Sẵn sàng xử lý!")

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 BẮT ĐẦU TRÍCH XUẤT VÀ ĐỐI CHIẾU DỮ LIỆU", type="primary", use_container_width=True):
    if not st.session_state.api_key_valid or not selected_model:
        st.error("⚠️ Vui lòng mở phần cấu hình và kết nối API Google trước!")
    elif not uploaded_files:
        st.error("⚠️ Chưa tải lên file PDF nào!")
    else:
        # Lưu file tạm thời để gửi API
        temp_dir = "temp_pdfs"
        os.makedirs(temp_dir, exist_ok=True)
        files_to_process = []
        for uf in uploaded_files:
            tpath = os.path.join(temp_dir, uf.name)
            with open(tpath, "wb") as f:
                f.write(uf.getbuffer())
            files_to_process.append((uf.name, tpath))
            
        client = genai.Client(api_key=api_key_input)
        data_out = []
        files_to_retry = [] 
        bar = st.progress(0)
        
        st.session_state.logs = f"> Kích hoạt động cơ {selected_model}...\n"
        log_box = st.empty()
        log_box.code(st.session_state.logs, language="bash")
        stt_counter = 1 
        
        # --- VÒNG QUÉT 1 ---
        for i, (fname, fpath) in enumerate(files_to_process):
            st.session_state.logs += f"\n[{i+1}/{len(files_to_process)}] Đang đọc file: {fname}...\n"
            log_box.code(st.session_state.logs, language="bash")
            
            kq, msg = phan_tich_file(client, selected_model, fpath, log_box)
            
            if kq:
                sp = kq.get("Ten_San_Pham", "Không xác định")
                tps = kq.get("Thanh_Phan", [])
                st.session_state.logs += f" -> XONG: {sp} ({len(tps)} thành phần)\n"
                if tps:
                    for idx, tp in enumerate(tps):
                        data_out.append({
                            '_STT_Sort': stt_counter, '_Sub_Idx': idx, 
                            'STT': stt_counter if idx == 0 else "", 'Tên File': fname if idx == 0 else "", 
                            'Sản Phẩm': sp if idx == 0 else "", 'Thành Phần': tp.get('Ten_Chat',''), 'Mã CAS': tp.get('Ma_CAS','')
                        })
                else:
                    data_out.append({'_STT_Sort': stt_counter, '_Sub_Idx': 0, 'STT': stt_counter, 'Tên File': fname, 'Sản Phẩm': sp, 'Thành Phần': 'Trống', 'Mã CAS': '-'})
            else:
                if "quá tải" in msg.lower() or "quota" in msg.lower() or "429" in msg or "503" in msg:
                    files_to_retry.append((fname, fpath, stt_counter))
                    st.session_state.logs += f" -> ⚠️ Tạm bỏ qua do quá tải. Sẽ quét lại ở vòng sau.\n"
                else:
                    st.session_state.logs += f" -> [LỖI]: {msg}\n"
                    data_out.append({'_STT_Sort': stt_counter, '_Sub_Idx': 0, 'STT': stt_counter, 'Tên File': fname, 'Sản Phẩm': '⚠️ Lỗi tài liệu', 'Thành Phần': msg, 'Mã CAS': '-'})
            
            stt_counter += 1
            log_box.code(st.session_state.logs, language="bash")
            bar.progress((i + 1) / len(files_to_process))
            if i < len(files_to_process) - 1: time.sleep(2)
        
        # --- VÒNG QUÉT 2 ---
        if files_to_retry:
            st.session_state.logs += f"\n====================================\n🔄 ĐANG NGHỈ 5S TRƯỚC KHI KIỂM TRA LẠI {len(files_to_retry)} FILE BỊ QUÁ TẢI...\n"
            log_box.code(st.session_state.logs, language="bash")
            time.sleep(5)
            
            for index_retry, (fname, fpath, assigned_stt) in enumerate(files_to_retry):
                st.session_state.logs += f"\n[VÒNG 2 - {index_retry+1}/{len(files_to_retry)}] Quét lại: {fname}...\n"
                log_box.code(st.session_state.logs, language="bash")
                kq, msg = phan_tich_file(client, selected_model, fpath, log_box)
                
                if kq:
                    sp = kq.get("Ten_San_Pham", "Không xác định")
                    tps = kq.get("Thanh_Phan", [])
                    st.session_state.logs += f" -> THÀNH CÔNG Ở VÒNG 2: {sp}\n"
                    if tps:
                        for idx, tp in enumerate(tps):
                            data_out.append({
                                '_STT_Sort': assigned_stt, '_Sub_Idx': idx, 
                                'STT': assigned_stt if idx == 0 else "", 'Tên File': fname if idx == 0 else "", 
                                'Sản Phẩm': sp if idx == 0 else "", 'Thành Phần': tp.get('Ten_Chat',''), 'Mã CAS': tp.get('Ma_CAS','')
                            })
                    else:
                        data_out.append({'_STT_Sort': assigned_stt, '_Sub_Idx': 0, 'STT': assigned_stt, 'Tên File': fname, 'Sản Phẩm': sp, 'Thành Phần': 'Trống', 'Mã CAS': '-'})
                else:
                    st.session_state.logs += f" -> ❌ THẤT BẠI: Vẫn bị Google quá tải.\n"
                    data_out.append({'_STT_Sort': assigned_stt, '_Sub_Idx': 0, 'STT': assigned_stt, 'Tên File': fname, 'Sản Phẩm': '⚠️ Bị bỏ qua', 'Thành Phần': 'Ghi chú: Lỗi quá tải', 'Mã CAS': '-'})
                log_box.code(st.session_state.logs, language="bash")
                time.sleep(3)
                
        st.session_state.logs += "\n✨ HOÀN TẤT TOÀN BỘ QUÁ TRÌNH!\n"
        log_box.code(st.session_state.logs, language="bash")
        
        # Xóa file tạm
        for _, fpath in files_to_process:
            try: os.remove(fpath)
            except: pass
            
        if data_out:
            data_out.sort(key=lambda x: (x['_STT_Sort'], x['_Sub_Idx']))
            for row in data_out:
                del row['_STT_Sort']
                del row['_Sub_Idx']
            
            st.markdown("<div style='color:#1e293b; font-size: 18px; font-weight: 700; margin-top:20px; margin-bottom: 10px;'>📊 KẾT QUẢ ĐỒNG BỘ</div>", unsafe_allow_html=True)
            df = pd.DataFrame(data_out)
            st.dataframe(df, use_container_width=True)
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as w:
                df.to_excel(w, index=False)
            st.download_button("📥 TẢI BÁO CÁO EXCEL", data=out.getvalue(), file_name="Vietchem_Data_MSDS.xlsx", type="primary")
else:
    log_box = st.empty()
    log_box.code(st.session_state.logs, language="bash")

st.markdown("""
<div class="footer-grid">
    <div class="footer-card main-hq">
        <strong>🏢 TRỤ SỞ CHÍNH</strong>
        <p>📍 Số 34, đường 3C, KDC Nam Hùng Vương, Phường An Lạc, TP.HCM</p>
    </div>
    <div class="footer-card">
        <strong>🏭 CHI NHÁNH TẠI LONG AN</strong>
        <p>📍 Kho K2-2, KCN Tân Kim mở rộng, Xã Cần Giuộc, Tây Ninh</p>
    </div>
    <div class="footer-card">
        <strong>🏭 CHI NHÁNH 2 LONG AN</strong>
        <p>📍 Lô R24-R25 ĐS 8, KCN Hải sơn mở rộng, Xã Đức Hòa, Tây Ninh</p>
    </div>
    <div class="footer-card">
        <strong>🏭 CHI NHÁNH 3 LONG AN</strong>
        <p>📍 Lô R9 & R10 ĐS 9, KCN Hải Sơn mở rộng, Xã Đức Hòa, Tây Ninh</p>
    </div>
    <div class="footer-card">
        <strong>🏭 CHI NHÁNH 04 LONG AN</strong>
        <p>📍 Lô H9A-H10, Đường N3, KCN Nam Thuận, Xã Mỹ Hạnh, Tây Ninh</p>
    </div>
    <div class="footer-card">
        <strong>🏭 CHI NHÁNH 05</strong>
        <p>📍 Lô H11, Đường N3, KCN Nam Thuận, Xã Mỹ Hạnh, Tây Ninh</p>
    </div>
</div>
""", unsafe_allow_html=True)