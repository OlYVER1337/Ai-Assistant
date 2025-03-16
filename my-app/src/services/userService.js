import { collection, getDocs, query, orderBy, setDoc, addDoc, doc, deleteDoc, updateDoc } from "firebase/firestore";
import { db } from "../config/firebase";
import { serverTimestamp } from "firebase/firestore";

// Cập nhật thời gian hoạt động cuối của người dùng
export const updateUserLastActive = async (uid) => {
  if (!uid) {
    console.error("updateUserLastActive: UID không hợp lệ!");
    return;
  }

  try {
    await setDoc(
      doc(db, "users", uid),
      { lastActive: serverTimestamp() },
      { merge: true }
    );
  } catch (error) {
    console.error("Lỗi khi cập nhật thời gian hoạt động cuối:", error);
  }
};

// Cập nhật thời gian của một cuộc trò chuyện đã tồn tại
export const updateChatTimestamp = async (uid, chatId) => {
  if (!uid || !chatId) {
    console.error("updateChatTimestamp: UID hoặc chatId không hợp lệ!");
    return;
  }

  try {
    const chatDocRef = doc(db, "users", uid, "chatHistory", chatId);
    await updateDoc(chatDocRef, {
      updatedAt: serverTimestamp(),
    });
    console.log(`Đã cập nhật thời gian cho cuộc trò chuyện ${chatId}`);
  } catch (error) {
    console.error("Lỗi khi cập nhật thời gian cuộc trò chuyện:", error);
  }
};

// Lưu hoặc cập nhật lịch sử chat
export const saveChatHistory = async (uid, messages, chatId = null) => {
  if (!uid || !messages.length) {
    console.error("saveChatHistory: UID hoặc messages không hợp lệ!");
    return null;
  }

  try {
    const chatRef = collection(db, "users", uid, "chatHistory");
    const firstQuestion = messages[0].text; // Lấy câu hỏi đầu tiên làm tiêu đề

    if (chatId) {
      // Nếu có chatId, cập nhật cuộc trò chuyện hiện có
      const chatDocRef = doc(db, "users", uid, "chatHistory", chatId);
      await setDoc(chatDocRef, {
        title: firstQuestion,
        messages: messages,
        updatedAt: serverTimestamp(),
      }, { merge: true });
      console.log(`Đã cập nhật cuộc trò chuyện ${chatId}`);
      return chatId;
    } else {
      // Nếu không có chatId, tạo mới
      const docRef = await addDoc(chatRef, {
        title: firstQuestion,
        messages: messages,
        createdAt: serverTimestamp(),
        updatedAt: serverTimestamp(),
      });
      console.log("Đã lưu lịch sử chat mới!");
      return docRef.id;
    }
  } catch (error) {
    console.error("Lỗi khi lưu/cập nhật lịch sử chat:", error);
    return null;
  }
};

// Lấy danh sách lịch sử chat từ subcollection chatHistory
export const getChatHistory = async (uid) => {
  if (!uid) {
    console.error("getChatHistory: UID không hợp lệ!");
    return [];
  }

  try {
    const chatRef = collection(db, "users", uid, "chatHistory");
    const q = query(chatRef, orderBy("updatedAt", "desc")); // Sắp xếp theo thời gian tạo, mới nhất trước
    const querySnapshot = await getDocs(q);
    const chatHistory = querySnapshot.docs.map(doc => ({
      id: doc.id,
      ...doc.data(),
    }));
    console.log("Đã lấy lịch sử chat:", chatHistory);
    return chatHistory;
  } catch (error) {
    console.error("Lỗi khi lấy lịch sử chat:", error);
    return [];
  }
};

// Xóa một cuộc hội thoại từ chatHistory
export const deleteChatHistory = async (uid, chatId) => {
  if (!uid || !chatId) {
    console.error("deleteChatHistory: UID hoặc chatId không hợp lệ!");
    return;
  }
  try {
    const chatDocRef = doc(db, "users", uid, "chatHistory", chatId);
    await deleteDoc(chatDocRef);
    console.log(`Đã xóa cuộc hội thoại ${chatId}`);
  } catch (error) {
    console.error("Lỗi khi xóa cuộc hội thoại:", error);
    throw error;
  }
};