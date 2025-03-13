import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import os, re, random, sqlite3, webbrowser, subprocess, requests
import requests_cache  # Thư viện cache cho requests
import screen_brightness_control as sbc
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import spacy
from dateutil import parser  # Dùng để parse chuỗi thời gian

# Tải mô hình spaCy (cho tiếng Anh)
nlp = spacy.load("en_core_web_sm")

# -----------------------------------------------------------------------------
# KHỞI TẠO CƠ SỞ DỮ LIỆU: learned_knowledge, interactions, user_profile, song_usage, app_usage
# -----------------------------------------------------------------------------
conn = sqlite3.connect('knowledge.db', check_same_thread=False)
cursor = conn.cursor()

# learned_knowledge
cursor.execute('''
CREATE TABLE IF NOT EXISTS learned_knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT UNIQUE NOT NULL,
    data TEXT NOT NULL
)
''')
conn.commit()

# interactions
cursor.execute('''
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_message TEXT NOT NULL,
    ai_response TEXT NOT NULL
)
''')
conn.commit()

# user_profile (bao gồm username, location, preferences, score)
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE,
    username TEXT,
    location TEXT,
    preferences TEXT,
    score INTEGER DEFAULT 0
)
''')
conn.commit()

# song_usage
cursor.execute('''
CREATE TABLE IF NOT EXISTS song_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_title TEXT UNIQUE,
    play_count INTEGER,
    genre TEXT
)
''')
conn.commit()

# app_usage
cursor.execute('''
CREATE TABLE IF NOT EXISTS app_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT UNIQUE,
    usage_count INTEGER
)
''')
conn.commit()

# -----------------------------------------------------------------------------
# QUẢN LÝ HỒ SƠ NGƯỜI DÙNG & HỆ THỐNG THƯỞNG – PHẠT
# -----------------------------------------------------------------------------
def get_user_profile(uid):
    conn = sqlite3.connect('knowledge.db')
    cursor = conn.cursor()

    cursor.execute("SELECT username, location, preferences, score FROM user_profile WHERE uid = ?", (uid,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "username": row[0] or "",  
            "location": row[1] or "",
            "preferences": row[2] or "",
            "score": row[3] or 0
        }
    return None  # Không có user này


def update_user_profile(uid, username=None, location=None, preferences=None):
    conn = sqlite3.connect('knowledge.db')
    cursor = conn.cursor()

    profile = get_user_profile(uid)

    new_username = username if username else profile["username"] if profile else ""
    new_location = location if location else profile["location"] if profile else ""
    new_preferences = preferences if preferences else profile["preferences"] if profile else ""
    new_score = profile["score"] if profile else 0

    cursor.execute("SELECT COUNT(*) FROM user_profile WHERE uid = ?", (uid,))
    exists = cursor.fetchone()[0] > 0

    if exists:
        cursor.execute(
            "UPDATE user_profile SET username=?, location=?, preferences=?, score=? WHERE uid=?",
            (new_username, new_location, new_preferences, new_score, uid),
        )
    else:
        cursor.execute(
            "INSERT INTO user_profile (uid, username, location, preferences, score) VALUES (?, ?, ?, ?, ?)",
            (uid, new_username, new_location, new_preferences, new_score),
        )

    conn.commit()
    conn.close()



def get_reward_score() -> int:
    profile = get_user_profile()
    if profile and profile.get("score") is not None:
        return profile["score"]
    return 0

def update_reward_score(delta: int):
    profile = get_user_profile()
    if profile:
        new_score = profile.get("score", 0) + delta
        cursor.execute("UPDATE user_profile SET score = ? WHERE id = 1", (new_score,))
        conn.commit()

def process_negative_feedback(feedback: str) -> str:
    negative_keywords = ["no", "wrong", "that not right", "incorrect", "not correct"]
    if any(kw in feedback.lower() for kw in negative_keywords):
        update_reward_score(-5)
        return "Negative feedback noted. Your reward score has been reduced."
    return ""

# -----------------------------------------------------------------------------
# GHI NHẬN SỬ DỤNG: bài hát & ứng dụng
# -----------------------------------------------------------------------------
def log_song_play(song_title: str, genre: str = None):
    cursor.execute("SELECT play_count, genre FROM song_usage WHERE song_title = ?", (song_title,))
    row = cursor.fetchone()
    if row:
        play_count = row[0] + 1
        updated_genre = genre if genre and (row[1] is None or row[1]=="") else row[1]
        cursor.execute("UPDATE song_usage SET play_count = ?, genre = ? WHERE song_title = ?", 
                       (play_count, updated_genre, song_title))
    else:
        play_count = 1
        cursor.execute("INSERT INTO song_usage (song_title, play_count, genre) VALUES (?, ?, ?)", 
                       (song_title, play_count, genre))
    conn.commit()

def log_app_usage(app_name: str):
    cursor.execute("SELECT usage_count FROM app_usage WHERE app_name = ?", (app_name,))
    row = cursor.fetchone()
    if row:
        usage_count = row[0] + 1
        cursor.execute("UPDATE app_usage SET usage_count = ? WHERE app_name = ?", (usage_count, app_name))
    else:
        usage_count = 1
        cursor.execute("INSERT INTO app_usage (app_name, usage_count) VALUES (?, ?)", (app_name, usage_count))
    conn.commit()

# -----------------------------------------------------------------------------
# CÁC HÀM TRÍCH XUẤT THỰC THỂ CHO CÁC LỆNH
# -----------------------------------------------------------------------------
def refine_query(query: str) -> str:
    doc = nlp(query)
    entities = [ent.text for ent in doc.ents]
    noun_chunks = [chunk.text for chunk in doc.noun_chunks]
    refined_terms = list(set(entities + noun_chunks))
    refined_query = query + " " + " ".join(refined_terms)
    return refined_query.strip()

def extract_app_name_spacy(command: str) -> str:
    command_clean = command.lower().strip()
    if command_clean.startswith("open "):
        command_clean = command_clean[len("open "):].strip()
    doc = nlp(command_clean)
    candidates = [ent.text for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT"]]
    if candidates:
        return candidates[0].lower()
    noun_chunks = [chunk.text for chunk in doc.noun_chunks]
    if noun_chunks:
        return noun_chunks[0].lower()
    return command_clean

def extract_music_query(command: str) -> str:
    command_clean = command.lower().strip()
    if command_clean.startswith("play "):
        command_clean = command_clean[len("play "):].strip()
    doc = nlp(command_clean)
    candidates = [ent.text for ent in doc.ents if ent.label_ == "WORK_OF_ART"]
    if candidates:
        return candidates[0]
    noun_chunks = [chunk.text for chunk in doc.noun_chunks]
    if noun_chunks:
        return noun_chunks[-1]
    return command_clean

def extract_location(command: str) -> str:
    doc = nlp(command)
    for ent in doc.ents:
        if ent.label_ == "GPE":
            return ent.text
    return command.lower().replace("weather", "").strip()

def extract_appointment_details(command: str) -> dict:
    doc = nlp(command)
    details = {"person": None, "datetime_str": None}
    persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
    if persons:
        details["person"] = persons[0]
    else:
        m = re.search(r"with\s+([\w\s]+)", command, re.IGNORECASE)
        if m:
            details["person"] = m.group(1).strip()
    time_entities = [ent.text for ent in doc.ents if ent.label_ in ["TIME", "DATE"]]
    if time_entities:
        details["datetime_str"] = " ".join(time_entities)
    else:
        m_time = re.search(r"\d{1,2}:\d{2}", command)
        if m_time:
            details["datetime_str"] = m_time.group(0)
    return details

# -----------------------------------------------------------------------------
# TÍNH NĂNG ĐẶT LỊCH HẸN
# -----------------------------------------------------------------------------
def handle_set_appointment(command: str) -> str:
    details = extract_appointment_details(command)
    if not details["person"]:
        update_reward_score(-5)
        return "Không xác định được người cần gặp. Vui lòng cung cấp tên người bạn muốn hẹn."
    if details["datetime_str"]:
        try:
            dt = parser.parse(details["datetime_str"], fuzzy=True, default=datetime.now())
        except Exception:
            dt = None
    else:
        dt = None
    now = datetime.now()
    if not dt or dt < now:
        dt = now + timedelta(days=1)
        dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
    start_time = dt
    end_time = start_time + timedelta(hours=1)
    service = authenticate_google_calendar()
    event_link = create_event(service, f"Meeting with {details['person']}",
                              start_time.isoformat(), end_time.isoformat())
    update_reward_score(10)
    return (f"Lịch hẹn đã được đặt với {details['person']} vào "
            f"{start_time.strftime('%Y-%m-%d %I:%M %p')}. "
            f"Bạn có thể xem lịch hẹn tại: {event_link}")

# -----------------------------------------------------------------------------
# TÍNH NĂNG TÌM WEBSITE CHÍNH THỨC VỚI GOOGLE CUSTOM SEARCH API
# -----------------------------------------------------------------------------
def search_official_website(app_name: str) -> str:
    query = f"{app_name} official website"
    GOOGLE_API_KEY = "AIzaSyAyzKTHtZizjO4AV7jZrk8Z9IqgeOV-kAk"
    SEARCH_ENGINE_ID = "44b740bae2e4045a8"
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": SEARCH_ENGINE_ID, "q": query, "num": 1}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            link = data["items"][0].get("link", None)
            return link
        else:
            return None
    except Exception:
        return None

# -----------------------------------------------------------------------------
# CẤU HÌNH CACHE CHO TRA CỨU MẠNG
# -----------------------------------------------------------------------------
requests_cache.install_cache('search_cache', backend='sqlite', expire_after=1800)

# -----------------------------------------------------------------------------
# PHẦN GHI NHẬN TƯƠNG TÁC & TRI THỨC
# -----------------------------------------------------------------------------
def log_interaction(user_message: str, ai_response: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO interactions (timestamp, user_message, ai_response) VALUES (?, ?, ?)",
                   (timestamp, user_message, ai_response))
    conn.commit()

def get_learned_responses(topic: str):
    topic_norm = topic.strip().lower()
    cursor.execute("SELECT data FROM learned_knowledge WHERE topic = ?", (topic_norm,))
    rows = cursor.fetchall()
    return [row[0] for row in rows]

def add_learned_responses(topic: str, data: str):
    topic_norm = topic.strip().lower()
    cursor.execute("INSERT OR REPLACE INTO learned_knowledge (topic, data) VALUES (?, ?)", (topic_norm, data))
    conn.commit()

# -----------------------------------------------------------------------------
# PHẦN TRI THỨC: GOOGLE CUSTOM SEARCH API
# -----------------------------------------------------------------------------
def enhanced_aggregate_search_results(query: str, num_results: int = 5) -> str:
    GOOGLE_API_KEY = "AIzaSyAyzKTHtZizjO4AV7jZrk8Z9IqgeOV-kAk"
    SEARCH_ENGINE_ID = "44b740bae2e4045a8"
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": SEARCH_ENGINE_ID, "q": query, "num": num_results}
    try:
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        snippets = []
        if "items" in data:
            for item in data["items"]:
                snippet = item.get("snippet", "")
                if snippet:
                    snippets.append(snippet)
        if not snippets:
            return "No relevant search results found."
        aggregated_text = "\n".join(snippets)
        return aggregated_text
    except requests.exceptions.RequestException as e:
        return f"Error fetching search results: {e}"

# -----------------------------------------------------------------------------
# PHẦN SINH CÂU TRẢ LỜI: FLAN-T5
# -----------------------------------------------------------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer_gen = AutoTokenizer.from_pretrained("google/flan-t5-small")
model_gen = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")
model_gen.to(device)

def generate_multiple_answers(aggregated_text: str, num_sequences: int = 2) -> list:
    prompt = f"Using the following context, generate a comprehensive, detailed, and accurate answer to the user's query. Make sure to include all relevant steps and information if applicable:\n{aggregated_text}"
    inputs = tokenizer_gen.encode(prompt, return_tensors="pt", max_length=512, truncation=True).to(device)
    outputs = model_gen.generate(inputs, num_beams=3, max_length=200, num_return_sequences=num_sequences,
                                   temperature=0.8, top_p=0.9, repetition_penalty=1.1, early_stopping=True)
    answers = [tokenizer_gen.decode(output, skip_special_tokens=True) for output in outputs]
    return answers

def generate_flexible_response(raw_data: str) -> str:
    prompt = (
        "Using the following context, generate a comprehensive, detailed, and accurate answer "
        "to the user's query. Make sure to include all relevant steps and information if applicable:\n"
        f"{raw_data}"
    )
    inputs = tokenizer_gen.encode(prompt, return_tensors="pt", max_length=512, truncation=True).to(device)
    outputs = model_gen.generate(inputs, num_beams=3, max_length=150, early_stopping=True, temperature=0.7)
    return tokenizer_gen.decode(outputs[0], skip_special_tokens=True)

# -----------------------------------------------------------------------------
# PHẦN QA CỐ ĐỊNH VỀ BẢN THÂN AI
# -----------------------------------------------------------------------------
ai_qa = {
    "intro": {
        "patterns": ["who are you", "what are you", "what is your name"],
        "responses": [
            "I am Trinity - A multi-purpose virtual assistant developed by the AI Engineers team from Vaa.",
            "My name is Trinity. I am a new generation virtual assistant capable of multitasking and system control."
        ]
    },
    "creator": {
        "patterns": ["who created you", "who developed you"],
        "responses": [
            "I was developed by the AI research team at Vaa with the mission of supporting people in their daily work.",
            "The AI engineering team from Vietnam created me with the desire to bring the most advanced technological experience to users."
        ]
    },
    "capabilities": {
        "patterns": ["what can you do", "your function"],
        "responses": [
            "I can help you: Control devices, manage schedules, find information, play music, and more!",
            "My tasks include: System control, intelligent virtual assistant, work and entertainment support."
        ]
    },
    "personality": {
        "patterns": ["are you human", "do you have feelings", "are you a robot"],
        "responses": [
            "I am an artificial intelligence, without feelings but always trying to communicate naturally!",
            "I am an AI program designed to understand and respond like a human."
        ]
    }
}

def handle_ai_question(command: str) -> str:
    command_lower = command.lower()
    for category, data in ai_qa.items():
        for pattern in data["patterns"]:
            if pattern in command_lower:
                return random.choice(data["responses"])
    return None

# -----------------------------------------------------------------------------
# PHẦN XỬ LÝ LỆNH HỆ THỐNG (shutdown, restart, brightness, mute, unmute)
# -----------------------------------------------------------------------------
def mute_sound() -> str:
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMute(1, None)
    return "Sound muted."

def unmute_sound() -> str:
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMute(0, None)
    return "Sound unmuted."

def increase_brightness() -> str:
    current_brightness = sbc.get_brightness()[0]
    new_brightness = min(current_brightness + 10, 100)
    sbc.set_brightness(new_brightness)
    return f"Increased brightness to {new_brightness}%"

def decrease_brightness() -> str:
    current_brightness = sbc.get_brightness()[0]
    new_brightness = max(current_brightness - 10, 0)
    sbc.set_brightness(new_brightness)
    return f"Decreased brightness to {new_brightness}%"

def handle_system_command(command: str) -> str:
    command_lower = command.lower()
    if "shut down" in command_lower or "turn off" in command_lower:
        os.system("shutdown /s /t 1")
        return "Shutting down the computer..."
    elif "restart" in command_lower or "reboot" in command_lower:
        os.system("shutdown /r /t 1")
        return "Restarting the computer..."
    elif "increase brightness" in command_lower:
        return increase_brightness()
    elif "decrease brightness" in command_lower:
        return decrease_brightness()
    elif "unmute" in command_lower:
        return unmute_sound()
    elif "mute" in command_lower:
        return mute_sound()
    else:
        return "System command not recognized."

# -----------------------------------------------------------------------------
# PHẦN XỬ LÝ ỨNG DỤNG & NHẠC
# -----------------------------------------------------------------------------
# Mapping local ứng dụng (chỉ chứa các ứng dụng chạy file .exe)
app_mapping = {
    "chrome": "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "spotify": "spotify.exe",
    "word": "C:/Program Files/Microsoft Office/root/Office16/WINWORD.EXE",
    "excel": "C:/Program Files/Microsoft Office/root/Office16/EXCEL.EXE",
    "powerpoint": "C:/Program Files/Microsoft Office/root/Office16/POWERPNT.EXE",
    "vscode": "C:/Users/YourUsername/AppData/Local/Programs/Microsoft VS Code/Code.exe",
}

def search_official_website(app_name: str) -> str:
    query = f"{app_name} official website"
    GOOGLE_API_KEY = "AIzaSyAyzKTHtZizjO4AV7jZrk8Z9IqgeOV-kAk"
    SEARCH_ENGINE_ID = "44b740bae2e4045a8"
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_API_KEY, "cx": SEARCH_ENGINE_ID, "q": query, "num": 1}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "items" in data and len(data["items"]) > 0:
            link = data["items"][0].get("link", None)
            return link
        else:
            return None
    except Exception:
        return None

def open_application(app_name: str) -> str:
    """
    Thử mở ứng dụng bằng file .exe dựa trên mapping.
    Nếu không thành công, sử dụng Google Custom Search API để tìm URL website chính thức
    và mở kết quả tìm được.
    Ghi nhận lượt sử dụng và cộng điểm thưởng.
    """
    app_name = app_name.lower()
    if app_name in app_mapping:
        app_path = app_mapping[app_name]
        if not app_path.startswith("http"):
            try:
                subprocess.Popen(app_path)
                log_app_usage(app_name)
                update_reward_score(2)
                return f"Opening {app_name}..."
            except Exception:
                website_url = search_official_website(app_name)
                if website_url:
                    webbrowser.open(website_url)
                    log_app_usage(app_name)
                    update_reward_score(1)
                    return f"Could not open local app. Opened official website: {website_url}"
                else:
                    return f"Could not open {app_name}."
        else:
            webbrowser.open(app_path)
            log_app_usage(app_name)
            update_reward_score(2)
            return f"Opening {app_name} in your browser..."
    else:
        website_url = search_official_website(app_name)
        if website_url:
            webbrowser.open(website_url)
            log_app_usage(app_name)
            update_reward_score(1)
            return f"Application '{app_name}' is not in local mapping. Opened official website: {website_url}"
        else:
            return f"Application '{app_name}' is not supported."

def handle_open_application(command: str) -> str:
    app_name = extract_app_name_spacy(command)
    if app_name:
        return open_application(app_name)
    else:
        return "Invalid command. Please specify an application to open."

def play_on_youtube(query: str) -> str:
    request = youtube.search().list(q=query, part="snippet", type="video,playlist", maxResults=1)
    response = request.execute()
    result = response["items"][0] if response["items"] else None
    if result:
        if result["id"]["kind"] == "youtube#video":
            video_id = result["id"]["videoId"]
            url = f"https://www.youtube.com/watch?v={video_id}"
        elif result["id"]["kind"] == "youtube#playlist":
            playlist_id = result["id"]["playlistId"]
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
        webbrowser.open(url)
        log_song_play(query)
        update_reward_score(3)
        return f"Playing '{query}' on YouTube..."
    else:
        return f"No results found for '{query}'."

def handle_play_music(command: str) -> str:
    if command.lower().strip() == "play music":
        cursor.execute("SELECT song_title FROM song_usage ORDER BY play_count DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            favorite_song = row[0]
            update_reward_score(5)
            return play_on_youtube(favorite_song)
        else:
            return "No favorite song data found. Please specify a song to play."
    else:
        music_query = extract_music_query(command)
        if music_query:
            update_reward_score(2)
            return play_on_youtube(music_query)
        else:
            return "Music command not recognized."

# -----------------------------------------------------------------------------
# PHẦN NHẠC: KHỞI TẠO YOUTUBE API
# -----------------------------------------------------------------------------
API_KEY = "AIzaSyAyzKTHtZizjO4AV7jZrk8Z9IqgeOV-kAk"
youtube = build("youtube", "v3", developerKey=API_KEY)

# -----------------------------------------------------------------------------
# PHẦN LỊCH HẸN (Google Calendar API)
# -----------------------------------------------------------------------------
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_calendar():
    creds = None
    if os.path.exists('token.json'):
        try:
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        except ValueError as e:
            print(f"Error loading credentials: {e}")
            os.remove('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    return service

def create_event(service, summary, start_time, end_time, description=None, location=None):
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {'dateTime': start_time, 'timeZone': 'Asia/Ho_Chi_Minh'},
        'end': {'dateTime': end_time, 'timeZone': 'Asia/Ho_Chi_Minh'},
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return event.get('htmlLink')

def get_upcoming_appointments(limit=5) -> list:
    service = authenticate_google_calendar()
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=limit, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

# -----------------------------------------------------------------------------
# PHẦN TRI THỨC & TRA CỨU (FLAN-T5)
# -----------------------------------------------------------------------------
def normalize_topic(query: str) -> str:
    query_lower = query.strip().lower()
    if "how to" in query_lower:
        return "how to " + query_lower.replace("how to", "").strip()
    elif "what is" in query_lower:
        return "what is " + query_lower.replace("what is", "").strip()
    else:
        return query_lower

def compute_answer_quality(answer: str) -> float:
    return 0.8 if len(answer) > 50 else 0.5

def handle_knowledge_query_custom(query: str) -> str:
    topic_key = normalize_topic(query)
    learned = get_learned_responses(topic_key)
    if learned:
        raw_data = learned[0]
    else:
        refined_query = refine_query(query)
        raw_data = enhanced_aggregate_search_results(refined_query, num_results=5)
    
    answer = generate_flexible_response(raw_data)
    quality = compute_answer_quality(answer)
    automatic_accept_threshold = 0.75
    if quality >= automatic_accept_threshold:
        print("\nAI's answer:")
        print(answer)
        if not learned:
            add_learned_responses(topic_key, raw_data)
        update_reward_score(2)
        return answer
    else:
        print("\nInitial answer quality low, trying alternative search results...")
        alternative_raw_data = enhanced_aggregate_search_results(refine_query(query), num_results=10)
        alternative_answer = generate_flexible_response(alternative_raw_data)
        quality2 = compute_answer_quality(alternative_answer)
        if quality2 >= automatic_accept_threshold:
            print("\nAI's improved answer:")
            print(alternative_answer)
            if not learned:
                add_learned_responses(topic_key, alternative_raw_data)
            update_reward_score(1)
            return alternative_answer
        else:
            print("\nQuality still low after alternative search.")
            feedback = input("Please provide the correct information for this query: ").strip()
            if feedback:
                add_learned_responses(topic_key, feedback)
                new_answer = generate_flexible_response(feedback)
                update_reward_score(5)
                return f"Thank you for your feedback. Here is the updated answer:\n{new_answer}"
            else:
                update_reward_score(-5)
                return "No new information provided. Using initial answer:\n" + answer

def dynamic_respond(query: str) -> str:
    query_lower = query.lower()
    for category, data in ai_qa.items():
        for pattern in data["patterns"]:
            if re.search(pattern, query, re.IGNORECASE):
                return random.choice(data["responses"])
    if "how to" in query_lower or "what is" in query_lower:
        return handle_knowledge_query_custom(query)
    learned = get_learned_responses(query)
    if learned:
        basic_data = random.choice(learned)
        return generate_flexible_response(basic_data)
    user_input = input(f"I don't know about '{query}'. Can you teach me? ").strip()
    if user_input:
        add_learned_responses(query, user_input)
        return generate_flexible_response(user_input)
    else:
        return f"Sorry, I don't have any information about '{query}'."

def learn_new_knowledge(query: str) -> str:
    if "how to" in query.lower() or "what is" in query.lower():
        return handle_knowledge_query_custom(query)
    else:
        user_input = input(f"Can you teach me about '{query}'? ").strip()
        if user_input:
            add_learned_responses(query, user_input)
            return generate_flexible_response(user_input)
        else:
            return f"Thanks, I've learned about '{query}'."

# -----------------------------------------------------------------------------
# PHẦN KIỂM TRA THỜI TIẾT VÀ LỜI KHUYẾN
# -----------------------------------------------------------------------------
def get_weather(city_name: str, api_key: str) -> str:
    base_url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": api_key, "q": city_name}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        temperature = weather_data["current"]["temp_c"]
        weather_description = weather_data["current"]["condition"]["text"]
        humidity = weather_data["current"]["humidity"]
        wind_speed = weather_data["current"]["wind_kph"]
        upcoming = get_upcoming_appointments(limit=1)
        if any(keyword in weather_description.lower() for keyword in ["rain", "storm", "snow", "hail"]):
            advice = "It looks like bad weather; if you go out, remember to bring an umbrella and warm clothes."
        elif not upcoming:
            advice = "The weather is beautiful and you have no appointments today. How about going out for a walk or exercise?"
        else:
            advice = "The weather is pleasant, but you have appointments scheduled."
        return (f"Weather in {city_name}: {weather_description}, "
                f"Temperature: {temperature}°C, Humidity: {humidity}%, "
                f"Wind Speed: {wind_speed} km/h. {advice}")
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "Error: Invalid API Key."
        elif response.status_code == 400:
            return f"Error: City '{city_name}' not found."
        else:
            return f"Error fetching weather data: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"

def handle_check_weather(command: str, api_key: str) -> str:
    city_name = extract_location(command)
    if city_name:
        city_name = city_name.title()
        update_reward_score(1)
        return get_weather(city_name, api_key)
    else:
        return "Please specify a city name."

WEATHERAPI_API_KEY = "5e65619e9ff54500a5c62422250103"

# -----------------------------------------------------------------------------
# PHẦN NHẮC LẠI LỊCH HẸN
# -----------------------------------------------------------------------------
def check_appointment_reminders() -> str:
    events = get_upcoming_appointments()
    if events:
        reminders = "Upcoming appointments:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt = parser.parse(start)
            reminders += f"- {event['summary']} at {dt.strftime('%Y-%m-%d %I:%M %p')}\n"
        return reminders
    else:
        return "No upcoming appointments found."

# -----------------------------------------------------------------------------
# TÍNH NĂNG CÁ NHÂN HÓA: CHÈN TÊN NGƯỜI DÙNG VÀ ĐIỂM THƯỞNG
# -----------------------------------------------------------------------------
def personalize_response(response: str) -> str:
    profile = get_user_profile()
    if profile and profile.get("username"):
        return f"Hello {profile['username']}, {response}"
    return response

def handle_set_username(command: str) -> str:
    m = re.search(r"(?:set my name as|my name is)\s+(.*)", command, re.IGNORECASE)
    if m:
        username = m.group(1).strip()
        update_user_profile(username=username)
        update_reward_score(10)
        return f"Your name has been set to {username}."
    else:
        update_reward_score(-5)
        return "Could not extract your name. Please try again."

def handle_set_location(command: str) -> str:
    m = re.search(r"(?:set my location as|my location is)\s+(.*)", command, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        update_user_profile(location=location)
        update_reward_score(5)
        return f"Your location has been set to {location}."
    else:
        update_reward_score(-5)
        return "Could not extract your location. Please try again."

def greet_user(uid, username=None, location=None) -> dict:
    """Trả về lời chào hoặc yêu cầu nhập thông tin nếu thiếu username hoặc location."""
    profile = get_user_profile(uid)  # ✅ Truy vấn user theo UID

    # Trường hợp 1: Nếu chưa có username
    if not profile or not profile.get("username"):
        if not username:
            return {"error": "missing_username", "message": "Vui lòng nhập tên của bạn."}
        update_user_profile(uid, username=username)  # ✅ Cập nhật username

    # Trường hợp 2: Nếu chưa có location
    profile = get_user_profile(uid)  # ✅ Lấy lại profile sau khi cập nhật username
    if not profile.get("location"):
        if not location:
            return {"error": "missing_location", "message": "Vui lòng nhập vị trí của bạn."}
        update_user_profile(uid, location=location)  # ✅ Cập nhật location

    # Nếu đủ thông tin, trả về lời chào kèm thời tiết
    profile = get_user_profile(uid)  # ✅ Lấy profile sau khi cập nhật thông tin
    weather_info = get_weather(profile["location"], WEATHERAPI_API_KEY)
    score = profile["score"]

    return {"message": f"Hello {profile['username']}! Your current reward score is {score}. {weather_info}"}





# -----------------------------------------------------------------------------
# PHẦN THỐNG KÊ & GỢI Ý CÁ NHÂN HÓA
# -----------------------------------------------------------------------------
def get_frequent_songs(limit=3):
    cursor.execute("SELECT song_title, play_count, genre FROM song_usage ORDER BY play_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def get_frequent_apps(limit=3):
    cursor.execute("SELECT app_name, usage_count FROM app_usage ORDER BY usage_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def print_user_statistics():
    profile = get_user_profile()
    if profile:
        print(f"User Profile: {profile}")
    else:
        print("No user profile found.")
    print("\nFrequently Played Songs:")
    songs = get_frequent_songs()
    if songs:
        for song in songs:
            print(f"  - Song: {song[0]}, Played: {song[1]} times, Genre: {song[2]}")
    else:
        print("  No song usage data available.")
    print("\nFrequently Used Applications:")
    apps = get_frequent_apps()
    if apps:
        for app in apps:
            print(f"  - App: {app[0]}, Used: {app[1]} times")
    else:
        print("  No app usage data available.")
    cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM interactions")
    total, first_time, last_time = cursor.fetchone()
    print(f"\nTotal interactions: {total}")
    print(f"From {first_time} to {last_time}")

def recommend_song():
    songs = get_frequent_songs(limit=1)
    if songs:
        top_song = songs[0]
        return f"Based on your listening habits, you seem to love '{top_song[0]}' in the {top_song[2]} genre."
    return "No song data available for recommendations."

def recommend_app():
    apps = get_frequent_apps(limit=1)
    if apps:
        top_app = apps[0]
        return f"You frequently use '{top_app[0]}'. Consider exploring its advanced features!"
    return "No application data available for recommendations."

def display_personalized_recommendations():
    print("\n--- USER STATISTICS ---")
    print_user_statistics()
    print("\n--- RECOMMENDATIONS ---")
    print(recommend_song())
    print(recommend_app())
    print("\n--- Upcoming Appointments ---")
    reminders = check_appointment_reminders()
    print(reminders)

# -----------------------------------------------------------------------------
# PHẦN XỬ LÝ TRI THỨC: FLAN-T5 với phản hồi tiêu cực và thử kết quả tìm kiếm khác
# -----------------------------------------------------------------------------
def handle_knowledge_query_custom(query: str) -> str:
    topic_key = normalize_topic(query)
    learned = get_learned_responses(topic_key)
    if learned:
        raw_data = learned[0]
    else:
        refined_query = refine_query(query)
        raw_data = enhanced_aggregate_search_results(refined_query, num_results=5)
    
    answer = generate_flexible_response(raw_data)
    quality = compute_answer_quality(answer)
    automatic_accept_threshold = 0.75

    if quality >= automatic_accept_threshold:
        print("\nAI's answer:")
        print(answer)
        if not learned:
            add_learned_responses(topic_key, raw_data)
        update_reward_score(2)
        return answer
    else:
        print("\nInitial answer quality low, trying alternative search results...")
        alternative_raw_data = enhanced_aggregate_search_results(refine_query(query), num_results=10)
        alternative_answer = generate_flexible_response(alternative_raw_data)
        quality2 = compute_answer_quality(alternative_answer)
        if quality2 >= automatic_accept_threshold:
            print("\nAI's improved answer:")
            print(alternative_answer)
            if not learned:
                add_learned_responses(topic_key, alternative_raw_data)
            update_reward_score(1)
            return alternative_answer
        else:
            print("\nQuality still low after alternative search.")
            feedback = input("Please provide the correct information for this query: ").strip()
            if feedback:
                add_learned_responses(topic_key, feedback)
                new_answer = generate_flexible_response(feedback)
                update_reward_score(5)
                return f"Thank you for your feedback. Here is the updated answer:\n{new_answer}"
            else:
                update_reward_score(-5)
                return "No new information provided. Using initial answer:\n" + answer

def dynamic_respond(query: str) -> str:
    query_lower = query.lower()
    for category, data in ai_qa.items():
        for pattern in data["patterns"]:
            if re.search(pattern, query, re.IGNORECASE):
                return random.choice(data["responses"])
    if "how to" in query_lower or "what is" in query_lower:
        return handle_knowledge_query_custom(query)
    learned = get_learned_responses(query)
    if learned:
        basic_data = random.choice(learned)
        return generate_flexible_response(basic_data)
    user_input = input(f"I don't know about '{query}'. Can you teach me? ").strip()
    if user_input:
        add_learned_responses(query, user_input)
        return generate_flexible_response(user_input)
    else:
        return f"Sorry, I don't have any information about '{query}'."

def learn_new_knowledge(query: str) -> str:
    if "how to" in query.lower() or "what is" in query.lower():
        return handle_knowledge_query_custom(query)
    else:
        user_input = input(f"Can you teach me about '{query}'? ").strip()
        if user_input:
            add_learned_responses(query, user_input)
            return generate_flexible_response(user_input)
        else:
            return f"Thanks, I've learned about '{query}'."

# -----------------------------------------------------------------------------
# PHẦN KIỂM TRA THỜI TIẾT VÀ LỜI KHUYẾN
# -----------------------------------------------------------------------------
def get_weather(city_name: str, api_key: str) -> str:
    if not city_name:  # Kiểm tra city_name trước khi gọi API
        return "Error: Location not provided. Please update your profile."

    base_url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": api_key, "q": city_name}

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        
        temperature = weather_data.get("current", {}).get("temp_c", "N/A")
        weather_description = weather_data.get("current", {}).get("condition", {}).get("text", "Unknown")
        humidity = weather_data.get("current", {}).get("humidity", "N/A")
        wind_speed = weather_data.get("current", {}).get("wind_kph", "N/A")

        upcoming = get_upcoming_appointments(limit=1)
        if any(keyword in str(weather_description).lower() for keyword in ["rain", "storm", "snow", "hail"]):
            advice = "It looks like bad weather; if you go out, remember to bring an umbrella and warm clothes."
        elif not upcoming:
            advice = "The weather is beautiful and you have no appointments today. How about going out for a walk or exercise?"
        else:
            advice = "The weather is pleasant, but you have appointments scheduled."

        return (f"Weather in {city_name}: {weather_description}, "
                f"Temperature: {temperature}°C, Humidity: {humidity}%, "
                f"Wind Speed: {wind_speed} km/h. {advice}")
    except requests.exceptions.HTTPError as e:
        if 'response' in locals() and response.status_code == 401:
            return "Error: Invalid API Key."
        elif 'response' in locals() and response.status_code == 400:
            return f"Error: City '{city_name}' not found."
        else:
            return f"Error fetching weather data: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"


def handle_check_weather(command: str, api_key: str) -> str:
    city_name = extract_location(command)
    if city_name:
        city_name = city_name.title()
        update_reward_score(1)
        return get_weather(city_name, api_key)
    else:
        return "Please specify a city name."

WEATHERAPI_API_KEY = "5e65619e9ff54500a5c62422250103"

# -----------------------------------------------------------------------------
# PHẦN NHẮC LẠI LỊCH HẸN
# -----------------------------------------------------------------------------
def check_appointment_reminders() -> str:
    events = get_upcoming_appointments()
    if events:
        reminders = "Upcoming appointments:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt = parser.parse(start)
            reminders += f"- {event['summary']} at {dt.strftime('%Y-%m-%d %I:%M %p')}\n"
        return reminders
    else:
        return "No upcoming appointments found."

# -----------------------------------------------------------------------------
# TÍNH NĂNG CÁ NHÂN HÓA: CHÈN TÊN NGƯỜI DÙNG VÀ ĐIỂM THƯỞNG
# -----------------------------------------------------------------------------
def personalize_response(response: str) -> str:
    profile = get_user_profile()
    if profile and profile.get("username"):
        return f"Hello {profile['username']}, {response}"
    return response

def handle_set_username(command: str) -> str:
    m = re.search(r"(?:set my name as|my name is)\s+(.*)", command, re.IGNORECASE)
    if m:
        username = m.group(1).strip()
        update_user_profile(username=username)
        update_reward_score(10)
        return f"Your name has been set to {username}."
    else:
        update_reward_score(-5)
        return "Could not extract your name. Please try again."

def handle_set_location(command: str) -> str:
    m = re.search(r"(?:set my location as|my location is)\s+(.*)", command, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        update_user_profile(location=location)
        update_reward_score(5)
        return f"Your location has been set to {location}."
    else:
        update_reward_score(-5)
        return "Could not extract your location. Please try again."

def greet_user(uid, username=None, location=None) -> dict:
    """Trả về lời chào hoặc yêu cầu nhập thông tin nếu thiếu username hoặc location."""
    profile = get_user_profile(uid)  # ✅ Truy vấn user theo UID

    # Trường hợp 1: Nếu chưa có username
    if not profile or not profile.get("username"):
        if not username:
            return {"error": "missing_username", "message": "Vui lòng nhập tên của bạn."}
        update_user_profile(uid, username=username)  # ✅ Cập nhật username

    # Trường hợp 2: Nếu chưa có location
    profile = get_user_profile(uid)  # ✅ Lấy lại profile sau khi cập nhật username
    if not profile.get("location"):
        if not location:
            return {"error": "missing_location", "message": "Vui lòng nhập vị trí của bạn."}
        update_user_profile(uid, location=location)  # ✅ Cập nhật location

    # Nếu đủ thông tin, trả về lời chào kèm thời tiết
    profile = get_user_profile(uid)  # ✅ Lấy profile sau khi cập nhật thông tin
    weather_info = get_weather(profile["location"], WEATHERAPI_API_KEY)
    score = profile["score"]

    return {"message": f"Hello {profile['username']}! Your current reward score is {score}. {weather_info}"}



# -----------------------------------------------------------------------------
# PHẦN THỐNG KÊ & GỢI Ý CÁ NHÂN HÓA
# -----------------------------------------------------------------------------
def get_frequent_songs(limit=3):
    cursor.execute("SELECT song_title, play_count, genre FROM song_usage ORDER BY play_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def get_frequent_apps(limit=3):
    cursor.execute("SELECT app_name, usage_count FROM app_usage ORDER BY usage_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def print_user_statistics():
    profile = get_user_profile()
    if profile:
        print(f"User Profile: {profile}")
    else:
        print("No user profile found.")
    print("\nFrequently Played Songs:")
    songs = get_frequent_songs()
    if songs:
        for song in songs:
            print(f"  - Song: {song[0]}, Played: {song[1]} times, Genre: {song[2]}")
    else:
        print("  No song usage data available.")
    print("\nFrequently Used Applications:")
    apps = get_frequent_apps()
    if apps:
        for app in apps:
            print(f"  - App: {app[0]}, Used: {app[1]} times")
    else:
        print("  No app usage data available.")
    cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM interactions")
    total, first_time, last_time = cursor.fetchone()
    print(f"\nTotal interactions: {total}")
    print(f"From {first_time} to {last_time}")

def recommend_song():
    songs = get_frequent_songs(limit=1)
    if songs:
        top_song = songs[0]
        return f"Based on your listening habits, you seem to love '{top_song[0]}' in the {top_song[2]} genre."
    return "No song data available for recommendations."

def recommend_app():
    apps = get_frequent_apps(limit=1)
    if apps:
        top_app = apps[0]
        return f"You frequently use '{top_app[0]}'. Consider exploring its advanced features!"
    return "No application data available for recommendations."

def display_personalized_recommendations():
    print("\n--- USER STATISTICS ---")
    print_user_statistics()
    print("\n--- RECOMMENDATIONS ---")
    print(recommend_song())
    print(recommend_app())
    print("\n--- Upcoming Appointments ---")
    reminders = check_appointment_reminders()
    print(reminders)

# -----------------------------------------------------------------------------
# PHẦN XỬ LÝ TRI THỨC: FLAN-T5 với cơ chế thử kết quả tìm kiếm khác
# -----------------------------------------------------------------------------
def handle_knowledge_query_custom(query: str) -> str:
    topic_key = normalize_topic(query)
    learned = get_learned_responses(topic_key)
    if learned:
        raw_data = learned[0]
    else:
        refined_query = refine_query(query)
        raw_data = enhanced_aggregate_search_results(refined_query, num_results=5)
    
    answer = generate_flexible_response(raw_data)
    quality = compute_answer_quality(answer)
    automatic_accept_threshold = 0.75
    if quality >= automatic_accept_threshold:
        print("\nAI's answer:")
        print(answer)
        if not learned:
            add_learned_responses(topic_key, raw_data)
        update_reward_score(2)
        return answer
    else:
        print("\nInitial answer quality low, trying alternative search results...")
        alternative_raw_data = enhanced_aggregate_search_results(refine_query(query), num_results=10)
        alternative_answer = generate_flexible_response(alternative_raw_data)
        quality2 = compute_answer_quality(alternative_answer)
        if quality2 >= automatic_accept_threshold:
            print("\nAI's improved answer:")
            print(alternative_answer)
            if not learned:
                add_learned_responses(topic_key, alternative_raw_data)
            update_reward_score(1)
            return alternative_answer
        else:
            print("\nQuality still low after alternative search.")
            feedback = input("Please provide the correct information for this query: ").strip()
            if feedback:
                add_learned_responses(topic_key, feedback)
                new_answer = generate_flexible_response(feedback)
                update_reward_score(5)
                return f"Thank you for your feedback. Here is the updated answer:\n{new_answer}"
            else:
                update_reward_score(-5)
                return "No new information provided. Using initial answer:\n" + answer

def dynamic_respond(query: str) -> str:
    query_lower = query.lower()
    for category, data in ai_qa.items():
        for pattern in data["patterns"]:
            if re.search(pattern, query, re.IGNORECASE):
                return random.choice(data["responses"])
    if "how to" in query_lower or "what is" in query_lower:
        return handle_knowledge_query_custom(query)
    learned = get_learned_responses(query)
    if learned:
        basic_data = random.choice(learned)
        return generate_flexible_response(basic_data)
    user_input = input(f"I don't know about '{query}'. Can you teach me? ").strip()
    if user_input:
        add_learned_responses(query, user_input)
        return generate_flexible_response(user_input)
    else:
        return f"Sorry, I don't have any information about '{query}'."

def learn_new_knowledge(query: str) -> str:
    if "how to" in query.lower() or "what is" in query.lower():
        return handle_knowledge_query_custom(query)
    else:
        user_input = input(f"Can you teach me about '{query}'? ").strip()
        if user_input:
            add_learned_responses(query, user_input)
            return generate_flexible_response(user_input)
        else:
            return f"Thanks, I've learned about '{query}'."

# -----------------------------------------------------------------------------
# PHẦN KIỂM TRA THỜI TIẾT VÀ LỜI KHUYẾN
# -----------------------------------------------------------------------------
def get_weather(city_name: str, api_key: str) -> str:
    base_url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": api_key, "q": city_name}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        temperature = weather_data["current"]["temp_c"]
        weather_description = weather_data["current"]["condition"]["text"]
        humidity = weather_data["current"]["humidity"]
        wind_speed = weather_data["current"]["wind_kph"]
        upcoming = get_upcoming_appointments(limit=1)
        if any(keyword in weather_description.lower() for keyword in ["rain", "storm", "snow", "hail"]):
            advice = "It looks like bad weather; if you go out, remember to bring an umbrella and warm clothes."
        elif not upcoming:
            advice = "The weather is beautiful and you have no appointments today. How about going out for a walk or exercise?"
        else:
            advice = "The weather is pleasant, but you have appointments scheduled."
        return (f"Weather in {city_name}: {weather_description}, "
                f"Temperature: {temperature}°C, Humidity: {humidity}%, "
                f"Wind Speed: {wind_speed} km/h. {advice}")
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "Error: Invalid API Key."
        elif response.status_code == 400:
            return f"Error: City '{city_name}' not found."
        else:
            return f"Error fetching weather data: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"

def handle_check_weather(command: str, api_key: str) -> str:
    city_name = extract_location(command)
    if city_name:
        city_name = city_name.title()
        update_reward_score(1)
        return get_weather(city_name, api_key)
    else:
        return "Please specify a city name."

WEATHERAPI_API_KEY = "5e65619e9ff54500a5c62422250103"

# -----------------------------------------------------------------------------
# PHẦN NHẮC LẠI LỊCH HẸN
# -----------------------------------------------------------------------------
def check_appointment_reminders() -> str:
    events = get_upcoming_appointments()
    if events:
        reminders = "Upcoming appointments:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt = parser.parse(start)
            reminders += f"- {event['summary']} at {dt.strftime('%Y-%m-%d %I:%M %p')}\n"
        return reminders
    else:
        return "No upcoming appointments found."

# -----------------------------------------------------------------------------
# TÍNH NĂNG CÁ NHÂN HÓA: CHÈN TÊN NGƯỜI DÙNG VÀ ĐIỂM THƯỞNG
# -----------------------------------------------------------------------------
def personalize_response(response: str) -> str:
    profile = get_user_profile()
    if profile and profile.get("username"):
        return f"Hello {profile['username']}, {response}"
    return response

def handle_set_username(command: str) -> str:
    m = re.search(r"(?:set my name as|my name is)\s+(.*)", command, re.IGNORECASE)
    if m:
        username = m.group(1).strip()
        update_user_profile(username=username)
        update_reward_score(10)
        return f"Your name has been set to {username}."
    else:
        update_reward_score(-5)
        return "Could not extract your name. Please try again."

def handle_set_location(command: str) -> str:
    m = re.search(r"(?:set my location as|my location is)\s+(.*)", command, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        update_user_profile(location=location)
        update_reward_score(5)
        return f"Your location has been set to {location}."
    else:
        update_reward_score(-5)
        return "Could not extract your location. Please try again."

def greet_user(uid, username=None, location=None) -> dict:
    """Trả về lời chào hoặc yêu cầu nhập thông tin nếu thiếu username hoặc location."""
    profile = get_user_profile(uid)  # ✅ Truy vấn user theo UID

    # Trường hợp 1: Nếu chưa có username
    if not profile or not profile.get("username"):
        if not username:
            return {"error": "missing_username", "message": "Vui lòng nhập tên của bạn."}
        update_user_profile(uid, username=username)  # ✅ Cập nhật username

    # Trường hợp 2: Nếu chưa có location
    profile = get_user_profile(uid)  # ✅ Lấy lại profile sau khi cập nhật username
    if not profile.get("location"):
        if not location:
            return {"error": "missing_location", "message": "Vui lòng nhập vị trí của bạn."}
        update_user_profile(uid, location=location)  # ✅ Cập nhật location

    # Nếu đủ thông tin, trả về lời chào kèm thời tiết
    profile = get_user_profile(uid)  # ✅ Lấy profile sau khi cập nhật thông tin
    weather_info = get_weather(profile["location"], WEATHERAPI_API_KEY)
    score = profile["score"]

    return {"message": f"Hello {profile['username']}! Your current reward score is {score}. {weather_info}"}



# -----------------------------------------------------------------------------
# PHẦN THỐNG KÊ & GỢI Ý CÁ NHÂN HÓA
# -----------------------------------------------------------------------------
def get_frequent_songs(limit=3):
    cursor.execute("SELECT song_title, play_count, genre FROM song_usage ORDER BY play_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def get_frequent_apps(limit=3):
    cursor.execute("SELECT app_name, usage_count FROM app_usage ORDER BY usage_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def print_user_statistics():
    profile = get_user_profile()
    if profile:
        print(f"User Profile: {profile}")
    else:
        print("No user profile found.")
    print("\nFrequently Played Songs:")
    songs = get_frequent_songs()
    if songs:
        for song in songs:
            print(f"  - Song: {song[0]}, Played: {song[1]} times, Genre: {song[2]}")
    else:
        print("  No song usage data available.")
    print("\nFrequently Used Applications:")
    apps = get_frequent_apps()
    if apps:
        for app in apps:
            print(f"  - App: {app[0]}, Used: {app[1]} times")
    else:
        print("  No app usage data available.")
    cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM interactions")
    total, first_time, last_time = cursor.fetchone()
    print(f"\nTotal interactions: {total}")
    print(f"From {first_time} to {last_time}")

def recommend_song():
    songs = get_frequent_songs(limit=1)
    if songs:
        top_song = songs[0]
        return f"Based on your listening habits, you seem to love '{top_song[0]}' in the {top_song[2]} genre."
    return "No song data available for recommendations."

def recommend_app():
    apps = get_frequent_apps(limit=1)
    if apps:
        top_app = apps[0]
        return f"You frequently use '{top_app[0]}'. Consider exploring its advanced features!"
    return "No application data available for recommendations."

def display_personalized_recommendations():
    print("\n--- USER STATISTICS ---")
    print_user_statistics()
    print("\n--- RECOMMENDATIONS ---")
    print(recommend_song())
    print(recommend_app())
    print("\n--- Upcoming Appointments ---")
    reminders = check_appointment_reminders()
    print(reminders)

# -----------------------------------------------------------------------------
# PHẦN XỬ LÝ TRI THỨC: FLAN-T5 với cơ chế thử kết quả tìm kiếm thay thế trước khi hỏi feedback
# -----------------------------------------------------------------------------
def handle_knowledge_query_custom(query: str) -> str:
    topic_key = normalize_topic(query)
    learned = get_learned_responses(topic_key)
    if learned:
        raw_data = learned[0]
    else:
        refined_query = refine_query(query)
        raw_data = enhanced_aggregate_search_results(refined_query, num_results=5)
    
    answer = generate_flexible_response(raw_data)
    quality = compute_answer_quality(answer)
    automatic_accept_threshold = 0.75
    if quality >= automatic_accept_threshold:
        print("\nAI's answer:")
        print(answer)
        if not learned:
            add_learned_responses(topic_key, raw_data)
        update_reward_score(2)
        return answer
    else:
        print("\nInitial answer quality low, trying alternative search results...")
        alternative_raw_data = enhanced_aggregate_search_results(refine_query(query), num_results=10)
        alternative_answer = generate_flexible_response(alternative_raw_data)
        quality2 = compute_answer_quality(alternative_answer)
        if quality2 >= automatic_accept_threshold:
            print("\nAI's improved answer:")
            print(alternative_answer)
            if not learned:
                add_learned_responses(topic_key, alternative_raw_data)
            update_reward_score(1)
            return alternative_answer
        else:
            print("\nQuality still low after alternative search.")
            feedback = input("Please provide the correct information for this query: ").strip()
            if feedback:
                add_learned_responses(topic_key, feedback)
                new_answer = generate_flexible_response(feedback)
                update_reward_score(5)
                return f"Thank you for your feedback. Here is the updated answer:\n{new_answer}"
            else:
                update_reward_score(-5)
                return "No new information provided. Using initial answer:\n" + answer

def dynamic_respond(query: str) -> str:
    query_lower = query.lower()
    for category, data in ai_qa.items():
        for pattern in data["patterns"]:
            if re.search(pattern, query, re.IGNORECASE):
                return random.choice(data["responses"])
    if "how to" in query_lower or "what is" in query_lower:
        return handle_knowledge_query_custom(query)
    learned = get_learned_responses(query)
    if learned:
        basic_data = random.choice(learned)
        return generate_flexible_response(basic_data)
    user_input = input(f"I don't know about '{query}'. Can you teach me? ").strip()
    if user_input:
        add_learned_responses(query, user_input)
        return generate_flexible_response(user_input)
    else:
        return f"Sorry, I don't have any information about '{query}'."

def learn_new_knowledge(query: str) -> str:
    if "how to" in query.lower() or "what is" in query.lower():
        return handle_knowledge_query_custom(query)
    else:
        user_input = input(f"Can you teach me about '{query}'? ").strip()
        if user_input:
            add_learned_responses(query, user_input)
            return generate_flexible_response(user_input)
        else:
            return f"Thanks, I've learned about '{query}'."

# -----------------------------------------------------------------------------
# PHẦN KIỂM TRA THỜI TIẾT VÀ LỜI KHUYẾN
# -----------------------------------------------------------------------------
def get_weather(city_name: str, api_key: str) -> str:
    base_url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": api_key, "q": city_name}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        temperature = weather_data["current"]["temp_c"]
        weather_description = weather_data["current"]["condition"]["text"]
        humidity = weather_data["current"]["humidity"]
        wind_speed = weather_data["current"]["wind_kph"]
        upcoming = get_upcoming_appointments(limit=1)
        if any(keyword in weather_description.lower() for keyword in ["rain", "storm", "snow", "hail"]):
            advice = "It looks like bad weather; if you go out, remember to bring an umbrella and warm clothes."
        elif not upcoming:
            advice = "The weather is beautiful and you have no appointments today. How about going out for a walk or exercise?"
        else:
            advice = "The weather is pleasant, but you have appointments scheduled."
        return (f"Weather in {city_name}: {weather_description}, "
                f"Temperature: {temperature}°C, Humidity: {humidity}%, "
                f"Wind Speed: {wind_speed} km/h. {advice}")
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "Error: Invalid API Key."
        elif response.status_code == 400:
            return f"Error: City '{city_name}' not found."
        else:
            return f"Error fetching weather data: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"

def handle_check_weather(command: str, api_key: str) -> str:
    city_name = extract_location(command)
    if city_name:
        city_name = city_name.title()
        update_reward_score(1)
        return get_weather(city_name, api_key)
    else:
        return "Please specify a city name."

WEATHERAPI_API_KEY = "5e65619e9ff54500a5c62422250103"

# -----------------------------------------------------------------------------
# PHẦN NHẮC LẠI LỊCH HẸN
# -----------------------------------------------------------------------------
def get_upcoming_appointments(limit=5) -> list:
    service = authenticate_google_calendar()
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=limit, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

def check_appointment_reminders() -> str:
    events = get_upcoming_appointments()
    if events:
        reminders = "Upcoming appointments:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt = parser.parse(start)
            reminders += f"- {event['summary']} at {dt.strftime('%Y-%m-%d %I:%M %p')}\n"
        return reminders
    else:
        return "No upcoming appointments found."

# -----------------------------------------------------------------------------
# TÍNH NĂNG CÁ NHÂN HÓA: CHÈN TÊN NGƯỜI DÙNG & ĐIỂM THƯỞNG
# -----------------------------------------------------------------------------
def personalize_response(response: str) -> str:
    profile = get_user_profile()
    if profile and profile.get("username"):
        return f"Hello {profile['username']}, {response}"
    return response

def handle_set_username(command: str) -> str:
    m = re.search(r"(?:set my name as|my name is)\s+(.*)", command, re.IGNORECASE)
    if m:
        username = m.group(1).strip()
        update_user_profile(username=username)
        update_reward_score(10)
        return f"Your name has been set to {username}."
    else:
        update_reward_score(-5)
        return "Could not extract your name. Please try again."

def handle_set_location(command: str) -> str:
    m = re.search(r"(?:set my location as|my location is)\s+(.*)", command, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        update_user_profile(location=location)
        update_reward_score(5)
        return f"Your location has been set to {location}."
    else:
        update_reward_score(-5)
        return "Could not extract your location. Please try again."

def greet_user(uid, username=None, location=None) -> dict:
    """Trả về lời chào hoặc yêu cầu nhập thông tin nếu thiếu username hoặc location."""
    profile = get_user_profile(uid)  # ✅ Truy vấn user theo UID

    # Trường hợp 1: Nếu chưa có username
    if not profile or not profile.get("username"):
        if not username:
            return {"error": "missing_username", "message": "Vui lòng nhập tên của bạn."}
        update_user_profile(uid, username=username)  # ✅ Cập nhật username

    # Trường hợp 2: Nếu chưa có location
    profile = get_user_profile(uid)  # ✅ Lấy lại profile sau khi cập nhật username
    if not profile.get("location"):
        if not location:
            return {"error": "missing_location", "message": "Vui lòng nhập vị trí của bạn."}
        update_user_profile(uid, location=location)  # ✅ Cập nhật location

    # Nếu đủ thông tin, trả về lời chào kèm thời tiết
    profile = get_user_profile(uid)  # ✅ Lấy profile sau khi cập nhật thông tin
    weather_info = get_weather(profile["location"], WEATHERAPI_API_KEY)
    score = profile["score"]

    return {"message": f"Hello {profile['username']}! Your current reward score is {score}. {weather_info}"}



# -----------------------------------------------------------------------------
# PHẦN THỐNG KÊ & GỢI Ý CÁ NHÂN HÓA
# -----------------------------------------------------------------------------
def get_frequent_songs(limit=3):
    cursor.execute("SELECT song_title, play_count, genre FROM song_usage ORDER BY play_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def get_frequent_apps(limit=3):
    cursor.execute("SELECT app_name, usage_count FROM app_usage ORDER BY usage_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def print_user_statistics():
    profile = get_user_profile()
    if profile:
        print(f"User Profile: {profile}")
    else:
        print("No user profile found.")
    print("\nFrequently Played Songs:")
    songs = get_frequent_songs()
    if songs:
        for song in songs:
            print(f"  - Song: {song[0]}, Played: {song[1]} times, Genre: {song[2]}")
    else:
        print("  No song usage data available.")
    print("\nFrequently Used Applications:")
    apps = get_frequent_apps()
    if apps:
        for app in apps:
            print(f"  - App: {app[0]}, Used: {app[1]} times")
    else:
        print("  No app usage data available.")
    cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM interactions")
    total, first_time, last_time = cursor.fetchone()
    print(f"\nTotal interactions: {total}")
    print(f"From {first_time} to {last_time}")

def recommend_song():
    songs = get_frequent_songs(limit=1)
    if songs:
        top_song = songs[0]
        return f"Based on your listening habits, you seem to love '{top_song[0]}' in the {top_song[2]} genre."
    return "No song data available for recommendations."

def recommend_app():
    apps = get_frequent_apps(limit=1)
    if apps:
        top_app = apps[0]
        return f"You frequently use '{top_app[0]}'. Consider exploring its advanced features!"
    return "No application data available for recommendations."

def display_personalized_recommendations():
    print("\n--- USER STATISTICS ---")
    print_user_statistics()
    print("\n--- RECOMMENDATIONS ---")
    print(recommend_song())
    print(recommend_app())
    print("\n--- Upcoming Appointments ---")
    reminders = check_appointment_reminders()
    print(reminders)

# -----------------------------------------------------------------------------
# PHẦN XỬ LÝ TRI THỨC: FLAN-T5 với cơ chế thử kết quả thay thế trước feedback
# -----------------------------------------------------------------------------
def handle_knowledge_query_custom(query: str) -> str:
    topic_key = normalize_topic(query)
    learned = get_learned_responses(topic_key)
    if learned:
        raw_data = learned[0]
    else:
        refined_query = refine_query(query)
        raw_data = enhanced_aggregate_search_results(refined_query, num_results=5)
    
    answer = generate_flexible_response(raw_data)
    quality = compute_answer_quality(answer)
    automatic_accept_threshold = 0.75
    if quality >= automatic_accept_threshold:
        print("\nAI's answer:")
        print(answer)
        if not learned:
            add_learned_responses(topic_key, raw_data)
        update_reward_score(2)
        return answer
    else:
        print("\nInitial answer quality low, trying alternative search results...")
        alternative_raw_data = enhanced_aggregate_search_results(refine_query(query), num_results=10)
        alternative_answer = generate_flexible_response(alternative_raw_data)
        quality2 = compute_answer_quality(alternative_answer)
        if quality2 >= automatic_accept_threshold:
            print("\nAI's improved answer:")
            print(alternative_answer)
            if not learned:
                add_learned_responses(topic_key, alternative_raw_data)
            update_reward_score(1)
            return alternative_answer
        else:
            print("\nQuality still low after alternative search.")
            feedback = input("Please provide the correct information for this query: ").strip()
            if feedback:
                add_learned_responses(topic_key, feedback)
                new_answer = generate_flexible_response(feedback)
                update_reward_score(5)
                return f"Thank you for your feedback. Here is the updated answer:\n{new_answer}"
            else:
                update_reward_score(-5)
                return "No new information provided. Using initial answer:\n" + answer

def dynamic_respond(query: str) -> str:
    query_lower = query.lower()
    for category, data in ai_qa.items():
        for pattern in data["patterns"]:
            if re.search(pattern, query, re.IGNORECASE):
                return random.choice(data["responses"])
    if "how to" in query_lower or "what is" in query_lower:
        return handle_knowledge_query_custom(query)
    learned = get_learned_responses(query)
    if learned:
        basic_data = random.choice(learned)
        return generate_flexible_response(basic_data)
    user_input = input(f"I don't know about '{query}'. Can you teach me? ").strip()
    if user_input:
        add_learned_responses(query, user_input)
        return generate_flexible_response(user_input)
    else:
        return f"Sorry, I don't have any information about '{query}'."

def learn_new_knowledge(query: str) -> str:
    if "how to" in query.lower() or "what is" in query.lower():
        return handle_knowledge_query_custom(query)
    else:
        user_input = input(f"Can you teach me about '{query}'? ").strip()
        if user_input:
            add_learned_responses(query, user_input)
            return generate_flexible_response(user_input)
        else:
            return f"Thanks, I've learned about '{query}'."

# -----------------------------------------------------------------------------
# PHẦN KIỂM TRA THỜI TIẾT VÀ LỜI KHUYẾN
# -----------------------------------------------------------------------------
def get_weather(city_name: str, api_key: str) -> str:
    base_url = "http://api.weatherapi.com/v1/current.json"
    params = {"key": api_key, "q": city_name}
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        weather_data = response.json()
        temperature = weather_data["current"]["temp_c"]
        weather_description = weather_data["current"]["condition"]["text"]
        humidity = weather_data["current"]["humidity"]
        wind_speed = weather_data["current"]["wind_kph"]
        upcoming = get_upcoming_appointments(limit=1)
        if any(keyword in weather_description.lower() for keyword in ["rain", "storm", "snow", "hail"]):
            advice = "It looks like bad weather; if you go out, remember to bring an umbrella and warm clothes."
        elif not upcoming:
            advice = "The weather is beautiful and you have no appointments today. How about going out for a walk or exercise?"
        else:
            advice = "The weather is pleasant, but you have appointments scheduled."
        return (f"Weather in {city_name}: {weather_description}, "
                f"Temperature: {temperature}°C, Humidity: {humidity}%, "
                f"Wind Speed: {wind_speed} km/h. {advice}")
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "Error: Invalid API Key."
        elif response.status_code == 400:
            return f"Error: City '{city_name}' not found."
        else:
            return f"Error fetching weather data: {e}"
    except requests.exceptions.RequestException as e:
        return f"Error fetching weather data: {e}"

def handle_check_weather(command: str, api_key: str) -> str:
    city_name = extract_location(command)
    if city_name:
        city_name = city_name.title()
        update_reward_score(1)
        return get_weather(city_name, api_key)
    else:
        return "Please specify a city name."

WEATHERAPI_API_KEY = "5e65619e9ff54500a5c62422250103"

# -----------------------------------------------------------------------------
# PHẦN NHẮC LẠI LỊCH HẸN
# -----------------------------------------------------------------------------
def get_upcoming_appointments(limit=5) -> list:
    service = authenticate_google_calendar()
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=limit, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events

def check_appointment_reminders() -> str:
    events = get_upcoming_appointments()
    if events:
        reminders = "Upcoming appointments:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            dt = parser.parse(start)
            reminders += f"- {event['summary']} at {dt.strftime('%Y-%m-%d %I:%M %p')}\n"
        return reminders
    else:
        return "No upcoming appointments found."

# -----------------------------------------------------------------------------
# TÍNH NĂNG CÁ NHÂN HÓA: CHÈN TÊN NGƯỜI DÙNG & ĐIỂM THƯỞNG
# -----------------------------------------------------------------------------
def personalize_response(response: str) -> str:
    profile = get_user_profile()
    if profile and profile.get("username"):
        return f"Hello {profile['username']}, {response}"
    return response

def handle_set_username(command: str) -> str:
    m = re.search(r"(?:set my name as|my name is)\s+(.*)", command, re.IGNORECASE)
    if m:
        username = m.group(1).strip()
        update_user_profile(username=username)
        update_reward_score(10)
        return f"Your name has been set to {username}."
    else:
        update_reward_score(-5)
        return "Could not extract your name. Please try again."

def handle_set_location(command: str) -> str:
    m = re.search(r"(?:set my location as|my location is)\s+(.*)", command, re.IGNORECASE)
    if m:
        location = m.group(1).strip()
        update_user_profile(location=location)
        update_reward_score(5)
        return f"Your location has been set to {location}."
    else:
        update_reward_score(-5)
        return "Could not extract your location. Please try again."

def greet_user(uid, username=None, location=None) -> dict:
    """Trả về lời chào hoặc yêu cầu nhập thông tin nếu thiếu username hoặc location."""
    profile = get_user_profile(uid)  # ✅ Truy vấn user theo UID

    # Trường hợp 1: Nếu chưa có username
    if not profile or not profile.get("username"):
        if not username:
            return {"error": "missing_username", "message": "Vui lòng nhập tên của bạn."}
        update_user_profile(uid, username=username)  # ✅ Cập nhật username

    # Trường hợp 2: Nếu chưa có location
    profile = get_user_profile(uid)  # ✅ Lấy lại profile sau khi cập nhật username
    if not profile.get("location"):
        if not location:
            return {"error": "missing_location", "message": "Vui lòng nhập vị trí của bạn."}
        update_user_profile(uid, location=location)  # ✅ Cập nhật location

    # Nếu đủ thông tin, trả về lời chào kèm thời tiết
    profile = get_user_profile(uid)  # ✅ Lấy profile sau khi cập nhật thông tin
    weather_info = get_weather(profile["location"], WEATHERAPI_API_KEY)
    score = profile["score"]

    return {"message": f"Hello {profile['username']}! Your current reward score is {score}. {weather_info}"}



# -----------------------------------------------------------------------------
# PHẦN THỐNG KÊ & GỢI Ý CÁ NHÂN HÓA
# -----------------------------------------------------------------------------
def get_frequent_songs(limit=3):
    cursor.execute("SELECT song_title, play_count, genre FROM song_usage ORDER BY play_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def get_frequent_apps(limit=3):
    cursor.execute("SELECT app_name, usage_count FROM app_usage ORDER BY usage_count DESC LIMIT ?", (limit,))
    return cursor.fetchall()

def print_user_statistics():
    profile = get_user_profile()
    if profile:
        print(f"User Profile: {profile}")
    else:
        print("No user profile found.")
    print("\nFrequently Played Songs:")
    songs = get_frequent_songs()
    if songs:
        for song in songs:
            print(f"  - Song: {song[0]}, Played: {song[1]} times, Genre: {song[2]}")
    else:
        print("  No song usage data available.")
    print("\nFrequently Used Applications:")
    apps = get_frequent_apps()
    if apps:
        for app in apps:
            print(f"  - App: {app[0]}, Used: {app[1]} times")
    else:
        print("  No app usage data available.")
    cursor.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM interactions")
    total, first_time, last_time = cursor.fetchone()
    print(f"\nTotal interactions: {total}")
    print(f"From {first_time} to {last_time}")

def recommend_song():
    songs = get_frequent_songs(limit=1)
    if songs:
        top_song = songs[0]
        return f"Based on your listening habits, you seem to love '{top_song[0]}' in the {top_song[2]} genre."
    return "No song data available for recommendations."

def recommend_app():
    apps = get_frequent_apps(limit=1)
    if apps:
        top_app = apps[0]
        return f"You frequently use '{top_app[0]}'. Consider exploring its advanced features!"
    return "No application data available for recommendations."

def display_personalized_recommendations():
    print("\n--- USER STATISTICS ---")
    print_user_statistics()
    print("\n--- RECOMMENDATIONS ---")
    print(recommend_song())
    print(recommend_app())
    print("\n--- Upcoming Appointments ---")
    reminders = check_appointment_reminders()
    print(reminders)

# -----------------------------------------------------------------------------
# VÒNG LẶP CHÍNH
# -----------------------------------------------------------------------------
if __name__ == "__main__":   
    print(greet_user())

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # Nếu người dùng gửi phản hồi tiêu cực
        if user_input.lower().startswith("feedback:"):
            feedback_text = user_input[len("feedback:"):].strip()
            feedback_response = process_negative_feedback(feedback_text)
            print("\n" + feedback_response)
            continue

        if re.search(r"(set my name as|my name is)", user_input, re.IGNORECASE):
            result = handle_set_username(user_input)
        elif re.search(r"(set my location as|my location is)", user_input, re.IGNORECASE):
            result = handle_set_location(user_input)
        elif re.search(r"(remind me about appointments|what are my upcoming appointments)", user_input, re.IGNORECASE):
            result = check_appointment_reminders()
        elif any(cmd in user_input.lower() for cmd in ["shut down", "turn off", "restart", "reboot", "brightness", "mute", "unmute"]):
            result = handle_system_command(user_input)
        elif "open" in user_input.lower():
            result = handle_open_application(user_input)
        elif "play" in user_input.lower():
            result = handle_play_music(user_input)
        elif "set an appointment" in user_input.lower() or "schedule a meeting" in user_input.lower():
            result = handle_set_appointment(user_input)
        elif "weather" in user_input.lower():
            result = handle_check_weather(user_input, WEATHERAPI_API_KEY)
        elif any(keyword in user_input.lower() for keyword in [
                "who are you", "what are you", "tell me about yourself", "your name",
                "who created you", "who made you"]):
            result = handle_ai_question(user_input)
        else:
            if "how " in user_input.lower() or "what " in user_input.lower() or "when" in user_input.lower() or "who" in user_input.lower() or "search" in user_input.lower() or "?" in user_input.lower():
                result = handle_knowledge_query_custom(user_input)
            else:
                result = dynamic_respond(user_input)
        if result:
            personalized_result = personalize_response(result)
            print("\n" + personalized_result)
            log_interaction(user_input, personalized_result)
