from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth
from main import (
    dynamic_respond, handle_system_command, handle_open_application,
    handle_play_music, handle_check_weather, handle_set_appointment,
    check_appointment_reminders, personalize_response, greet_user, WEATHERAPI_API_KEY,
    process_negative_feedback, add_learned_responses, generate_flexible_response,
    update_user_profile, learn_new_knowledge, update_reward_score
)
import logging

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
    except Exception as e:
        print(f"Lỗi xác thực Firebase: {e}")
        return None

@app.route('/ask', methods=['POST'])
def ask_question():
    """Xử lý câu hỏi của người dùng."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        data = request.get_json(force=True)
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"error": "Câu hỏi không được để trống", "status": "error"}), 400
        
        logging.debug(f"Received question: {question}")
        answer = dynamic_respond(question)
        logging.debug(f"Generated answer: {answer}")
        return jsonify({"answer": answer, "status": "success"})
    except Exception as e:
        logging.error(f"Error in /ask: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/command', methods=['POST'])
def execute_command():
    """Xử lý lệnh hệ thống từ người dùng."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        data = request.get_json(force=True)
        command = data.get('command', '').strip()
        response = handle_system_command(command)
        return jsonify({"response": response, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/open_app', methods=['POST'])
def open_application():
    """Mở ứng dụng theo yêu cầu của người dùng."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        data = request.get_json(force=True)
        app_name = data.get('app_name', '').strip()
        response = handle_open_application(app_name)
        return jsonify({"response": response, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/play_music', methods=['POST'])
def play_music():
    """Phát nhạc theo yêu cầu của người dùng."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        data = request.get_json(force=True)
        song_request = data.get('song', '').strip()
        response = handle_play_music(song_request)
        return jsonify({"response": response, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/weather', methods=['POST'])
def check_weather():
    """Kiểm tra thời tiết theo yêu cầu của người dùng."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        data = request.get_json(force=True)
        location = data.get('location', '').strip()
        response = handle_check_weather(location, WEATHERAPI_API_KEY)
        return jsonify({"response": response, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/set_appointment', methods=['POST'])
def set_appointment():
    """Đặt lịch hẹn theo yêu cầu của người dùng."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        data = request.get_json(force=True)
        appointment_request = data.get('appointment', '').strip()
        response = handle_set_appointment(appointment_request)
        return jsonify({"response": response, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/reminders', methods=['GET'])
def get_reminders():
    """Lấy danh sách nhắc nhở lịch hẹn."""
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        response = check_appointment_reminders()
        return jsonify({"response": response, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e), "status": "error"}), 500

@app.route('/greet', methods=['POST'])
def greet():
    try:
        user = verify_firebase_token()
        if not user:
            return jsonify({"error": "Unauthorized", "status": "error"}), 401

        uid = user.get("uid")  # 🔥 Lấy UID từ Firebase

        data = request.get_json(force=True) or {}
        username = data.get('username', '').strip()
        location = data.get('location', '').strip()

        # Gọi greet_user với UID
        response = greet_user(uid=uid, username=username, location=location)  # ✅ Truyền uid vào

        # Nếu thiếu username, yêu cầu frontend nhập
        if response.get("error") == "missing_username":
            return jsonify(response), 400  # HTTP 400: Bad Request

        # Nếu thiếu location, yêu cầu frontend nhập
        if response.get("error") == "missing_location":
            return jsonify(response), 400

        return jsonify({"response": response["message"], "status": "success"})
    except Exception as e:
        print(f"🔥 Lỗi trong API /greet: {e}")
        return jsonify({"error": str(e), "status": "error"}), 500



@app.route('/provide_feedback', methods=['POST'])
def provide_feedback():
    data = request.get_json()
    feedback = data.get('feedback', '').strip()
    if feedback:
        add_learned_responses('feedback', feedback)
        new_answer = generate_flexible_response(feedback)
        update_reward_score(5)
        return jsonify({'message': f'Thank you for your feedback. Here is the updated answer: {new_answer}'}), 200
    else:
        update_reward_score(-5)
        return jsonify({'message': 'No new information provided.'}), 400

@app.route('/teach_ai', methods=['POST'])
def teach_ai():
    data = request.get_json()
    query = data.get('query', '').strip()
    user_input = data.get('user_input', '').strip()
    if user_input:
        add_learned_responses(query, user_input)
        return jsonify({'message': generate_flexible_response(user_input)}), 200
    else:
        return jsonify({'message': f'Thanks, I have learned about {query}.'}), 200

@app.route('/set_user_info', methods=['POST'])
def set_user_info():
    data = request.get_json()
    username = data.get('username', '').strip()
    location = data.get('location', '').strip()
    if username and location:
        update_user_profile(username=username, location=location)
        return jsonify({'message': 'User information updated successfully.'}), 200
    else:
        return jsonify({'message': 'Invalid user information.'}), 400

@app.route('/user_input', methods=['POST'])
def user_input():
    data = request.get_json()
    user_input = data.get('user_input', '').strip()
    if user_input:
        # Process user input here
        return jsonify({'message': 'User input processed.'}), 200
    else:
        return jsonify({'message': 'No input provided.'}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
