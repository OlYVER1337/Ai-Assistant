import React from "react";

const ChatBubble = ({ text, isAnswer }) => {
  // Kiểm tra nếu text là object
  const message = typeof text === 'object' ? text.answer : text;
  
  const defaultStyle = {
    maxWidth: "60%",
    margin: isAnswer ? "10px auto 10px 0" : "10px 0 10px auto",
    padding: "10px",
    borderRadius: "10px",
    backgroundColor: isAnswer ? "#E0E0E0" : "#FFD700",
    color: "#000",
    textAlign: "left",
    fontFamily: "Arial, sans-serif",
    fontSize: "14px",
    lineHeight: "1.5",
  };

  return (
    <div style={defaultStyle}>
      {message}
    </div>
  );
};


export default ChatBubble;
