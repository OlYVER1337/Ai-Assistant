import React, { useState } from "react";

const LoginButton = () => {
  const [loggedIn, setLoggedIn] = useState(false);
  const [avatar, setAvatar] = useState("");

  const handleLogin = () => {
    const userAvatar = prompt("Nhập URL avatar của bạn:");
    if (userAvatar) {
      setAvatar(userAvatar);
      setLoggedIn(true);
    }
  };

  return (
    <div style={{ position: "absolute", top: 10, right: 10 }}>
      {loggedIn ? (
        <img
          src={avatar}
          alt="Avatar"
          style={{
            width: 50,
            height: 50,
            borderRadius: "50%",
            border: "2px solid #000",
          }}
        />
      ) : (
        <button
          onClick={handleLogin}
          style={{
            padding: "10px 20px",
            borderRadius: "20px",
            backgroundColor: "#4CAF50",
            color: "white",
            border: "none",
            cursor: "pointer",
          }}
        >
          Đăng nhập
        </button>
      )}
    </div>
  );
};

export default LoginButton;
