import datetime
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials, firestore
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os
import re

# Lấy đường dẫn tuyệt đối của thư mục hiện tại
current_dir = os.path.dirname(os.path.abspath(__file__))

# Khởi tạo Firebase Firestore
firebase_config_path = os.path.join(current_dir, "firebase_admin_sdk.json")
cred = credentials.Certificate(firebase_config_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Khởi tạo Google Search API
API_KEY = "AIzaSyAyzKTHtZizjO4AV7jZrk8Z9IqgeOV-kAk"
SEARCH_ENGINE_ID = "44b740bae2e4045a8"

# Tạo đường dẫn đến thư mục model
model_path = os.path.join(current_dir, "model")

# Load model và tokenizer với đường dẫn tuyệt đối
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForSeq2SeqLM.from_pretrained(model_path, local_files_only=True)


# Hàm Google Search

def google_search(query, api_key, search_engine_id):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=search_engine_id, num=5).execute()
    
    # Chỉ lấy nội dung chính, bỏ qua metadata
    meaningful_content = []
    if "items" in res:
        for item in res["items"]:
            # Lấy phần snippet và loại bỏ thông tin thời gian, URL
            content = item.get('snippet', '')
            # Loại bỏ các reference như "r/askscience", ngày tháng
            content = ' '.join([
                line for line in content.split('\n')
                if not any(x in line.lower() for x in ['r/', 'http', 'www.', '.com', 'jan', 'feb', 'mar'])
            ])
            if content:
                meaningful_content.append(content)
    
    return meaningful_content
# Hàm lấy tri thức từ Firestore
def fetch_knowledge(question):
    docs = db.collection("knowledge_base").where("question", "==", question).get()
    if docs:
        for doc in docs:
            return doc.to_dict()
    return None

# Hàm lưu tri thức vào Firestore
def save_knowledge(question, answer):
    data = {
        "question": question,
        "answer": answer,
        "last_updated": datetime.datetime.now().isoformat()
    }
    db.collection("knowledge_base").add(data)

# Hàm tạo câu trả lời từ model
def generate_answer(context, question):
    # Đảm bảo encoding UTF-8 cho input
    question = question.encode('utf-8').decode('utf-8')
    context = context.encode('utf-8').decode('utf-8')

    # Tạo prompt rõ ràng hơn
    input_text = f"""
    Question: {question}
    Context: {context}
    
    Please provide a detailed answer that:
    1. Explains the concept clearly
    2. Uses simple language
    3. Includes examples when needed
    4. Is scientifically accurate
    """
    
    input_ids = tokenizer.encode(input_text, return_tensors="pt")
    output_ids = model.generate(
        input_ids,
        max_length=500,
        num_beams=5,
        length_penalty=1.5,
        temperature=0.7
    )
    
    # Xử lý câu trả lời với encoding UTF-8
    answer = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    answer = answer.encode('utf-8').decode('utf-8')
    
    # Xử lý câu trả lời để loại bỏ prompt
    answer = answer.replace('Question:', '')
    answer = answer.replace('Context:', '')
    answer = answer.replace('Please provide', '')
    
    # Chỉ lấy phần câu trả lời thực sự đã được xử lý encoding
    return answer.strip()



# Hàm xử lý câu hỏi
def process_question(question):
    knowledge = fetch_knowledge(question)
    if knowledge:
        return generate_answer(knowledge["answer"], question)

    search_results = google_search(question, API_KEY, SEARCH_ENGINE_ID)
    if search_results:
        # Kết hợp các kết quả có ý nghĩa
        context = ' '.join(search_results)
        # Tạo câu trả lời từ context đã được lọc
        answer = generate_answer(context, question)
        
        # Lưu vào Firestore
        save_knowledge(question, context)
        return answer
    
    return "Tôi có thông tin chính xác cho câu hỏi của bạn."

# Thực thi
if __name__ == "__main__":
    user_question = input("Hỏi trợ lý ảo: ")
    final_answer = process_question(user_question)
    print(f"Câu trả lời: {final_answer}")
