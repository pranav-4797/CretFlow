import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Award,
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/hooks/use-toast'

function getAuthErrorMessage(code: string): string {
  const currentHost = typeof window !== 'undefined' ? window.location.hostname : 'current domain'
  const messages: Record<string, string> = {
    'auth/email-already-in-use': 'An account with this email already exists. Try signing in.',
    'auth/invalid-email': 'Invalid email address.',
    'auth/weak-password': 'Password must be at least 6 characters.',
    'auth/network-request-failed': 'Network error. Check your connection.',
    'auth/popup-closed-by-user': 'Google sign-up was cancelled.',
    'auth/popup-blocked': 'Popup was blocked by your browser. Allow popups and try again.',
    'auth/unauthorized-domain':
      currentHost === '127.0.0.1'
        ? 'Domain "127.0.0.1" is not authorized. Please open http://localhost:5173 instead, or click "Add domain" in Firebase Console and add "127.0.0.1".'
        : `Domain "${currentHost}" is not authorized. Please click "Add domain" in Firebase Console > Authentication > Settings > Authorised domains and enter "${currentHost}".`,
    'auth/operation-not-allowed':
      'Google Sign-In is not enabled. Go to Firebase Console > Authentication > Sign-in method, click Google, and enable it.',
    'auth/account-exists-with-different-credential':
      'An account already exists with this email. Try a different sign-in method.',
  }
  return messages[code] ?? 'Something went wrong. Please try again.'
}

/** Real-time password strength indicator */
function getPasswordStrength(pw: string): { label: string; color: string; width: string } {
  if (pw.length === 0) return { label: '', color: 'bg-muted', width: '0%' }
  if (pw.length < 6) return { label: 'Too short', color: 'bg-destructive', width: '20%' }
  if (pw.length < 8) return { label: 'Weak', color: 'bg-orange-500', width: '40%' }
  const hasUpper = /[A-Z]/.test(pw)
  const hasNumber = /[0-9]/.test(pw)
  const hasSpecial = /[^A-Za-z0-9]/.test(pw)
  const score = [hasUpper, hasNumber, hasSpecial].filter(Boolean).length
  if (score === 0) return { label: 'Fair', color: 'bg-yellow-500', width: '60%' }
  if (score === 1) return { label: 'Good', color: 'bg-blue-500', width: '75%' }
  return { label: 'Strong', color: 'bg-green-500', width: '100%' }
}

export default function SignupPage() {
  const { signUp, signInWithGoogle } = useAuth()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loadingEmail, setLoadingEmail] = useState(false)
  const [loadingGoogle, setLoadingGoogle] = useState(false)

  const strength = getPasswordStrength(password)

  const handleEmailSignUp = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) { setError('Please enter your full name.'); return }
    if (!email) { setError('Please enter your email address.'); return }
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return }

    setError('')
    setLoadingEmail(true)
    try {
      await signUp(email, password, name.trim())
      toast.success('Account created!', 'Welcome to CertFlow. Let\'s build your first campaign.')
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      const code = (err as { code?: string }).code ?? ''
      setError(getAuthErrorMessage(code))
    } finally {
      setLoadingEmail(false)
    }
  }

  const handleGoogleSignUp = async () => {
    setError('')
    setLoadingGoogle(true)
    try {
      await signInWithGoogle()
      toast.success('Account created!', 'Welcome to CertFlow.')
      navigate('/dashboard', { replace: true })
    } catch (err: unknown) {
      const code = (err as { code?: string }).code ?? ''
      setError(getAuthErrorMessage(code))
    } finally {
      setLoadingGoogle(false)
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 certflow-gradient relative overflow-hidden flex-col justify-between p-12">
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'radial-gradient(circle, white 1px, transparent 1px)',
            backgroundSize: '30px 30px',
          }}
        />
        <div className="relative z-10 flex items-center gap-3 text-white">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/20">
            <Award className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold">CertFlow</span>
        </div>

        <div className="relative z-10 text-white">
          <div className="flex items-center gap-2 mb-4 text-white/70 text-sm font-medium uppercase tracking-wider">
            <div className="h-px w-8 bg-white/50" />
            Get Started Free
          </div>
          <h2 className="text-3xl font-bold mb-4 leading-snug">
            Start issuing certificates
            <br />
            in minutes.
          </h2>
          <p className="text-white/70 text-base leading-relaxed">
            No credit card required. Set up your first campaign, design your template,
            and send certificates to hundreds of participants — all in one place.
          </p>
          <div className="mt-8 grid grid-cols-2 gap-4">
            {[
              { value: '500K+', label: 'Certificates issued' },
              { value: '99.2%', label: 'Delivery rate' },
              { value: '1,200+', label: 'Organizations' },
              { value: '10x', label: 'Time saved' },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl bg-white/10 backdrop-blur-sm p-4">
                <div className="text-2xl font-bold">{stat.value}</div>
                <div className="text-white/70 text-xs mt-0.5">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-white/40 text-xs">
          Free to start · No credit card required
        </div>
      </div>

      {/* Right panel */}
      <div className="flex flex-1 items-center justify-center p-6 bg-background overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-md py-8"
        >
          <Link to="/" className="flex items-center gap-2.5 mb-8 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl certflow-gradient">
              <Award className="h-4 w-4 text-white" />
            </div>
            <span className="text-lg font-bold">CertFlow</span>
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-bold tracking-tight mb-1">Create your account</h1>
            <p className="text-muted-foreground text-sm">Get started with CertFlow for free</p>
          </div>

          {/* Google Sign-Up */}
          <Button
            id="btn-google-signup"
            type="button"
            variant="outline"
            size="lg"
            className="w-full gap-3 mb-4"
            onClick={handleGoogleSignUp}
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
            Sign up with Google
          </Button>

          <div className="flex items-center gap-3 mb-4">
            <Separator className="flex-1" />
            <span className="text-xs text-muted-foreground px-1">or create with email</span>
            <Separator className="flex-1" />
          </div>

          <form onSubmit={handleEmailSignUp} className="space-y-4">
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
              <Label htmlFor="name">Full name</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="name"
                  placeholder="Jane Doe"
                  className="pl-9"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoComplete="name"
                  required
                  disabled={loadingEmail || loadingGoogle}
                />
              </div>
            </div>

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
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Min. 6 characters"
                  className="pl-9 pr-9"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                  disabled={loadingEmail || loadingGoogle}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {/* Password strength bar */}
              {password.length > 0 && (
                <div className="space-y-1">
                  <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                    <motion.div
                      animate={{ width: strength.width }}
                      transition={{ duration: 0.3 }}
                      className={`h-full rounded-full ${strength.color}`}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Strength: <span className="font-medium text-foreground">{strength.label}</span>
                  </p>
                </div>
              )}
            </div>

            <Button
              id="btn-create-account"
              type="submit"
              size="lg"
              className="w-full"
              loading={loadingEmail}
              disabled={loadingGoogle}
            >
              Create Account
            </Button>
          </form>

          <div className="mt-4 flex items-start gap-2 text-xs text-muted-foreground">
            <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 flex-shrink-0 text-green-500" />
            <span>
              By signing up, you agree to use CertFlow responsibly. Your data is stored
              securely with Firebase Authentication.
            </span>
          </div>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </motion.div>
      </div>
    </div>
  )
}
