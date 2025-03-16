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
      return { error: error.response.data.error || `Lỗi server: ${error.response.status}` };
    }
    return { error: "Không thể kết nối đến server!" };
  }
}

export async function askQuestion(question, isTeaching = false, teachResponse = '') {
  try {
    console.log("🔥 Gửi câu hỏi:", question, "isTeaching:", isTeaching);
    const response = await apiRequest('/ask', 'POST', { 
      question, 
      is_teaching: isTeaching, 
      teach_response: teachResponse 
    });
    console.log("🔥 API Response =", response);

    if (!response || !response.answer) {
      return { response: "Không nhận được phản hồi hợp lệ từ server.", status: "error" };
    }
    return { response: response.answer, status: response.status || "success", query: response.query };
  } catch (error) {
    console.error("❌ API Error:", error);
    return { response: "Không thể kết nối đến server. Hãy thử lại sau.", status: "error" };
  }
}

export async function greetUser() {
  const response = await apiRequest('/greet', 'POST', {});
  if (response.error === "missing_username") {
    const username = prompt("Nhập tên của bạn:");
    if (!username) return { response: "Bạn cần nhập tên để tiếp tục!", status: "error" };
    return await apiRequest('/greet', 'POST', { username });
  }
  if (response.error === "missing_location") {
    const location = prompt("Nhập vị trí của bạn:");
    if (!location) return { response: "Bạn cần nhập vị trí để tiếp tục!", status: "error" };
    return await apiRequest('/greet', 'POST', { username: response.username, location });
  }
  return response;
}

export async function logout() {
  const response = await apiRequest('/logout', 'POST', {});
  return response;
}

export async function teachAI(originalQuery, teachResponse) {
  try {
    console.log("🔥 Gửi dạy AI:", originalQuery, teachResponse);
    const response = await apiRequest('/teach', 'POST', { 
      original_query: originalQuery, 
      teach_response: teachResponse 
    });
    console.log("🔥 Teach API Response =", response);
    if (!response || response.error) {
      return { response: response.error || "Không thể dạy AI.", status: "error" };
    }
    return { response: response.answer, status: "success" };
  } catch (error) {
    console.error("❌ Teach API Error:", error);
    return { response: "Không thể kết nối đến server. Hãy thử lại sau.", status: "error" };
  }
}

export async function sendFeedback(originalQuery, feedback) {
  try {
    console.log("🔥 Gửi feedback:", originalQuery, feedback);
    const response = await apiRequest('/feedback', 'POST', { 
      original_query: originalQuery, 
      feedback: feedback 
    });
    console.log("🔥 Feedback API Response =", response);
    if (!response || response.error) {
      return { response: response.error || "Không thể gửi feedback.", status: "error" };
    }
    return { response: response.answer, status: "success" };
  } catch (error) {
    console.error("❌ Feedback API Error:", error);
    return { response: "Không thể kết nối đến server. Hãy thử lại sau.", status: "error" };
  }
}

