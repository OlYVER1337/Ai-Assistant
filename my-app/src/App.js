import React, { useState } from "react";
import MovingCircle from "./components/MovingCircle";
import ChatInput from "./components/ChatInput";
import ChatBubble from "./components/ChatBubble";
import { askQuestion } from "./services/apiService";

function App() {
  const [messages, setMessages] = useState([]);
  const [currentResponse, setCurrentResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showMessage, setShowMessage] = useState(false);

  const handleSend = async (question) => {
    try {
      if (!question.trim()) return;
      
      setIsLoading(true);
      setMessages(prev => [...prev, { text: question, isAnswer: false }]);

      const response = await askQuestion(question);
      const answer = typeof response === 'object' ? response.answer : response;
      
      setCurrentResponse(answer);
      setIsSpeaking(true);

      // Đợi 5 giây trước khi hiển thị tin nhắn
      setTimeout(() => {
        setIsSpeaking(false);
        setCurrentResponse("");
        setShowMessage(true);
        setMessages(prev => [...prev, { text: answer, isAnswer: true }]);
      }, 5000);

    } catch (error) {
      setMessages(prev => [...prev, { text: "Vui lòng thử lại sau", isAnswer: true }]);
    } finally {
      setIsLoading(false);
    }
  };

  

  return (
    <div style={{ 
      height: "100vh", 
      position: "relative", 
      padding: "20px",
      fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif",
      WebkitFontSmoothing: 'antialiased',
      MozOsxFontSmoothing: 'grayscale'
    }}>
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
