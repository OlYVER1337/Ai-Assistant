<<<<<<< HEAD
﻿from transformers import T5Tokenizer, T5ForConditionalGeneration
import torch

model_path = "checkpoint_epoch_1"
tokenizer = T5Tokenizer.from_pretrained(model_path)
model = T5ForConditionalGeneration.from_pretrained(model_path)
# Define input question and context
context = """
Artificial intelligence (AI), in its broadest sense, is intelligence exhibited by machines, particularly computer systems. It is a field of research in computer science that develops and studies methods and software that enable machines to perceive their environment and use learning and intelligence to take actions that maximize their chances of achieving defined goals.[1] Such machines may be called AIs.

High-profile applications of AI include advanced web search engines (e.g., Google Search); recommendation systems (used by YouTube, Amazon, and Netflix); virtual assistants (e.g., Google Assistant, Siri, and Alexa); autonomous vehicles (e.g., Waymo); generative and creative tools (e.g., ChatGPT and AI art); and superhuman play and analysis in strategy games (e.g., chess and Go). However, many AI applications are not perceived as AI: "A lot of cutting edge AI has filtered into general applications, often without being called AI because once something becomes useful enough and common enough it's not labeled AI anymore."[2][3]

Various subfields of AI research are centered around particular goals and the use of particular tools. The traditional goals of AI research include reasoning, knowledge representation, planning, learning, natural language processing, perception, and support for robotics.[a] General intelligence—the ability to complete any task performed by a human on an at least equal level—is among the field's long-term goals.[4] To reach these goals, AI researchers have adapted and integrated a wide range of techniques, including search and mathematical optimization, formal logic, artificial neural networks, and methods based on statistics, operations research, and economics.[b] AI also draws upon psychology, linguistics, philosophy, neuroscience, and other fields.[5]

Artificial intelligence was founded as an academic discipline in 1956,[6] and the field went through multiple cycles of optimism throughout its history,[7][8] followed by periods of disappointment and loss of funding, known as AI winters.[9][10] Funding and interest vastly increased after 2012 when deep learning outperformed previous AI techniques.[11] This growth accelerated further after 2017 with the transformer architecture,[12] and by the early 2020s many billions of dollars were being invested in AI and the field experienced rapid ongoing progress in what has become known as the AI boom. The emergence of advanced generative AI in the midst of the AI boom and its ability to create and modify content exposed several unintended consequences and harms in the present and raised concerns about the risks of AI and its long-term effects in the future, prompting discussions about regulatory policies to ensure the safety and benefits of the technology.
"""

question = "which ones AI applied for?"

# Format input for the T5 model
input_text = f"question: {question} context: {context} </s>"
input_ids = tokenizer.encode(input_text, return_tensors="pt")

# Generate answer
model.eval()
with torch.no_grad():
    output_ids = model.generate(
        input_ids,
        max_length=100,  # Tăng độ dài câu trả lời
        num_beams=15,   # Sử dụng nhiều beam hơn
        temperature=0.7,  # Điều chỉnh tính sáng tạo
        repetition_penalty=2.0,  # Giảm trùng lặp
        early_stopping=True
    )

# Decode the answer
answer = tokenizer.decode(output_ids[0], skip_special_tokens=True)
answer = answer.replace("answer: ", "").strip()

print("Question:", question)
print("Answer:", answer)
=======
﻿from transformers import T5Tokenizer, T5ForConditionalGeneration
import torch

model_path = "checkpoint_epoch_1"
tokenizer = T5Tokenizer.from_pretrained(model_path)
model = T5ForConditionalGeneration.from_pretrained(model_path)
# Define input question and context
context = """
Artificial intelligence (AI), in its broadest sense, is intelligence exhibited by machines, particularly computer systems. It is a field of research in computer science that develops and studies methods and software that enable machines to perceive their environment and use learning and intelligence to take actions that maximize their chances of achieving defined goals.[1] Such machines may be called AIs.

High-profile applications of AI include advanced web search engines (e.g., Google Search); recommendation systems (used by YouTube, Amazon, and Netflix); virtual assistants (e.g., Google Assistant, Siri, and Alexa); autonomous vehicles (e.g., Waymo); generative and creative tools (e.g., ChatGPT and AI art); and superhuman play and analysis in strategy games (e.g., chess and Go). However, many AI applications are not perceived as AI: "A lot of cutting edge AI has filtered into general applications, often without being called AI because once something becomes useful enough and common enough it's not labeled AI anymore."[2][3]

Various subfields of AI research are centered around particular goals and the use of particular tools. The traditional goals of AI research include reasoning, knowledge representation, planning, learning, natural language processing, perception, and support for robotics.[a] General intelligence—the ability to complete any task performed by a human on an at least equal level—is among the field's long-term goals.[4] To reach these goals, AI researchers have adapted and integrated a wide range of techniques, including search and mathematical optimization, formal logic, artificial neural networks, and methods based on statistics, operations research, and economics.[b] AI also draws upon psychology, linguistics, philosophy, neuroscience, and other fields.[5]

Artificial intelligence was founded as an academic discipline in 1956,[6] and the field went through multiple cycles of optimism throughout its history,[7][8] followed by periods of disappointment and loss of funding, known as AI winters.[9][10] Funding and interest vastly increased after 2012 when deep learning outperformed previous AI techniques.[11] This growth accelerated further after 2017 with the transformer architecture,[12] and by the early 2020s many billions of dollars were being invested in AI and the field experienced rapid ongoing progress in what has become known as the AI boom. The emergence of advanced generative AI in the midst of the AI boom and its ability to create and modify content exposed several unintended consequences and harms in the present and raised concerns about the risks of AI and its long-term effects in the future, prompting discussions about regulatory policies to ensure the safety and benefits of the technology.
"""

question = "which ones AI applied for?"

# Format input for the T5 model
input_text = f"question: {question} context: {context} </s>"
input_ids = tokenizer.encode(input_text, return_tensors="pt")

# Generate answer
model.eval()
with torch.no_grad():
    output_ids = model.generate(
        input_ids,
        max_length=100,  # Tăng độ dài câu trả lời
        num_beams=15,   # Sử dụng nhiều beam hơn
        temperature=0.7,  # Điều chỉnh tính sáng tạo
        repetition_penalty=2.0,  # Giảm trùng lặp
        early_stopping=True
    )

# Decode the answer
answer = tokenizer.decode(output_ids[0], skip_special_tokens=True)
answer = answer.replace("answer: ", "").strip()

print("Question:", question)
print("Answer:", answer)
>>>>>>> 2a2eb86c2056c80c06c9171fab2aa27892dc910c
