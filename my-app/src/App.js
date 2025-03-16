import React, { useState, useEffect, useCallback } from "react";
import MovingCircle from "./components/MovingCircle";
import ChatInput from "./components/ChatInput";
import ChatBubble from "./components/ChatBubble";
import { askQuestion, greetUser, sendFeedback, teachAI } from "./services/apiService";
import { useAuthState } from 'react-firebase-hooks/auth';
import { auth } from './config/firebase';
import { updateUserLastActive, saveChatHistory, getChatHistory, deleteChatHistory } from './services/userService';
import Login from './components/Login';


function App() {
  const [user] = useAuthState(auth);
  const [messages, setMessages] = useState([]);
  const [greeting, setGreeting] = useState("");
  const [currentResponse, setCurrentResponse] = useState(""); // Phản hồi tạm thời cho MovingCircle
  const [isLoading, setIsLoading] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false); // Trạng thái mở/đóng miệng
  const [chatHistory, setChatHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [teachingQuery, setTeachingQuery] = useState(null);
  const [lastQuery, setLastQuery] = useState(null);
  const [mode, setMode] = useState("normal");
  const [currentChatId, setCurrentChatId] = useState(null); // Theo dõi cuộc trò chuyện hiện tại
  const [showGuide, setShowGuide] = useState(false); // Trạng thái mới để hiển thị bảng hướng dẫn

  const fetchChatHistory = useCallback(async () => {
    const history = await getChatHistory(user.uid);
    setChatHistory(history);
  }, [user]);

  useEffect(() => {
    if (user) {
      updateUserLastActive(user.uid);
      fetchGreeting();
      fetchChatHistory();
    } else {
      // Khi không có user (đăng xuất), làm sạch tin nhắn
      setMessages([]);
      setCurrentChatId(null);
      setGreeting("");
    }
  }, [user, fetchChatHistory]);

  const handleLogout = async () => {
    try {
      await fetch('http://127.0.0.1:5000/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${await auth.currentUser.getIdToken()}`,
          'Content-Type': 'application/json',
        },
      });
      auth.signOut();
    } catch (error) {
      console.error("Lỗi khi đăng xuất:", error);
    }
  };

  const fetchGreeting = async () => {
    setIsLoading(true);
    try {
      const greetingResponse = await greetUser();
      console.log("🔥 Greeting Response:", greetingResponse); // Thêm log
      setGreeting(greetingResponse.response);
    } catch (error) {
      console.error("Lỗi khi lấy lời chào:", error);
      setGreeting("Lỗi khi lấy lời chào, vui lòng thử lại.");
    } finally {
      setIsLoading(false);
    }
  };;

  const handleNewChat = async () => {
    if (messages.length > 0 && currentChatId) {
      await saveChatHistory(user.uid, messages, currentChatId); // Cập nhật nếu đang ở chat cũ
    } else if (messages.length > 0) {
      const newChatId = await saveChatHistory(user.uid, messages); // Tạo mới nếu chưa có
      setCurrentChatId(newChatId);
    }
    setMessages([]);
    setGreeting("");
    fetchGreeting();
    setMode("normal");
    setCurrentChatId(null); // Reset chatId khi tạo chat mới
    fetchChatHistory();
  };

  const handleSend = async (question) => {
    if (!question.trim()) return;
    setIsLoading(true);
    const userMessage = { text: question, isAnswer: false };
    setMessages(prev => [...prev, userMessage]);
    setLastQuery(question);

    try {
      let response;
      if (mode === "teach" && teachingQuery) {
        response = await teachAI(teachingQuery, question);
        setTeachingQuery(null);
        setMode("normal");
      } else if (mode === "feedback" && lastQuery) {
        response = await sendFeedback(lastQuery, question);
        setMode("normal");
      } else {
        response = await askQuestion(question, !!teachingQuery, teachingQuery ? question : '');
        if (response.status === "teach_me") {
          setTeachingQuery(response.query);
          setMode("teach");
        } else {
          setTeachingQuery(null);
        }
      }

      // Hiển thị phản hồi trong MovingCircle và kích hoạt miệng
      setCurrentResponse(response.response);
      setIsSpeaking(true);

      // Sau 5 giây, thêm vào messages và tắt hiệu ứng
      setTimeout(() => {
        const aiMessage = { text: response.response, isAnswer: true };
        const updatedMessages = [...messages, userMessage, aiMessage];
        setMessages(updatedMessages);
        setCurrentResponse("");
        setIsSpeaking(false);

        // Lưu lịch sử chat ngay sau khi cập nhật messages
        saveChatHistory(user.uid, updatedMessages, currentChatId).then(chatId => {
          if (!currentChatId) {
            setCurrentChatId(chatId);
          }
          fetchChatHistory();
        });
      }, 5000);

      
    } catch (error) {
      // Xử lý lỗi: hiển thị trong MovingCircle trước, sau đó thêm vào messages
      setCurrentResponse("Lỗi kết nối server, vui lòng thử lại.");
      setIsSpeaking(true);
      setTimeout(() => {
        const errorMessage = { text: "Lỗi kết nối server, vui lòng thử lại.", isAnswer: true };
        const updatedMessages = [...messages, userMessage, errorMessage];
        setMessages(updatedMessages);
        setCurrentResponse("");
        setIsSpeaking(false);

        // Lưu lịch sử chat ngay cả khi có lỗi
        saveChatHistory(user.uid, updatedMessages, currentChatId).then(chatId => {
          if (!currentChatId) {
            setCurrentChatId(chatId);
          }
          fetchChatHistory();
        });
      }, 5000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedbackMode = () => {
    console.log("Feedback mode activated, lastQuery:", lastQuery, "Current mode:", mode);
    if (mode === "feedback") {
      setMode("normal");
      console.log("Mode reset to normal");
    } else if (lastQuery) {
      setMode("feedback");
      console.log("Mode set to feedback");
    } else {
      alert("Vui lòng gửi một câu hỏi trước khi cung cấp feedback!");
    }
  };

  const handleShowHistory = () => {
    setShowHistory(true);
  };

  const handleSelectChat = (chat) => {
    setMessages(chat.messages);
    setGreeting("");
    setShowHistory(false);
    setMode("normal");
    setCurrentChatId(chat.id); // Đặt chatId của cuộc trò chuyện được chọn
  };

  const handleDeleteChat = async (chatId) => {
    const confirmDelete = window.confirm("Bạn có chắc muốn xóa cuộc hội thoại này không?");
    if (confirmDelete) {
      try {
        await deleteChatHistory(user.uid, chatId);
        setChatHistory(prev => prev.filter(chat => chat.id !== chatId));
      } catch (error) {
        console.error("Lỗi khi xóa:", error);
        alert("Không thể xóa cuộc hội thoại. Vui lòng thử lại.");
      }
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
      {/* Nút điều khiển */}
      <div style={{
        position: 'absolute',
        top: 10,
        right: 10,
        zIndex: 1000,
        display: 'flex',
        gap: '10px'
      }}>
        {/* Nút Hướng dẫn */}
        <div style={{ position: 'relative' }}>
          <button 
            onMouseEnter={() => setShowGuide(true)} // Hiển thị bảng khi rê chuột vào
            onMouseLeave={() => setShowGuide(false)} // Ẩn bảng khi rời chuột
            onClick={() => setShowGuide(!showGuide)} // Hiển thị/ẩn bảng khi nhấn
            style={{
              padding: '8px 16px',
              borderRadius: '5px',
              border: '1px solid #ccc',
              backgroundColor: '#fff',
              cursor: 'pointer'
            }}
          >
            Hướng dẫn
          </button>
          {showGuide && (
            <div style={{
              position: 'absolute',
              top: '40px',
              right: 0,
              backgroundColor: '#333',
              color: '#fff',
              padding: '15px',
              borderRadius: '8px',
              boxShadow: '0 4px 8px rgba(0,0,0,0.2)',
              zIndex: 1001,
              width: '350px',
              fontSize: '14px',
              fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif"
            }}>
              <h3 style={{ margin: '0 0 10px', fontSize: '16px', fontWeight: 'bold' }}>
                HƯỚNG DẪN SỬ DỤNG
              </h3>
              <p style={{ margin: '5px 0' }}>
                <strong>Nếu bạn muốn thực hiện lệnh hệ thống:</strong> hãy nhập từ khóa: "shut down", "turn off", "restart", "reboot", "decrease brightness", "increase brightness", "mute", "unmute"
              </p>
              <p style={{ margin: '5px 0' }}>
                <strong>Nếu bạn muốn mở ứng dụng:</strong> hãy nhập từ khóa: "open"
              </p>
              <p style={{ margin: '5px 0' }}>
                <strong>Nếu bạn muốn mở nhạc:</strong> hãy nhập từ khóa: "play music"
              </p>
              <p style={{ margin: '5px 0' }}>
                <strong>Nếu bạn muốn kiểm tra thời tiết:</strong> hãy nhập từ khóa: "weather in"
              </p>
              <p style={{ margin: '5px 0' }}>
                <strong>Nếu bạn muốn đặt lịch hẹn:</strong> hãy nhập từ khóa: "set an appointment", "schedule a meeting"
              </p>
              <p style={{ margin: '5px 0' }}>
                <strong>Nếu bạn muốn kiểm tra hẹn:</strong> hãy nhập từ khóa: "remind me about appointments", "what are my upcoming appointments"
              </p>
            </div>
          )}
        </div>
        <button 
          onClick={handleShowHistory}
          style={{
            padding: '8px 16px',
            borderRadius: '5px',
            border: '1px solid #ccc',
            backgroundColor: '#fff',
            cursor: 'pointer'
          }}
        >
          History
        </button>
        <button 
          onClick={handleNewChat}
          style={{
            padding: '8px 16px',
            borderRadius: '5px',
            border: '1px solid #ccc',
            backgroundColor: '#fff',
            cursor: 'pointer'
          }}
        >
          New Chat
        </button>
        <button 
          onClick={handleFeedbackMode}
          style={{
            padding: '8px 16px',
            borderRadius: '5px',
            border: '1px solid #ccc',
            backgroundColor: mode === "feedback" ? '#28a745' : '#fff',
            color: mode === "feedback" ? '#fff' : '#000',
            cursor: 'pointer'
          }}
        >
          Give Feedback
        </button>
        <button 
          onClick={handleLogout}
          style={{
            padding: '8px 16px',
            borderRadius: '5px',
            border: '1px solid #ccc',
            backgroundColor: '#fff',
            cursor: 'pointer'
          }}
        >
          Đăng xuất
        </button>
      </div>

      {/* Sidebar hiển thị lịch sử chat */}
      {showHistory && (
        <div style={{ position: 'absolute', top: 0, left: 0, width: '250px', height: '100%', backgroundColor: '#f5f5f5', padding: '20px', overflowY: 'auto' }}>
          <h3 style={{ marginBottom: '20px' }}>Lịch sử chat</h3>
          {chatHistory.length > 0 ? (
            chatHistory.map((chat) => (
              <div key={chat.id} style={{ padding: '10px', marginBottom: '10px', backgroundColor: '#fff', borderRadius: '5px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div onClick={() => handleSelectChat(chat)} style={{ cursor: 'pointer', flexGrow: 1 }}>
                    <p style={{ fontWeight: 'bold', marginBottom: '5px' }}>{chat.title}</p>
                    <p style={{ fontSize: '12px', color: '#666' }}>
                      {chat.createdAt?.toDate().toLocaleString() || 'Không có ngày tạo'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDeleteChat(chat.id)}
                    style={{ padding: '4px 8px', color: 'red', border: 'none', background: 'none', cursor: 'pointer' }}
                  >
                    Xóa
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p>Không có lịch sử chat.</p>
          )}
          <button 
            onClick={() => setShowHistory(false)}
            style={{
              marginTop: '20px',
              padding: '8px 16px',
              borderRadius: '5px',
              border: '1px solid #ccc',
              backgroundColor: '#fff',
              cursor: 'pointer'
            }}
          >
            Đóng
          </button>
        </div>
      )}

      <MovingCircle 
        response={currentResponse} 
        isSpeaking={isSpeaking}
        isLoading={isLoading}  
      />
      <div style={{
        marginBottom: "80px",
        overflowY: "auto",
        height: "calc(100% - 100px)",
        padding: "10px",
        fontFamily: "'Roboto', 'Noto Sans', Arial, sans-serif"
      }}>
        {greeting && <ChatBubble text={greeting} isAnswer={true} />}
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
          placeholder={
            mode === "feedback" ? "Nhập phản hồi của bạn..." : 
            teachingQuery ? "" : "Ask me anything..."
          }
          mode={mode}
        />
      </div>
    </div>
  );
}

export default App;