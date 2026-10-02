import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Award, Mail, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/hooks/use-toast'

/** Map Firebase error codes to user-friendly messages */
function getAuthErrorMessage(code: string): string {
  const messages: Record<string, string> = {
    'auth/invalid-email': 'Invalid email address.',
    'auth/user-not-found': 'No account found with this email.',
    'auth/wrong-password': 'Incorrect password. Try again.',
    'auth/invalid-credential': 'Incorrect email or password.',
    'auth/too-many-requests': 'Too many failed attempts. Please wait a few minutes.',
    'auth/user-disabled': 'This account has been disabled.',
    'auth/network-request-failed': 'Network error. Check your connection.',
    'auth/popup-closed-by-user': 'Sign-in popup was closed. Please try again.',
    'auth/popup-blocked': 'Popup was blocked by your browser. Allow popups and try again.',
    'auth/cancelled-popup-request': 'Sign-in was cancelled.',
    'auth/unauthorized-domain':
      'This domain is not authorized for Google Sign-In. Add it to Firebase Console > Authentication > Settings > Authorized Domains.',
    'auth/operation-not-allowed':
      'Google Sign-In is not enabled. Enable Google provider in Firebase Console > Authentication > Sign-in method.',
    'auth/account-exists-with-different-credential':
      'An account already exists with this email. Try signing in with a different method.',
  }
  return messages[code] ?? 'Something went wrong. Please try again.'
}

export default function LoginPage() {
  const { signIn, signInWithGoogle } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loadingEmail, setLoadingEmail] = useState(false)
  const [loadingGoogle, setLoadingGoogle] = useState(false)

  // Redirect to previous page after login, or dashboard by default
  const redirectTo = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard'

  const handleEmailSignIn = async (e: FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      setError('Please enter your email and password.')
      return
    }
    setError('')
    setLoadingEmail(true)
    try {
      await signIn(email, password)
      toast.success('Signed in successfully!', 'Welcome back to CertFlow.')
      navigate(redirectTo, { replace: true })
    } catch (err: unknown) {
      const code = (err as { code?: string }).code ?? ''
      setError(getAuthErrorMessage(code))
    } finally {
      setLoadingEmail(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setError('')
    setLoadingGoogle(true)
    try {
      await signInWithGoogle()
      toast.success('Signed in successfully!', 'Welcome to CertFlow.')
      navigate(redirectTo, { replace: true })
    } catch (err: unknown) {
      console.error('Google Sign-In failed:', err)
      const code = (err as { code?: string }).code ?? ''
      setError(getAuthErrorMessage(code))
    } finally {
      setLoadingGoogle(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel — branding */}
      <div className="hidden lg:flex lg:w-1/2 certflow-gradient relative overflow-hidden flex-col justify-between p-12">
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'radial-gradient(circle, white 1px, transparent 1px)',
            backgroundSize: '30px 30px',
          }}
        />
        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3 text-white">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
            <Award className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold">CertFlow</span>
        </div>

        {/* Tagline */}
        <div className="relative z-10 text-white">
          <div className="flex items-center gap-2 mb-4 text-white/70 text-sm font-medium uppercase tracking-wider">
            <div className="h-px w-8 bg-white/50" />
            Certificate Platform
          </div>
          <h2 className="text-3xl font-bold mb-4 leading-snug">
            Certificate generation
            <br />
            made effortless.
          </h2>
          <p className="text-white/70 text-base leading-relaxed">
            Import participants, design templates, generate certificates,
            and send them via Gmail — all in one platform.
          </p>
          <div className="mt-8 flex flex-col gap-3">
            {[
              'Excel/CSV import with auto column detection',
              'Visual certificate editor with drag-and-drop',
              'Bulk Gmail distribution with real-time tracking',
              'Public certificate verification via unique ID',
            ].map((item) => (
              <div key={item} className="flex items-start gap-2.5 text-sm text-white/80">
                <div className="h-1.5 w-1.5 rounded-full bg-white/60 mt-1.5 flex-shrink-0" />
                {item}
              </div>
            ))}
          </div>
        </div>

        {/* Bottom decoration */}
        <div className="relative z-10 text-white/40 text-xs">
          Secured with Firebase Authentication · OAuth 2.0
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 items-center justify-center p-6 bg-background">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-md"
        >
          {/* Mobile logo */}
          <Link to="/" className="flex items-center gap-2.5 mb-8 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl certflow-gradient">
              <Award className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold">CertFlow</span>
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-bold tracking-tight mb-1">Welcome back</h1>
            <p className="text-muted-foreground text-sm">Sign in to your CertFlow account</p>
          </div>

          {/* Google Sign-In */}
          <Button
            id="btn-google-signin"
            type="button"
            variant="outline"
            size="lg"
            className="w-full gap-3 mb-4"
            onClick={handleGoogleSignIn}
            loading={loadingGoogle}
            disabled={loadingEmail}
          >
            {!loadingGoogle && (
              <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden>
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
            )}
            Continue with Google
          </Button>

          <div className="flex items-center gap-3 mb-4">
            <Separator className="flex-1" />
            <span className="text-xs text-muted-foreground px-1">or sign in with email</span>
            <Separator className="flex-1" />
          </div>

          {/* Email/Password form */}
          <form onSubmit={handleEmailSignIn} className="space-y-4">
            {/* Error banner */}
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="flex items-start gap-2.5 rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive"
              >
                <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <span>{error}</span>
              </motion.div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor="email">Email address</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  className="pl-9"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  required
                  disabled={loadingEmail || loadingGoogle}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Password</Label>
                <Link
                  to="/forgot-password"
                  className="text-xs text-primary hover:underline"
                  tabIndex={-1}
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  className="pl-9 pr-9"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                  disabled={loadingEmail || loadingGoogle}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <Button
              id="btn-email-signin"
              type="submit"
              size="lg"
              className="w-full"
              loading={loadingEmail}
              disabled={loadingGoogle}
            >
              Sign In
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{' '}
            <Link to="/signup" className="text-primary hover:underline font-medium">
              Create one free
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
