import datetime
from googleapiclient.discovery import build
import firebase_admin
from firebase_admin import credentials, firestore
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# Khởi tạo Firebase Firestore
cred = credentials.Certificate("firebase_admin_sdk.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Khởi tạo Google Search API
API_KEY = "AIzaSyAyzKTHtZizjO4AV7jZrk8Z9IqgeOV-kAk"
SEARCH_ENGINE_ID = "44b740bae2e4045a8"

# Khởi tạo model đã train (T5)
tokenizer = AutoTokenizer.from_pretrained("checkpoint_epoch_1")
model = AutoModelForSeq2SeqLM.from_pretrained("checkpoint_epoch_1")

# Hàm Google Search
def google_search(query, api_key, search_engine_id):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=query, cx=search_engine_id, num=3).execute()
    results = []
    if "items" in res:
        for item in res["items"]:
            results.append({
                "title": item["title"],
                "link": item["link"],
                "snippet": item["snippet"]
            })
    return results

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
    input_text = f"question: {question} context: {context} </s>"
    input_ids = tokenizer.encode(input_text, return_tensors="pt")
    output_ids = model.generate(input_ids, max_length=100, num_beams=5, early_stopping=True)
    answer = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return answer.strip()

# Hàm xử lý câu hỏi
def process_question(question):
    # Bước 1: Kiểm tra tri thức trong Firestore
    knowledge = fetch_knowledge(question)
    if knowledge:
        print("Tri thức tìm thấy trong Firestore.")
        return generate_answer(knowledge["answer"], question)

    # Bước 2: Nếu không có tri thức, tra cứu Google
    print("Tri thức không tồn tại. Đang tìm kiếm trên Google...")
    search_results = google_search(question, API_KEY, SEARCH_ENGINE_ID)
    if search_results:
        # Tổng hợp thông tin từ Google
        combined_info = "\n".join([result["snippet"] for result in search_results])
        answer = generate_answer(combined_info, question)
        
        # Lưu tri thức mới vào Firestore
        save_knowledge(question, combined_info)
        return answer
    
    return "Xin lỗi, tôi không tìm được câu trả lời cho câu hỏi của bạn."

# Thực thi
if __name__ == "__main__":
    user_question = input("Hỏi trợ lý ảo: ")
    final_answer = process_question(user_question)
    print(f"Câu trả lời: {final_answer}")
