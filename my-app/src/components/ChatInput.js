import React, { useState } from "react";

const ChatInput = ({ onSend }) => {
  
  
  const [question, setQuestion] = useState("");
  

  const handleSend = () => {
    if (question.trim() === "") return;
    onSend(question);
    setQuestion("");
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  return (
    <div style={{ display: "flex", gap: "10px" }}>
      <input
        type="text"
        placeholder="Nhập câu hỏi..."
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyPress={handleKeyPress}
        style={{
          flex: 1,
          padding: "10px",
          borderRadius: "5px",
          border: "1px solid #ccc",
        }}
      />
      <button onClick={handleSend} style={{ padding: "10px 15px" }}>
        Gửi
      </button>
    </div>
  );
  
};


export default ChatInput;
