import json

# Đường dẫn tới file dữ liệu JSONL
input_file = "D:\data\simplified-nq-train.jsonl"
output_file = "t5_train_data.txt"


with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
    for line in infile:
        # Parse từng dòng JSON
        data = json.loads(line.strip())
        question = data["question_text"]
        context = data["document_text"]
        
        # Lấy câu trả lời ngắn nhất (short answer)
        short_answers = data["annotations"][0]["short_answers"]
        if short_answers and "text" in short_answers[0]:
            answer = short_answers[0]["text"]
        else:
            # Nếu không có short answer hoặc không có trường 'text', bỏ qua
            continue
        
        # Format dữ liệu đầu vào cho T5
        input_text = f"question: {question} context: {context} </s>"
        output_text = answer
        
        # Lưu vào file
        outfile.write(f"{input_text}\t{output_text}\n")