import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';

const firebaseConfig = {
    apiKey: "AIzaSyDufr1TmeA5XkkWS6wxxULeCyW4_YNLRV0",
    authDomain: "assistant-project-c40dd.firebaseapp.com",
    projectId: "assistant-project-c40dd",
    storageBucket: "assistant-project-c40dd.firebasestorage.app",
    messagingSenderId: "347401192316",
    appId: "1:347401192316:web:6a4abd840715d3580a1af9",
    measurementId: "G-1T4RCT9BXR"
  };

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);
export const googleProvider = new GoogleAuthProvider();