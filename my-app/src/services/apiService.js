const API_URL = "http://localhost:5000";

export async function askQuestion(question) {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question })
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || `Lỗi server: ${response.status}`);
  }

  return data.answer;  // Trả về trực tiếp answer
}

