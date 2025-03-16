import React, { useState } from "react";

const ChatInput = ({ onSend, disabled, placeholder, mode }) => {
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

  // Xác định text nổi dựa trên mode
  const floatingText = mode === "teach" ? "Teach me about this:" : mode === "feedback" ? "Feedback:" : null;

  return (
    <div style={{ display: "flex", gap: "10px" }}>
      {floatingText && (
        <span
          style={{
            position: "absolute",
            top: "-20px",
            left: "10px",
            fontSize: "14px",
            fontWeight: "bold",
            color: "#333",
            backgroundColor: "#fff",
            padding: "0 5px",
          }}
        >
          {floatingText}
        </span>
      )}
      <input
        type="text"
        placeholder={placeholder || "Nhập câu hỏi..."}
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