from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth
from main import dynamic_respond, greet_user, WEATHERAPI_API_KEY, get_user_profile, add_learned_responses, generate_flexible_response, log_interaction, personalize_response, process_negative_feedback
import logging
import sqlite3

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Cấu hình UTF-8 cho Flask
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

# Cấu hình logging
logging.basicConfig(level=logging.DEBUG)

# Khởi tạo Firebase Admin SDK nếu chưa được khởi tạo
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_admin_sdk.json")
    firebase_admin.initialize_app(cred)

def verify_firebase_token():
    """Xác thực người dùng qua Firebase."""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    try:
        token = auth_header.split(' ')[1]
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except firebase_admin.exceptions.InvalidArgumentError as e:
        print(f"Lỗi xác thực Firebase: {e}")
        return None
    except ValueError as e:
        if "Token used too early" in str(e):
            print("⚠️ Token bị từ chối do lệch thời gian. Thử lại sau 1 giây...")
            time.sleep(1)  # Đợi 1 giây rồi thử lại
            try:
                decoded_token = auth.verify_id_token(token)
                return decoded_token
            except Exception:
                return None
        return None

@app.route('/ask', methods=['POST'])
def ask_question():
    user = verify_firebase_token()
    if not user:
        return jsonify({"error": "Unauthorized", "status": "error"}), 401

    data = request.get_json(force=True)
    question = data.get('question', '').strip()
    is_teaching = data.get('is_teaching', False)
    teach_response = data.get('teach_response', '')

    if not question:
        return jsonify({"error": "Câu hỏi không được để trống", "status": "error"}), 400

    logging.debug(f"📩 Received question: {question}, is_teaching: {is_teaching}")
    response = dynamic_respond(question, user.get("uid"), is_teaching, teach_response)
    logging.debug(f"🤖 AI's Response: {response}")
    return jsonify(response)

@app.route('/greet', methods=['POST'])
def greet():
    user = verify_firebase_token()
    if not user:
        return jsonify({"error": "Unauthorized", "status": "error"}), 401

    data = request.get_json() or {}
    username = data.get('username')
    location = data.get('location')
    response = greet_user(user.get("uid"), username, location)
    return jsonify({"response": response.get("message", response.get("error")), "status": "success" if "message" in response else "error"})

@app.route('/logout', methods=['POST'])
def logout():
    user = verify_firebase_token()
    if not user:
        return jsonify({"error": "Unauthorized", "status": "error"}), 401
    return jsonify({"status": "success", "message": "Đăng xuất thành công"})


@app.route('/teach', methods=['POST'])
def teach_ai():
    user = verify_firebase_token()
    if not user:
        return jsonify({"error": "Unauthorized", "status": "error"}), 401

    data = request.get_json()
    original_query = data.get('original_query')
    teach_response = data.get('teach_response')
    uid = user.get("uid")
    username = get_user_profile(uid).get("username", "User") if uid else "User"

    if not original_query or not teach_response:
        return jsonify({"error": "Missing original_query or teach_response", "status": "error"}), 400

    add_learned_responses(original_query, teach_response)
    updated_response = generate_flexible_response(teach_response)
    log_interaction(original_query, updated_response)  # Ghi lại tương tác
    return jsonify({
        "answer": f"Thanks for teaching me, {username}! Here's the updated response: {updated_response}",
        "status": "success"
    })

@app.route('/feedback', methods=['POST'])
def send_feedback():
    user = verify_firebase_token()
    if not user:
        return jsonify({"error": "Unauthorized", "status": "error"}), 401

    data = request.get_json()
    original_query = data.get('original_query')
    feedback = data.get('feedback')
    uid = user.get("uid")
    username = get_user_profile(uid).get("username", "User") if uid else "User"

    if not original_query or not feedback:
        return jsonify({"error": "Missing original_query or feedback", "status": "error"}), 400

    response = process_negative_feedback(original_query, feedback)
    log_interaction(original_query, response)
    return jsonify({
        "answer": response,
        "status": "success"
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')