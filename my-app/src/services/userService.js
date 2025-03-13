import { doc, setDoc } from "firebase/firestore";
import { db } from "../config/firebase";
import { serverTimestamp } from "firebase/firestore";

export const updateUserLastActive = async (uid) => {
  if (!uid) {
    console.error("updateUserLastActive: UID không hợp lệ!");
    return;
  }

  try {
    await setDoc(
      doc(db, "users", uid),
      { lastActive: serverTimestamp() }, // Sử dụng serverTimestamp() của Firebase
      { merge: true }
    );
  } catch (error) {
    console.error("Lỗi khi cập nhật thời gian hoạt động cuối:", error);
  }
};
