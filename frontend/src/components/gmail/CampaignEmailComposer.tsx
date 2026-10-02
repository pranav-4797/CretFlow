import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mail,
  Send,
  Eye,
  AlertCircle,
  RotateCcw,
  Loader2,
  FileCheck,
  Pause,
  Play,
  XCircle,
  RefreshCw,
  Info,
  Sparkles,
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import {
  gmailService,
  GmailStatus,
  CampaignEmailStatus,
  SendPreviewResponse,
} from '@/services/gmail'

interface CampaignEmailComposerProps {
  campaignId: string
  campaignName?: string
}

export function CampaignEmailComposer({
  campaignId,
  campaignName = 'CertFlow Campaign',
}: CampaignEmailComposerProps) {
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null)
  const [loadingStatus, setLoadingStatus] = useState(true)

  // Template state
  const [subjectTemplate, setSubjectTemplate] = useState('Your Certificate for {{event_name}}')
  const [bodyTemplate, setBodyTemplate] = useState(
    'Hello {{name}},\n\nCongratulations on completing {{event_name}}! Please find your personalized certificate attached to this email.\n\nBest regards,\nCertFlow Organizing Team'
  )
  const [confirmSend, setConfirmSend] = useState(false)

  // Preview state
  const [preview, setPreview] = useState<SendPreviewResponse | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)

  // Sending & Progress state
  const [sending, setSending] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [feedback, setFeedback] = useState<{ success: boolean; message: string } | null>(null)
  const [campaignStats, setCampaignStats] = useState<CampaignEmailStatus | null>(null)
  const [retrying, setRetrying] = useState(false)

  // Load Gmail status & campaign stats
  const fetchStatusAndStats = async () => {
    try {
      setLoadingStatus(true)
      const [statusRes, statsRes] = await Promise.all([
        gmailService.getStatus().catch(() => ({ is_connected: false })),
        gmailService.getCampaignStatus(campaignId).catch(() => null),
      ])
      setGmailStatus(statusRes)
      if (statsRes) setCampaignStats(statsRes)
    } finally {
      setLoadingStatus(false)
    }
  }

  useEffect(() => {
    fetchStatusAndStats()
    // Periodic refresh while in processing state
    const interval = setInterval(() => {
      if (campaignStats?.campaign_status === 'processing') {
        gmailService.getCampaignStatus(campaignId).then((res) => {
          if (res) setCampaignStats(res)
        }).catch(() => {})
      }
    }, 4000)

    return () => clearInterval(interval)
  }, [campaignId, campaignStats?.campaign_status])

  // Handle preview generation
  const handleGeneratePreview = async () => {
    try {
      setLoadingPreview(true)
      const res = await gmailService.sendPreview({
        subject_template: subjectTemplate,
        body_template: bodyTemplate,
        sample_variables: {
          name: 'Jane Doe',
          event_name: campaignName,
          certificate_id: 'CERT-2026-001',
        },
      })
      setPreview(res)
      setShowPreviewModal(true)
    } catch (err: any) {
      setFeedback({
        success: false,
        message: err.message || 'Failed to render template preview.',
      })
    } finally {
      setLoadingPreview(false)
    }
  }

  // Handle bulk sending
  const handleSendCampaign = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!gmailStatus?.is_connected) {
      setFeedback({
        success: false,
        message: 'Your Gmail account is not connected. Please connect Gmail in Settings before dispatching.',
      })
      return
    }

    if (!confirmSend) {
      setFeedback({
        success: false,
        message: 'Please check the authorization box above ("Step 2") to confirm and start sending emails.',
      })
      return
    }

    try {
      setSending(true)
      setFeedback(null)
      const res = await gmailService.sendCampaign({
        campaign_id: campaignId,
        subject_template: subjectTemplate,
        body_template: bodyTemplate,
        batch_size: 15,
        confirm: true,
      })
      setFeedback({
        success: true,
        message: res.message || 'Campaign email batch processing started in background!',
      })
      // Refresh stats
      const stats = await gmailService.getCampaignStatus(campaignId)
      setCampaignStats(stats)
    } catch (err: any) {
      setFeedback({
        success: false,
        message: err.message || 'Failed to trigger campaign email sending.',
      })
    } finally {
      setSending(false)
    }
  }

  // Campaign controls: Pause, Resume, Cancel, Reconcile
  const handlePause = async () => {
    try {
      setActionLoading(true)
      const res = await gmailService.pauseCampaign(campaignId)
      setFeedback({ success: true, message: res.message })
      const stats = await gmailService.getCampaignStatus(campaignId)
      setCampaignStats(stats)
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to pause campaign.' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleResume = async () => {
    try {
      setActionLoading(true)
      const res = await gmailService.resumeCampaign(campaignId)
      setFeedback({ success: true, message: res.message })
      const stats = await gmailService.getCampaignStatus(campaignId)
      setCampaignStats(stats)
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to resume campaign.' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancel = async () => {
    if (!window.confirm('Are you sure you want to cancel remaining email sends for this campaign?')) {
      return
    }
    try {
      setActionLoading(true)
      const res = await gmailService.cancelCampaign(campaignId)
      setFeedback({ success: true, message: res.message })
      const stats = await gmailService.getCampaignStatus(campaignId)
      setCampaignStats(stats)
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to cancel campaign.' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleReconcile = async () => {
    try {
      setActionLoading(true)
      const stats = await gmailService.reconcileCampaign(campaignId)
      setCampaignStats(stats)
      setFeedback({ success: true, message: 'Campaign progress reconciled successfully.' })
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to reconcile campaign.' })
    } finally {
      setActionLoading(false)
    }
  }

  // Retry failed emails
  const handleRetryFailed = async () => {
    try {
      setRetrying(true)
      const res = await gmailService.retryFailed(campaignId)
      setFeedback({
        success: true,
        message: res.message,
      })
      const stats = await gmailService.getCampaignStatus(campaignId)
      setCampaignStats(stats)
    } catch (err: any) {
      setFeedback({
        success: false,
        message: err.message || 'Failed to retry failed emails.',
      })
    } finally {
      setRetrying(false)
    }
  }

  const insertVariable = (variable: string, target: 'subject' | 'body') => {
    if (target === 'subject') {
      setSubjectTemplate((prev) => `${prev} {{${variable}}}`)
    } else {
      setBodyTemplate((prev) => `${prev} {{${variable}}}`)
    }
  }

  const completionPercent = campaignStats?.total_count
    ? Math.round(((campaignStats.sent_count + campaignStats.failed_count + (campaignStats.cancelled_count || 0)) / campaignStats.total_count) * 100)
    : 0

  const statusColorMap: Record<string, string> = {
    draft: 'bg-muted text-muted-foreground',
    processing: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',
    paused: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
    completed: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
    failed: 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20',
    cancelled: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border border-gray-500/20',
  }

  return (
    <Card className="border border-border/80 shadow-sm">
      <CardHeader className="bg-muted/30 pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="text-base font-semibold">Distribute via Gmail</CardTitle>
              <CardDescription className="text-xs">
                Send personalized PDF certificates in small resumable batches via your connected Gmail account.
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {campaignStats?.campaign_status && (
              <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${statusColorMap[campaignStats.campaign_status] || 'bg-muted'}`}>
                {campaignStats.campaign_status}
              </span>
            )}
            {gmailStatus?.is_connected ? (
              <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded-full border border-emerald-500/20">
                Sender: {gmailStatus.google_email}
              </span>
            ) : (
              <span className="text-xs font-medium text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full border border-amber-500/20">
                Gmail Disconnected
              </span>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-5 space-y-5">
        {feedback && (
          <div
            className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between ${
              feedback.success
                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20'
                : 'bg-red-500/10 text-red-700 dark:text-red-300 border border-red-500/20'
            }`}
          >
            <span>{feedback.message}</span>
            <button onClick={() => setFeedback(null)} className="ml-2 font-bold">×</button>
          </div>
        )}

        {/* Render Free Tier Sleep Notice */}
        <div className="p-3 rounded-lg border border-blue-500/20 bg-blue-500/5 text-xs text-blue-800 dark:text-blue-300 flex items-start gap-2">
          <Info className="h-4 w-4 shrink-0 mt-0.5 text-blue-600 dark:text-blue-400" />
          <div>
            <span className="font-semibold">Resumable Free-Tier Processing: </span>
            Campaigns process in bounded batches (10–25 recipients). Progress is continuously saved in Firestore. If the free Render service spins down during inactivity, campaigns safely resume upon service wakeup.
          </div>
        </div>

        {/* Not connected warning */}
        {!loadingStatus && !gmailStatus?.is_connected && (
          <div className="p-3.5 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
            <div>
              <p className="font-semibold">Gmail account not connected</p>
              <p className="mt-0.5">
                You must connect your Gmail account in{' '}
                <a href="/settings" className="underline font-medium hover:text-foreground">
                  Settings &gt; Gmail Integration
                </a>{' '}
                before you can send certificate emails.
              </p>
            </div>
          </div>
        )}

        {/* Campaign progress stats & control bar */}
        {campaignStats && campaignStats.total_count > 0 && (
          <div className="p-4 rounded-lg border bg-muted/20 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground">Delivery Progress</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleReconcile}
                  disabled={actionLoading}
                  className="h-6 px-2 text-[11px] gap-1"
                >
                  <RefreshCw className={`h-3 w-3 ${actionLoading ? 'animate-spin' : ''}`} />
                  Sync
                </Button>
                <span className="text-muted-foreground font-mono">{completionPercent}% Complete</span>
              </div>
            </div>
            <Progress value={completionPercent} className="h-2" />

            <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 text-center pt-2">
              <div className="p-2 rounded bg-background border text-xs">
                <p className="text-muted-foreground text-[10px]">Total</p>
                <p className="font-bold text-foreground text-sm">{campaignStats.total_count}</p>
              </div>
              <div className="p-2 rounded bg-background border text-xs">
                <p className="text-muted-foreground text-[10px]">Sent</p>
                <p className="font-bold text-emerald-600 dark:text-emerald-400 text-sm">{campaignStats.sent_count}</p>
              </div>
              <div className="p-2 rounded bg-background border text-xs">
                <p className="text-muted-foreground text-[10px]">Queued</p>
                <p className="font-bold text-blue-600 dark:text-blue-400 text-sm">{campaignStats.queued_count}</p>
              </div>
              <div className="p-2 rounded bg-background border text-xs">
                <p className="text-muted-foreground text-[10px]">Processing</p>
                <p className="font-bold text-amber-600 dark:text-amber-400 text-sm">{campaignStats.processing_count}</p>
              </div>
              <div className="p-2 rounded bg-background border text-xs">
                <p className="text-muted-foreground text-[10px]">Failed</p>
                <p className="font-bold text-red-600 dark:text-red-400 text-sm">{campaignStats.failed_count}</p>
              </div>
              <div className="p-2 rounded bg-background border text-xs">
                <p className="text-muted-foreground text-[10px]">Cancelled</p>
                <p className="font-bold text-gray-500 text-sm">{campaignStats.cancelled_count || 0}</p>
              </div>
            </div>

            {/* Campaign Controls: Pause / Resume / Cancel */}
            <div className="flex items-center justify-between pt-2 border-t">
              <div className="flex items-center gap-2">
                {campaignStats.campaign_status === 'processing' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePause}
                    disabled={actionLoading}
                    className="gap-1.5 text-xs h-7"
                  >
                    <Pause className="h-3 w-3" />
                    Pause
                  </Button>
                )}
                {campaignStats.campaign_status === 'paused' && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleResume}
                    disabled={actionLoading}
                    className="gap-1.5 text-xs h-7 text-emerald-600"
                  >
                    <Play className="h-3 w-3" />
                    Resume
                  </Button>
                )}
                {(campaignStats.campaign_status === 'processing' || campaignStats.campaign_status === 'paused') && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleCancel}
                    disabled={actionLoading}
                    className="gap-1.5 text-xs h-7 text-red-600 hover:text-red-700"
                  >
                    <XCircle className="h-3 w-3" />
                    Cancel Campaign
                  </Button>
                )}
              </div>

              {campaignStats.failed_count > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRetryFailed}
                  disabled={retrying || actionLoading}
                  className="gap-1.5 text-xs h-7"
                >
                  <RotateCcw className="h-3 w-3" />
                  {retrying ? 'Retrying...' : 'Retry Failed Sends'}
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Composer Form */}
        <form onSubmit={handleSendCampaign} className="space-y-4">
          {/* Template Presets */}
          <div className="space-y-1.5 p-3 rounded-lg bg-muted/30 border">
            <Label className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-primary" />
              Quick Templates
            </Label>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setSubjectTemplate('Your Official Certificate for {{event_name}}')
                  setBodyTemplate(
                    'Dear {{name}},\n\nCongratulations on completing {{event_name}}!\n\nPlease find your personalized certificate attached to this email (Certificate ID: {{certificate_id}}).\n\nThank you for your active participation!\n\nWarm regards,\nEvent Organizing Committee'
                  )
                }}
                className="text-[11px] h-7 bg-background"
              >
                🎓 Professional Certificate
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setSubjectTemplate('{{name}}, your Certificate of Achievement for {{event_name}}!')
                  setBodyTemplate(
                    'Hi {{name}},\n\nThank you for being an inspiring part of {{event_name}}! We are thrilled to recognize your dedication.\n\nYour verified certificate is attached. Certificate ID: {{certificate_id}}.\n\nKeep building and innovating!\n\nBest,\nThe Organizing Team'
                  )
                }}
                className="text-[11px] h-7 bg-background"
              >
                🚀 Tech Summit & Hackathon
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setSubjectTemplate('Certificate of Attendance — {{event_name}}')
                  setBodyTemplate(
                    'Dear {{name}},\n\nThank you for attending {{event_name}}.\n\nYour verified certificate of attendance is attached to this email. You can present this for professional verification with ID: {{certificate_id}}.\n\nSincerely,\nCertFlow Team'
                  )
                }}
                className="text-[11px] h-7 bg-background"
              >
                📜 Workshop & Seminar
              </Button>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="email-subject" className="text-xs font-medium">Email Subject</Label>
              <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <span>Insert:</span>
                <button
                  type="button"
                  onClick={() => insertVariable('name', 'subject')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{name}'}
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable('event_name', 'subject')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{event_name}'}
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable('date', 'subject')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{date}'}
                </button>
              </div>
            </div>
            <Input
              id="email-subject"
              value={subjectTemplate}
              onChange={(e) => setSubjectTemplate(e.target.value)}
              required
              className="text-xs"
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="email-body" className="text-xs font-medium">Message Body</Label>
              <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <span>Insert:</span>
                <button
                  type="button"
                  onClick={() => insertVariable('name', 'body')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{name}'}
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable('event_name', 'body')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{event_name}'}
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable('certificate_id', 'body')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{certificate_id}'}
                </button>
                <button
                  type="button"
                  onClick={() => insertVariable('date', 'body')}
                  className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px]"
                >
                  {'{date}'}
                </button>
              </div>
            </div>
            <Textarea
              id="email-body"
              value={bodyTemplate}
              onChange={(e) => setBodyTemplate(e.target.value)}
              rows={5}
              required
              className="text-xs font-mono"
            />
          </div>

          {/* Attachment info */}
          <div className="flex items-center gap-2 p-2.5 rounded-lg bg-muted/30 border text-xs text-muted-foreground">
            <FileCheck className="h-4 w-4 text-emerald-500 shrink-0" />
            <span>Generated certificate PDF will be automatically retrieved from Google Shared Drive and attached to each recipient's email.</span>
          </div>

          {/* Confirmation Checkbox Box */}
          <div
            className={`p-3.5 rounded-lg border transition-all ${
              confirmSend
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-900 dark:text-emerald-100'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-100'
            }`}
          >
            <label htmlFor="confirm-send" className="flex items-start gap-2.5 cursor-pointer">
              <input
                id="confirm-send"
                type="checkbox"
                checked={confirmSend}
                onChange={(e) => {
                  setConfirmSend(e.target.checked)
                  if (feedback && !feedback.success) setFeedback(null)
                }}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <div className="space-y-0.5">
                <span className="text-xs font-semibold block">
                  {confirmSend
                    ? '✓ Authorized — Ready to Dispatch'
                    : 'Step 2: Check Box to Authorize Sending'}
                </span>
                <p className="text-[11px] opacity-85 leading-snug">
                  I explicitly confirm and authorize sending personalized certificate emails to participants in this campaign via my connected Gmail account ({gmailStatus?.google_email || 'connected Gmail'}).
                </p>
              </div>
            </label>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleGeneratePreview}
              disabled={loadingPreview}
              className="gap-1.5 text-xs"
            >
              {loadingPreview ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Eye className="h-3.5 w-3.5" />
              )}
              Preview Email
            </Button>

            <Button
              type="submit"
              variant="gradient"
              size="sm"
              disabled={sending}
              className="gap-1.5 text-xs"
            >
              {sending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Starting Batch Processing...
                </>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  Send Campaign Emails
                </>
              )}
            </Button>
          </div>
        </form>

        {/* Preview Modal / Drawer */}
        <AnimatePresence>
          {showPreviewModal && preview && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="rounded-lg border bg-card p-4 space-y-3 mt-4"
            >
              <div className="flex items-center justify-between pb-2 border-b">
                <span className="text-xs font-semibold text-foreground">Sample Email Preview</span>
                <button
                  onClick={() => setShowPreviewModal(false)}
                  className="text-xs text-muted-foreground hover:text-foreground"
                >
                  Close
                </button>
              </div>
              <div className="space-y-1">
                <span className="text-[11px] text-muted-foreground font-semibold">Subject:</span>
                <p className="text-xs font-medium text-foreground">{preview.rendered_subject}</p>
              </div>
              <div className="space-y-1">
                <span className="text-[11px] text-muted-foreground font-semibold">HTML Body Preview:</span>
                <iframe
                  srcDoc={preview.rendered_html}
                  sandbox=""
                  className="w-full h-48 rounded bg-white dark:bg-zinc-900 border text-xs overflow-y-auto"
                  title="Rendered Email Preview"
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  )
}
