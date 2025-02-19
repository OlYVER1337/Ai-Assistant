from flask import Flask, request, jsonify
from flask_cors import CORS
from google_search import process_question

app = Flask(__name__)
CORS(app)

# Cấu hình UTF-8 cho Flask
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = 'application/json; charset=utf-8'

@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        # Xử lý request
        data = request.get_json(force=True)
        # Thêm xử lý encoding cho question
        question = data.get('question', '').strip().encode('utf-8').decode('utf-8')
        
        # Kiểm tra input
        if not question:
            return jsonify({
                "error": "Câu hỏi không được để trống",
                "status": "error",
                "style": {
                    "font-family": "'Roboto', 'Noto Sans', Arial, sans-serif",
                    "font-size": "16px",
                    "color": "#ff0000"
                }
            }), 400
            
        # Xử lý câu hỏi
        answer = process_question(question)
        # Thêm xử lý encoding cho answer
        answer = answer.encode('utf-8').decode('utf-8')
        
        # Format response
        response_data = {
            "answer": answer,
            "status": "success",
            "style": {
                "font-family": "'Roboto', 'Noto Sans', Arial, sans-serif",
                "font-size": "16px",
                "line-height": "1.5",
                "color": "#333333",
                "text-align": "justify",
                "padding": "10px",
                "background-color": "#f8f9fa",
                "border-radius": "8px",
                "box-shadow": "0 2px 4px rgba(0,0,0,0.1)"
            }
        }
        
        # Tạo response với headers phù hợp
        response = jsonify(response_data)
        response.headers.update({
            'Content-Type': 'application/json; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*'
        })
        
        return response

        
    except Exception as e:
        return jsonify({
            "error": f"Lỗi xử lý: {str(e)}",
            "status": "error",
            "style": {
                "font-family": "Arial, sans-serif",
                "font-size": "14px",
                "color": "#ff0000",
                "background-color": "#fff3f3",
                "padding": "10px",
                "border-radius": "4px"
            }
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
