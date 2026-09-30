/**
 * Firebase Authentication Context — Phase 2
 *
 * Provides:
 *  - Email/password sign-in and sign-up
 *  - Google Sign-In via OAuth popup
 *  - Persistent authentication (Firebase handles token refresh)
 *  - Sign out
 *  - getIdToken() for API calls
 *  - Protected routes via useAuth()
 *
 * Security notes:
 *  - Firebase ID tokens are short-lived (1h) and auto-refreshed
 *  - We NEVER store raw tokens in localStorage/sessionStorage
 *  - Backend must verify tokens using Firebase Admin SDK
 *  - User UID is sourced from the verified token, never from the client
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react'
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  updateProfile,
  sendPasswordResetEmail,
  type User as FirebaseUser,
} from 'firebase/auth'
import { auth } from '@/lib/firebase'
import type { User } from '@/types'

// ─── Types ───────────────────────────────────────────────────────────────────

interface AuthContextValue {
  /** Authenticated user profile, or null if not signed in */
  user: User | null
  /** Firebase user object — use for advanced auth operations */
  firebaseUser: FirebaseUser | null
  /** True while Firebase is determining the initial auth state */
  loading: boolean
  /** True when a user is authenticated */
  isAuthenticated: boolean
  /** Sign in with email and password */
  signIn: (email: string, password: string) => Promise<void>
  /** Sign in with Google (popup) */
  signInWithGoogle: () => Promise<void>
  /** Create account with email and password */
  signUp: (email: string, password: string, displayName: string) => Promise<void>
  /** Sign out and clear session */
  signOut: () => Promise<void>
  /** Send password reset email */
  resetPassword: (email: string) => Promise<void>
  /** Get current Firebase ID token for API requests */
  getIdToken: (forceRefresh?: boolean) => Promise<string | null>
}

// ─── Context ─────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null)

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Map a FirebaseUser to our app's User type */
function mapFirebaseUser(fbUser: FirebaseUser): User {
  return {
    id: fbUser.uid,
    email: fbUser.email ?? '',
    displayName: fbUser.displayName,
    photoURL: fbUser.photoURL,
    createdAt: fbUser.metadata.creationTime ?? new Date().toISOString(),
  }
}

// Google OAuth provider (reused across sign-ins)
const googleProvider = new GoogleAuthProvider()
googleProvider.addScope('email')
googleProvider.addScope('profile')

// ─── Provider ────────────────────────────────────────────────────────────────

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [firebaseUser, setFirebaseUser] = useState<FirebaseUser | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Subscribe to Firebase auth state changes
  // This handles: page refresh, token expiry, sign-in from another tab, etc.
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (fbUser) => {
      if (fbUser) {
        setFirebaseUser(fbUser)
        setUser(mapFirebaseUser(fbUser))
      } else {
        setFirebaseUser(null)
        setUser(null)
      }
      setLoading(false)
    })

    // Clean up listener when the provider unmounts
    return unsubscribe
  }, [])

  // ── Auth Methods ───────────────────────────────────────────────────────────

  const signIn = useCallback(async (email: string, password: string) => {
    await signInWithEmailAndPassword(auth, email, password)
    // onAuthStateChanged will update the user state automatically
  }, [])

  const signInWithGoogle = useCallback(async () => {
    await signInWithPopup(auth, googleProvider)
    // onAuthStateChanged will update the user state automatically
  }, [])

  const signUp = useCallback(
    async (email: string, password: string, displayName: string) => {
      const credential = await createUserWithEmailAndPassword(auth, email, password)
      // Set the display name immediately after account creation
      if (credential.user && displayName.trim()) {
        await updateProfile(credential.user, { displayName: displayName.trim() })
        // Update local state to reflect the new display name
        setUser(mapFirebaseUser(credential.user))
      }
    },
    [],
  )

  const signOut = useCallback(async () => {
    await firebaseSignOut(auth)
    // onAuthStateChanged will clear user state automatically
  }, [])

  const resetPassword = useCallback(async (email: string) => {
    await sendPasswordResetEmail(auth, email)
  }, [])

  const getIdToken = useCallback(
    async (forceRefresh = false): Promise<string | null> => {
      if (!firebaseUser) return null
      return firebaseUser.getIdToken(forceRefresh)
    },
    [firebaseUser],
  )

  // ── Context Value ──────────────────────────────────────────────────────────

  const value: AuthContextValue = {
    user,
    firebaseUser,
    loading,
    isAuthenticated: !!user,
    signIn,
    signInWithGoogle,
    signUp,
    signOut,
    resetPassword,
    getIdToken,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export type { AuthContextValue }
