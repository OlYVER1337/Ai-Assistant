import React, { useState, useEffect } from "react";
import { useAuthState } from "react-firebase-hooks/auth";
import { auth, db } from "../config/firebase";
import { collection, query, orderBy, onSnapshot } from "firebase/firestore";
import { useNavigate } from "react-router-dom";
import { deleteChatHistory } from "../services/userService";
import Login from "./Login";
function History() {
  const [user] = useAuthState(auth);
  const [chatHistory, setChatHistory] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      fetchChatHistory();
    }
  }, [user]);


const fetchChatHistory = () => {
  const chatRef = collection(db, "users", user.uid, "chatHistory");
  const q = query(chatRef, orderBy("updatedAt", "desc")); // Sắp xếp theo updatedAt
  const unsubscribe = onSnapshot(q, (querySnapshot) => {
    const history = querySnapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }));
    setChatHistory(history);
  }, (error) => {
    console.error("Lỗi khi lắng nghe lịch sử chat:", error);
  });
  return unsubscribe; // Để hủy lắng nghe khi component unmount
};

useEffect(() => {
  if (user) {
    const unsubscribe = fetchChatHistory();
    return () => unsubscribe(); // Hủy lắng nghe khi component unmount
  }
}, [user]);

  const handleChatClick = (chat) => {
    // Chuyển hướng đến trang chi tiết chat (nếu muốn hiển thị toàn bộ nội dung chat)
    navigate(`/chat/${chat.id}`, { state: { messages: chat.messages } });
  };

  if (!user) {
    return <Login />;
  }

  return (
    <div style={{ height: "100vh", padding: "20px", fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif" }}>
      <div style={{ position: "absolute", top: 10, right: 10, zIndex: 1000, display: "flex", gap: "10px" }}>
        <button onClick={() => navigate("/")}>Back to Chat</button>
        <button onClick={() => auth.signOut()}>Đăng xuất</button>
      </div>
      <h2>Lịch sử trò chuyện</h2>
      <div style={{ overflowY: "auto", height: "calc(100% - 100px)", padding: "10px" }}>
        {chatHistory.length === 0 ? (
          <p>Chưa có lịch sử trò chuyện.</p>
        ) : (
          chatHistory.map((chat) => (
            <div
              key={chat.id}
              style={{ padding: "10px", borderBottom: "1px solid #ccc", backgroundColor: "#f9f9f9", marginBottom: "5px", borderRadius: "5px" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div onClick={() => handleChatClick(chat)} style={{ cursor: "pointer", flexGrow: 1 }}>
                  <h3>{chat.title}</h3>
                  <p>
                    {chat.createdAt?.seconds ? new Date(chat.createdAt.seconds * 1000).toLocaleString() : "Không có ngày tạo"}
                  </p>
                </div>
                <button
                  onClick={() => handleDeleteChat(chat.id)}
                  style={{ padding: "4px 8px", color: "red", border: "none", background: "none", cursor: "pointer" }}
                >
                  Xóa
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default History;