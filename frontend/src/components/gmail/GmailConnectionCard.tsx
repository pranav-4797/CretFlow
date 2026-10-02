import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mail,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  RefreshCw,
  Send,
  Trash2,
  Loader2,
  ShieldCheck,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { gmailService, GmailStatus } from '@/services/gmail'
import { useAuth } from '@/contexts/AuthContext'

export function GmailConnectionCard() {
  const { user } = useAuth()
  const [status, setStatus] = useState<GmailStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  // Test email state
  const [showTestForm, setShowTestForm] = useState(false)
  const [testRecipient, setTestRecipient] = useState('')
  const [testCustomNote, setTestCustomNote] = useState('')
  const [sendingTest, setSendingTest] = useState(false)
  const [testFeedback, setTestFeedback] = useState<{ success: boolean; message: string } | null>(null)

  // URL notification feedback
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Fetch status on mount
  const fetchStatus = async () => {
    try {
      setLoading(true)
      const data = await gmailService.getStatus()
      setStatus(data)
    } catch (err: any) {
      console.error('Failed to load Gmail status:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Process query params from OAuth redirect
    const params = new URLSearchParams(window.location.search)
    const gmailStatus = params.get('gmail_status')
    const email = params.get('email')
    const errorCode = params.get('error_code')

    if (gmailStatus === 'connected') {
      setNotification({
        type: 'success',
        message: `Successfully connected Google account${email ? `: ${email}` : ''}!`,
      })
      // Clean query params from URL without reload
      window.history.replaceState({}, '', window.location.pathname)
    } else if (gmailStatus === 'error') {
      setNotification({
        type: 'error',
        message: `Failed to connect Gmail account (${errorCode || 'Authorization error'}). Please try again.`,
      })
      window.history.replaceState({}, '', window.location.pathname)
    }

    fetchStatus()
  }, [])

  // Auto-fill test email with current user's email if available
  useEffect(() => {
    if (user?.email && !testRecipient) {
      setTestRecipient(user.email)
    }
  }, [user, testRecipient])

  const handleConnect = async () => {
    try {
      setConnecting(true)
      const res = await gmailService.getConnectUrl()
      if (res?.authorization_url) {
        window.location.href = res.authorization_url
      }
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Could not initiate Google connection.',
      })
      setConnecting(false)
    }
  }

  const handleDisconnect = async () => {
    if (!window.confirm('Are you sure you want to disconnect your Gmail integration? Pending email distributions will be cancelled.')) {
      return
    }

    try {
      setDisconnecting(true)
      await gmailService.disconnect()
      await fetchStatus()
      setShowTestForm(false)
      setNotification({
        type: 'success',
        message: 'Gmail account successfully disconnected and revoked.',
      })
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Failed to disconnect Gmail account.',
      })
    } finally {
      setDisconnecting(false)
    }
  }

  const handleSendTest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!testRecipient) return

    try {
      setSendingTest(true)
      setTestFeedback(null)
      const res = await gmailService.sendTestEmail({
        recipient_email: testRecipient,
        subject: 'CertFlow Gmail Integration Verification',
        custom_message: testCustomNote,
      })
      setTestFeedback({
        success: true,
        message: `Test email sent to ${res.recipient} (Message ID: ${res.message_id || 'OK'})`,
      })
    } catch (err: any) {
      setTestFeedback({
        success: false,
        message: err.message || 'Failed to deliver test email. Check Gmail connection.',
      })
    } finally {
      setSendingTest(false)
    }
  }

  return (
    <Card className="border border-border/80 shadow-sm overflow-hidden">
      <CardHeader className="bg-muted/30 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-red-500/10 text-red-600 dark:text-red-400">
              <Mail className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold">Gmail Integration</CardTitle>
              <CardDescription className="text-xs">
                Send personalized certificates directly via the official Gmail API (OAuth 2.0).
              </CardDescription>
            </div>
          </div>
          {status?.is_connected ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Connected
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
              <AlertCircle className="h-3.5 w-3.5" />
              Not Connected
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-5 space-y-4">
        {/* Banner Alert Notification */}
        <AnimatePresence>
          {notification && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between ${
                notification.type === 'success'
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20'
                  : 'bg-red-500/10 text-red-700 dark:text-red-300 border border-red-500/20'
              }`}
            >
              <div className="flex items-center gap-2">
                {notification.type === 'success' ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                ) : (
                  <AlertCircle className="h-4 w-4 shrink-0" />
                )}
                <span>{notification.message}</span>
              </div>
              <button
                onClick={() => setNotification(null)}
                className="text-muted-foreground hover:text-foreground text-xs ml-2"
              >
                ×
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {loading ? (
          <div className="flex items-center justify-center py-6 text-muted-foreground gap-2">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-sm">Checking Gmail status...</span>
          </div>
        ) : status?.is_connected ? (
          /* Connected State */
          <div className="space-y-4">
            <div className="rounded-lg border bg-card p-4 space-y-2.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <p className="text-xs text-muted-foreground">Connected Google Account</p>
                  <p className="text-sm font-medium text-foreground">{status.google_email}</p>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                  <span>Tokens Encrypted at Rest (AES-128 / Fernet)</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-muted-foreground pt-2 border-t">
                <div>
                  <span className="font-medium text-foreground">Connected: </span>
                  {status.connected_at ? new Date(status.connected_at).toLocaleString() : 'N/A'}
                </div>
                <div>
                  <span className="font-medium text-foreground">Last Email Sent: </span>
                  {status.last_used_at ? new Date(status.last_used_at).toLocaleString() : 'Never'}
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowTestForm(!showTestForm)}
                className="gap-1.5 text-xs"
              >
                <Send className="h-3.5 w-3.5 text-primary" />
                {showTestForm ? 'Hide Test Form' : 'Send Test Email'}
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={fetchStatus}
                disabled={loading}
                className="gap-1.5 text-xs text-muted-foreground"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Refresh Status
              </Button>

              <Button
                variant="destructive"
                size="sm"
                onClick={handleDisconnect}
                disabled={disconnecting}
                className="gap-1.5 text-xs ml-auto"
              >
                {disconnecting ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                Disconnect
              </Button>
            </div>

            {/* Test Email Form */}
            <AnimatePresence>
              {showTestForm && (
                <motion.form
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  onSubmit={handleSendTest}
                  className="rounded-lg border bg-muted/20 p-4 space-y-3 mt-3"
                >
                  <div className="flex items-center justify-between pb-1 border-b">
                    <p className="text-xs font-semibold">Send Controlled Test Email</p>
                    <span className="text-[11px] text-muted-foreground">Uses Gmail API</span>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="test-email" className="text-xs">Recipient Address</Label>
                    <Input
                      id="test-email"
                      type="email"
                      required
                      placeholder="recipient@example.com"
                      value={testRecipient}
                      onChange={(e) => setTestRecipient(e.target.value)}
                      className="text-xs h-8"
                    />
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="test-note" className="text-xs">Optional Note</Label>
                    <Input
                      id="test-note"
                      placeholder="e.g. Testing CertFlow email delivery"
                      value={testCustomNote}
                      onChange={(e) => setTestCustomNote(e.target.value)}
                      className="text-xs h-8"
                    />
                  </div>

                  {testFeedback && (
                    <div
                      className={`p-2.5 rounded text-xs ${
                        testFeedback.success
                          ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20'
                          : 'bg-red-500/10 text-red-700 dark:text-red-300 border border-red-500/20'
                      }`}
                    >
                      {testFeedback.message}
                    </div>
                  )}

                  <div className="flex justify-end pt-1">
                    <Button
                      type="submit"
                      size="sm"
                      disabled={sendingTest || !testRecipient}
                      className="gap-1.5 text-xs"
                    >
                      {sendingTest ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          Sending...
                        </>
                      ) : (
                        <>
                          <Send className="h-3.5 w-3.5" />
                          Send Test
                        </>
                      )}
                    </Button>
                  </div>
                </motion.form>
              )}
            </AnimatePresence>
          </div>
        ) : (
          /* Disconnected State */
          <div className="space-y-3 py-2">
            <p className="text-xs text-muted-foreground leading-relaxed">
              Connect your Google account to automatically distribute certificates through Gmail.
              CertFlow uses the least-privilege scope (<code>https://www.googleapis.com/auth/gmail.send</code>)
              so only email sending is authorized.
            </p>

            <div className="pt-2">
              <Button
                variant="gradient"
                size="sm"
                onClick={handleConnect}
                disabled={connecting}
                className="gap-2"
              >
                {connecting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    <ExternalLink className="h-4 w-4" />
                    Connect with Google Gmail
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
