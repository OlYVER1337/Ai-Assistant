import React, { useState } from "react";

const ChatInput = ({ onSend, disabled }) => {
  const [question, setQuestion] = useState("");

  const handleSend = () => {
    if (question.trim() === "" || disabled) return;
    onSend(question);
    setQuestion("");
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !disabled) {
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
        disabled={disabled}
        style={{
          flex: 1,
          padding: "10px",
          borderRadius: "5px", 
          border: "1px solid #ccc",
          backgroundColor: disabled ? "#f3f3f3" : "#fff"
        }}
      />
      <button 
        onClick={handleSend} 
        disabled={disabled} 
        style={{ padding: "10px 15px" }}
      >
        {disabled ? "Đang gửi..." : "Gửi"}
      </button>
    </div>
  );
};

export default ChatInput;