import React, { useState, useEffect } from "react";
import MovingCircle from "./components/MovingCircle";
import ChatInput from "./components/ChatInput";
import ChatBubble from "./components/ChatBubble";
import { askQuestion, greetUser } from "./services/apiService";
import { useAuthState } from 'react-firebase-hooks/auth';
import { auth } from './config/firebase';
import { updateUserLastActive } from './services/userService';
import Login from './components/Login';

function App() {
  const [user] = useAuthState(auth);
  const [messages, setMessages] = useState([]);
  const [currentResponse, setCurrentResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  

  useEffect(() => {
    if (user) {
      updateUserLastActive(user.uid);
      fetchGreeting();
    }
  }, [user]);

  const fetchGreeting = async () => {
    setIsLoading(true);
    try {
      const greeting = await greetUser();
      console.log("🔥 Debug: Greeting response =", greeting); // Kiểm tra phản hồi từ API
      setMessages([{ text: greeting.response, isAnswer: true }]);
    } catch (error) {
      console.error("Lỗi khi lấy lời chào:", error);
      setMessages([{ text: "Lỗi khi lấy lời chào, vui lòng thử lại.", isAnswer: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (question) => {
    if (!question.trim()) return;
    setIsLoading(true);
    setMessages(prev => [...prev, { text: question, isAnswer: false }]);

    try {
      const response = await askQuestion(question);
      const answer = response?.answer || "Không nhận được phản hồi từ server.";
      setCurrentResponse(answer);
      setIsSpeaking(true);

      setTimeout(() => {
        setIsSpeaking(false);
        setCurrentResponse("");
        setMessages(prev => [...prev, { text: answer, isAnswer: true }]);
      }, 5000);

    } catch (error) {
      console.error("Lỗi khi gửi câu hỏi:", error);
      setMessages(prev => [...prev, { text: "Lỗi kết nối, vui lòng thử lại.", isAnswer: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  if (!user) {
    return <Login />;
  }

  return (
    <div style={{ 
      height: "100vh", 
      position: "relative", 
      padding: "20px",
      fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif",
      WebkitFontSmoothing: 'antialiased',
      MozOsxFontSmoothing: 'grayscale'
    }}>
      <div style={{
        position: 'absolute',
        top: 10,
        right: 10,
        zIndex: 1000
      }}>
        <button onClick={() => auth.signOut()}>Đăng xuất</button>
      </div>
      {isLoading && <div className="loading-indicator">Đang tải...</div>}
      <MovingCircle 
      response={currentResponse} 
      isSpeaking={isSpeaking}
      isLoading={isLoading}  />
      <div style={{
        marginBottom: "80px",
        overflowY: "auto",
        height: "calc(100% - 100px)",
        padding: "10px",
        fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif"
      }}>
        {messages.map((msg, idx) => (
          <ChatBubble 
            key={idx} 
            text={msg.text} 
            isAnswer={msg.isAnswer}
            isLoading={isLoading && idx === messages.length - 1} 
          />
        ))}
      </div>
      <div style={{
        position: "fixed",
        bottom: 20,
        left: "50%",
        transform: "translateX(-50%)",
        width: "90%",
        maxWidth: "800px",
        backgroundColor: "#fff",
        padding: "10px",
        borderRadius: "10px",
        boxShadow: "0 -2px 10px rgba(0,0,0,0.1)",
        zIndex: 1000,
        fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif"
      }}>
        <ChatInput 
          onSend={handleSend} 
          disabled={isLoading} 
          key="chat-input"
        />
      </div>
    </div>
  );
}

export default App;
