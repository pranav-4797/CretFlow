/**
 * Firebase client-side initialization.
 *
 * This module creates and exports the Firebase App, Auth, and Analytics
 * instances. It is the single source of truth for all Firebase SDK access
 * in the frontend. Import from here — never call initializeApp() elsewhere.
 *
 * All config values come from Vite environment variables (VITE_FIREBASE_*).
 * These are injected at build time and are safe to expose (they are
 * client-side keys, not secrets).
 */

import { initializeApp, getApps, type FirebaseApp } from 'firebase/app'
import {
  getAuth,
  type Auth,
  connectAuthEmulator,
} from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
}

// Avoid double-initialization in HMR / strict mode environments
let app: FirebaseApp
if (getApps().length === 0) {
  app = initializeApp(firebaseConfig)
} else {
  app = getApps()[0]
}

// Auth instance — used throughout the app
const auth: Auth = getAuth(app)

// Connect to Firebase Auth Emulator in local development if configured
if (
  import.meta.env.VITE_USE_FIREBASE_EMULATOR === 'true' &&
  import.meta.env.DEV
) {
  connectAuthEmulator(auth, 'http://localhost:9099', { disableWarnings: true })
}

export { app, auth }
export default app
