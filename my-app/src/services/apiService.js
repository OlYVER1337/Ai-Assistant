import { auth } from '../config/firebase';
import axios from 'axios';
import axiosRetry from 'axios-retry';

axiosRetry(axios, { retries: 3, retryDelay: axiosRetry.exponentialDelay });

// Cập nhật apiService.js
typeof window !== "undefined" && console.log("🔥 API Service Loaded");
const API_URL = "http://127.0.0.1:5000";

async function getAuthToken() {
  try {
    const token = await auth.currentUser?.getIdToken(true);
    return token;
  } catch (error) {
    console.error("Lỗi lấy token Firebase:", error);
    return null;
  }
}

async function apiRequest(endpoint, method, body) {
  const token = await getAuthToken();
  if (!token) return { error: "Không thể xác thực người dùng!" };

  try {
    const response = await axios({
      url: `${API_URL}${endpoint}`,
      method,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      data: body
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error(`Lỗi server: ${error.response.status}`, error.response.data);
      return { error: error.response.data.error || `Lỗi server: ${error.response.status}` };
    } else if (error.request) {
      console.error("Không thể kết nối đến server!", error.request);
      return { error: "Không thể kết nối đến server!" };
    } else {
      console.error("Lỗi không xác định:", error.message);
      return { error: "Lỗi không xác định!" };
    }
  }
}

export async function askQuestion(question) {
  return apiRequest('/ask', 'POST', { question });
}

export async function executeCommand(command) {
  return apiRequest('/command', 'POST', { command });
}

export async function openApp(app_name) {
  return apiRequest('/open_app', 'POST', { app_name });
}

export async function playMusic(song) {
  return apiRequest('/play_music', 'POST', { song });
}

export async function checkWeather(location) {
  return apiRequest('/weather', 'POST', { location });
}

export async function setAppointment(appointment) {
  return apiRequest('/set_appointment', 'POST', { appointment });
}

export async function getReminders() {
  return apiRequest('/reminders', 'GET', null);
}

export async function greetUser() {
  let response = await apiRequest('/greet', 'POST', {});

  // Trường hợp 1: Nếu thiếu tên, yêu cầu nhập
  if (response.error === "missing_username") {
    const username = prompt("Nhập tên của bạn:");
    if (!username) return { error: "Bạn cần nhập tên để tiếp tục!" };

    // Gửi lại API với username mới
    response = await apiRequest('/greet', 'POST', { username });
  }

  // Trường hợp 2: Nếu thiếu location, yêu cầu nhập
  if (response.error === "missing_location") {
    const location = prompt("Nhập vị trí của bạn:");
    if (!location) return { error: "Bạn cần nhập vị trí để tiếp tục!" };

    // Gửi lại API với location mới
    response = await apiRequest('/greet', 'POST', { username: response.username, location });
  }

  return response;
}

