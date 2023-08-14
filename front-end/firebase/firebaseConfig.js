import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, EmailAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID
};

let app, analytics, auth;

if (typeof window !== 'undefined') {
  if (!getApps().length) {  // Checks if there isn't already an app initialized.
    app = initializeApp(firebaseConfig);
  } else {
    app = getApp();  // If there is already an initialized app, get it.
  }

  try {
    const { getAnalytics } = require('firebase/analytics');
    analytics = getAnalytics(app);
  } catch (error) {
    console.error("Failed to initialize analytics:", error);
  }

  auth = getAuth(app);
}

export { app, analytics, auth, GoogleAuthProvider, EmailAuthProvider };
