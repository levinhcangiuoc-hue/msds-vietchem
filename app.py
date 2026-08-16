from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
import json
import os
import time
import traceback

app = Flask(__name__, static_folder='.', static_url_path='')
# Tăng giới hạn dung lượng tải lên 100MB cho chắc chắn
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  

CONFIG_FILE = "config.json"
TEMP_DIR = "temp_pdfs"
os.makedirs(TEMP_DIR, exist_ok=True)

def load_api_key():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f).get("api_key", "")
        except: pass
    return ""

def save_api_key(key):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"api_key": key}, f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def config_api():
    if request.method == 'POST':
        data = request.json
        key = data.get('api_key', '')
        save_api_key(key)
        return jsonify({"status": "success"})
    return jsonify({"api_key": load_api_key()})

@app.route('/api/scan_models', methods=['POST'])
def scan_models():
    api_key = request.json.get('api_key')
    try:
        client = genai.Client(api_key=api_key)
        models = []
        for m in client.models.list():
            ten = getattr(m, 'name', '').replace('models/', '')
            if 'gemini' in ten.lower():
                models.append(ten)
        models.sort(key=lambda x: ('pro' in x.lower(), x), reverse=True)
        return jsonify({"status": "success", "models": models})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    fpath = None
    tai_lieu = None
    client = None
    try:
        api_key = request.form.get('api_key')
        model_name = request.form.get('model')
        file = request.files.get('file')
        
        if not file or not api_key or not model_name:
            return jsonify({"status": "error", "message": "Thiếu thông tin yêu cầu từ trình duyệt."})

        # --- ĐÂY LÀ DÒNG CODE ĐÃ SỬA LỖI ---
        # Gọt bỏ toàn bộ đường dẫn thư mục, chỉ giữ lại đúng tên file (VD: 157791.pdf)
        filename = os.path.basename(file.filename.replace('\\', '/'))
        if not filename:
            filename = f"temp_{int(time.time())}.pdf"
            
        fpath = os.path.join(TEMP_DIR, filename)
        file.save(fpath)
        
        client = genai.Client(api_key=api_key)
        prompt = """Trích xuất JSON từ MSDS:
1. Tên Sản Phẩm (Mục 1).
2. Thành Phần & Mã CAS (Mục 3).
Format bắt buộc: {"Ten_San_Pham": "...", "Thanh_Phan": [{"Ten_Chat": "...", "Ma_CAS": "..."}]}"""

        tai_lieu = client.files.upload(file=fpath)
        time.sleep(2) 
        
        for lan in range(1, 4):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[prompt, tai_lieu],
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0)
                )
                
                raw = response.text.strip()
                if raw.startswith("```json"): raw = raw[7:]
                if raw.startswith("```"): raw = raw[3:]
                if raw.endswith("```"): raw = raw[:-3]
                
                try:
                    data = json.loads(raw.strip())
                    return jsonify({"status": "success", "data": data})
                except Exception as json_err:
                    return jsonify({"status": "error", "message": f"AI trả về sai định dạng JSON. Phản hồi gốc: {raw}"})
                    
            except Exception as e:
                err = str(e)
                if any(x in err for x in ["503", "429", "ResourceExhausted", "Quota"]):
                    if lan == 3: 
                        return jsonify({"status": "overloaded", "message": "Hệ thống Google bận (Đã thử 3 lần)"})
                    time.sleep(3 * lan)
                else:
                    return jsonify({"status": "error", "message": f"Lỗi từ Google: {err}"})
                    
        return jsonify({"status": "overloaded", "message": "Google từ chối do quá tải"})
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Lỗi Hệ thống Python: {str(e)}"})
        
    finally:
        if tai_lieu and client:
            try: client.files.delete(name=tai_lieu.name)
            except: pass
        if fpath and os.path.exists(fpath):
            try: os.remove(fpath)
            except: pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
