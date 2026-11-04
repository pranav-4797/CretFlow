import { useState, useEffect, useMemo, ChangeEvent, FormEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users,
  UserPlus,
  FileSpreadsheet,
  Search,
  RefreshCw,
  Send,
  RotateCcw,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  X,
  UploadCloud,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { participantService, Participant, ParticipantUploadResponse } from '@/services/participants'

interface ParticipantRosterProps {
  campaignId: string
  campaignName?: string
  onRosterUpdated?: () => void
}

export function ParticipantRoster({
  campaignId,
  campaignName = 'Campaign',
  onRosterUpdated,
}: ParticipantRosterProps) {
  const [participants, setParticipants] = useState<Participant[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'queued' | 'sent' | 'failed' | 'processing'>('all')

  // Modals state
  const [showAddModal, setShowAddModal] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)

  // Single Add form state
  const [newName, setNewName] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [newCertId, setNewCertId] = useState('')
  const [sendImmediately, setSendImmediately] = useState(true)
  const [addingParticipant, setAddingParticipant] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [addSuccess, setAddSuccess] = useState<string | null>(null)

  // Extend Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<ParticipantUploadResponse | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Action status per participant (e.g. sending single email)
  const [actionParticipantId, setActionParticipantId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const fetchParticipants = async () => {
    try {
      setLoading(true)
      const data = await participantService.list(campaignId, statusFilter === 'all' ? undefined : statusFilter)
      setParticipants(Array.isArray(data) ? data : [])
    } catch (err: any) {
      console.error('Failed to load participants:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchParticipants()
  }, [campaignId, statusFilter])

  // Filtered by search query
  const filteredParticipants = useMemo(() => {
    if (!searchQuery.trim()) return participants
    const q = searchQuery.toLowerCase().trim()
    return participants.filter(
      (p) =>
        p.name?.toLowerCase().includes(q) ||
        p.recipient_name?.toLowerCase().includes(q) ||
        p.email?.toLowerCase().includes(q) ||
        p.recipient_email?.toLowerCase().includes(q) ||
        p.certificate_id?.toLowerCase().includes(q)
    )
  }, [participants, searchQuery])

  // Counts summary
  const counts = useMemo(() => {
    const total = participants.length
    const sent = participants.filter((p) => p.email_status === 'sent').length
    const queued = participants.filter((p) => p.email_status === 'queued').length
    const failed = participants.filter((p) => p.email_status === 'failed').length
    const processing = participants.filter((p) => p.email_status === 'processing').length
    return { total, sent, queued, failed, processing }
  }, [participants])

  // Handle single participant addition
  const handleAddSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!newName.trim() || !newEmail.trim()) {
      setAddError('Please enter both name and email address.')
      return
    }

    try {
      setAddingParticipant(true)
      setAddError(null)
      setAddSuccess(null)

      const result = await participantService.add(campaignId, {
        name: newName,
        email: newEmail,
        certificate_id: newCertId || undefined,
        send_immediately: sendImmediately,
      })

      const statusMsg =
        result.email_status === 'sent'
          ? `Added "${newName}" and certificate email was delivered immediately via Gmail!`
          : `Added "${newName}" to campaign queue.`

      setAddSuccess(statusMsg)
      setNewName('')
      setNewEmail('')
      setNewCertId('')

      // Refresh list & counters
      fetchParticipants()
      if (onRosterUpdated) onRosterUpdated()

      setTimeout(() => {
        setShowAddModal(false)
        setAddSuccess(null)
      }, 1800)
    } catch (err: any) {
      setAddError(err.detail || err.message || 'Failed to add participant.')
    } finally {
      setAddingParticipant(false)
    }
  }

  // Handle file selection for upload
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      const lower = file.name.toLowerCase()
      if (!lower.endsWith('.csv') && !lower.endsWith('.xlsx') && !lower.endsWith('.xls')) {
        setUploadError('Only CSV (.csv) or Excel (.xlsx, .xls) files are supported.')
        return
      }
      setUploadError(null)
      setUploadFile(file)
    }
  }

  // Handle spreadsheet extension upload
  const handleUploadSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!uploadFile) {
      setUploadError('Please select a spreadsheet file to upload.')
      return
    }

    try {
      setUploading(true)
      setUploadError(null)
      setUploadResult(null)

      const res = await participantService.upload(campaignId, uploadFile)
      setUploadResult(res)
      setUploadFile(null)

      // Refresh list & counters
      fetchParticipants()
      if (onRosterUpdated) onRosterUpdated()
    } catch (err: any) {
      setUploadError(err.detail || err.message || 'Failed to upload spreadsheet.')
    } finally {
      setUploading(false)
    }
  }

  // Handle single send / resend
  const handleSendSingle = async (participant: Participant, forceResend: boolean = false) => {
    const pId = participant.participant_id || participant.id
    try {
      setActionParticipantId(pId)
      setActionMessage(null)

      const res = await participantService.sendSingle(campaignId, pId, forceResend)
      if (res.success) {
        setActionMessage({
          type: 'success',
          text: `Certificate sent to ${participant.recipient_email || participant.email}!`,
        })
      } else {
        setActionMessage({
          type: 'error',
          text: res.message || 'Send attempt failed. Check error details.',
        })
      }

      fetchParticipants()
      if (onRosterUpdated) onRosterUpdated()
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err.detail || err.message || 'Failed to send certificate.',
      })
    } finally {
      setActionParticipantId(null)
    }
  }

  // Handle delete participant
  const handleDelete = async (participant: Participant) => {
    const pId = participant.participant_id || participant.id
    const pName = participant.recipient_name || participant.name || 'this participant'
    if (!window.confirm(`Are you sure you want to remove "${pName}" from this campaign?`)) {
      return
    }

    try {
      setActionParticipantId(pId)
      await participantService.delete(campaignId, pId)
      fetchParticipants()
      if (onRosterUpdated) onRosterUpdated()
      setActionMessage({
        type: 'success',
        text: `Removed "${pName}" from campaign.`,
      })
    } catch (err: any) {
      setActionMessage({
        type: 'error',
        text: err.detail || err.message || 'Failed to delete participant.',
      })
    } finally {
      setActionParticipantId(null)
    }
  }

  const renderStatusBadge = (status: string, errorMsg?: string) => {
    switch (status) {
      case 'sent':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" />
            Sent
          </span>
        )
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <Loader2 className="h-3 w-3 animate-spin" />
            Sending...
          </span>
        )
      case 'failed':
        return (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20 cursor-help"
            title={errorMsg || 'Failed to send email'}
          >
            <AlertCircle className="h-3 w-3" />
            Failed
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <Clock className="h-3 w-3" />
            Queued
          </span>
        )
    }
  }

  return (
    <Card className="border border-border/80 shadow-sm mt-6">
      <CardHeader className="bg-muted/20 pb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <Users className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base font-semibold">Participant Roster</CardTitle>
                <span className="text-xs px-2 py-0.5 rounded-full bg-muted font-mono font-medium text-muted-foreground">
                  {counts.total} Enrolled
                </span>
              </div>
              <CardDescription className="text-xs">
                Manage recipients, add missing students on the fly, or upload a secondary spreadsheet to extend this campaign.
              </CardDescription>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setAddError(null)
                setAddSuccess(null)
                setShowAddModal(true)
              }}
              className="gap-1.5 text-xs h-8 border-primary/30 text-primary hover:bg-primary/5"
            >
              <UserPlus className="h-3.5 w-3.5" />
              Add Missing Participant
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setUploadError(null)
                setUploadResult(null)
                setShowUploadModal(true)
              }}
              className="gap-1.5 text-xs h-8"
            >
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" />
              Extend Campaign (Upload Excel)
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-4 space-y-4">
        {/* Action toast message */}
        {actionMessage && (
          <div
            className={`p-3 rounded-lg text-xs font-medium flex items-center justify-between ${
              actionMessage.type === 'success'
                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20'
                : 'bg-red-500/10 text-red-700 dark:text-red-300 border border-red-500/20'
            }`}
          >
            <span>{actionMessage.text}</span>
            <button onClick={() => setActionMessage(null)} className="ml-2 font-bold">×</button>
          </div>
        )}

        {/* Search & Filter Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Status Filters */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 text-xs">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === 'all'
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'bg-muted/60 text-muted-foreground hover:bg-muted'
              }`}
            >
              All ({counts.total})
            </button>
            <button
              onClick={() => setStatusFilter('sent')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === 'sent'
                  ? 'bg-emerald-600 text-white shadow-sm'
                  : 'bg-muted/60 text-muted-foreground hover:bg-muted'
              }`}
            >
              Sent ({counts.sent})
            </button>
            <button
              onClick={() => setStatusFilter('queued')}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === 'queued'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-muted/60 text-muted-foreground hover:bg-muted'
              }`}
            >
              Queued ({counts.queued})
            </button>
            {counts.failed > 0 && (
              <button
                onClick={() => setStatusFilter('failed')}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                  statusFilter === 'failed'
                    ? 'bg-red-600 text-white shadow-sm'
                    : 'bg-muted/60 text-muted-foreground hover:bg-muted'
                }`}
              >
                Failed ({counts.failed})
              </button>
            )}
          </div>

          {/* Search Input & Refresh */}
          <div className="flex items-center gap-2">
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search name or email..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 text-xs h-8"
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchParticipants}
              disabled={loading}
              className="h-8 w-8 p-0"
              title="Refresh roster"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* Participants Table */}
        <div className="rounded-lg border overflow-hidden">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-primary" />
              <span className="text-xs">Loading roster...</span>
            </div>
          ) : filteredParticipants.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground space-y-2">
              <Users className="h-8 w-8 mx-auto opacity-30" />
              <p className="text-xs font-medium">No participants found</p>
              <p className="text-[11px] text-muted-foreground max-w-xs mx-auto">
                {searchQuery
                  ? 'No recipients matched your search criteria.'
                  : 'Add missing students or upload a spreadsheet to populate this campaign.'}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[380px] overflow-y-auto">
              <table className="w-full text-xs text-left">
                <thead className="bg-muted/50 sticky top-0 border-b z-10 text-[11px] text-muted-foreground font-semibold uppercase tracking-wider">
                  <tr>
                    <th className="py-2.5 px-3">Recipient</th>
                    <th className="py-2.5 px-3">Certificate ID</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {filteredParticipants.map((p) => {
                    const pId = p.participant_id || p.id
                    const isOperating = actionParticipantId === pId
                    const name = p.recipient_name || p.name || 'Unnamed'
                    const email = p.recipient_email || p.email || ''

                    return (
                      <tr key={pId} className="hover:bg-muted/30 transition-colors">
                        <td className="py-2.5 px-3">
                          <div className="font-semibold text-foreground text-xs">{name}</div>
                          <div className="text-muted-foreground text-[11px] font-mono">{email}</div>
                          {p.last_error_message && (
                            <div className="text-[10px] text-red-600 dark:text-red-400 mt-0.5 max-w-sm truncate" title={p.last_error_message}>
                              Error: {p.last_error_message}
                            </div>
                          )}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="font-mono text-[11px] bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                            {p.certificate_id || `CERT-${pId.substring(2, 10).toUpperCase()}`}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          {renderStatusBadge(p.email_status, p.last_error_message)}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            {p.email_status === 'sent' ? (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleSendSingle(p, true)}
                                disabled={isOperating}
                                className="h-6 px-2 text-[11px] gap-1 text-muted-foreground hover:text-foreground"
                                title="Resend certificate email"
                              >
                                {isOperating ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <RotateCcw className="h-3 w-3" />
                                )}
                                Resend
                              </Button>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleSendSingle(p, false)}
                                disabled={isOperating}
                                className="h-6 px-2 text-[11px] gap-1 text-primary border-primary/30 hover:bg-primary/5"
                                title="Send certificate email immediately"
                              >
                                {isOperating ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  <Send className="h-3 w-3" />
                                )}
                                Send Now
                              </Button>
                            )}

                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(p)}
                              disabled={isOperating}
                              className="h-6 w-6 p-0 text-muted-foreground hover:text-red-600"
                              title="Remove recipient"
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </CardContent>

      {/* Modal 1: Add Missing Participant */}
      <AnimatePresence>
        {showAddModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="bg-card w-full max-w-md rounded-xl border shadow-xl overflow-hidden"
            >
              <div className="p-4 border-b flex items-center justify-between bg-muted/40">
                <div className="flex items-center gap-2">
                  <UserPlus className="h-4 w-4 text-primary" />
                  <h3 className="font-semibold text-sm text-foreground">Add Missing Participant</h3>
                </div>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <form onSubmit={handleAddSubmit} className="p-4 space-y-3.5">
                {addError && (
                  <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-700 dark:text-red-300">
                    {addError}
                  </div>
                )}
                {addSuccess && (
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-700 dark:text-emerald-300">
                    {addSuccess}
                  </div>
                )}

                <p className="text-xs text-muted-foreground">
                  Quickly insert a student who missed the registration form or needs a certificate issued directly into{' '}
                  <span className="font-semibold text-foreground">"{campaignName}"</span>.
                </p>

                <div className="space-y-1">
                  <Label htmlFor="participant-name" className="text-xs font-medium">Student / Recipient Full Name *</Label>
                  <Input
                    id="participant-name"
                    placeholder="e.g. Rahul Sharma"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    required
                    className="text-xs"
                    autoFocus
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="participant-email" className="text-xs font-medium">Email Address *</Label>
                  <Input
                    id="participant-email"
                    type="email"
                    placeholder="e.g. rahul.sharma@example.com"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    required
                    className="text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="participant-certid" className="text-xs font-medium">Certificate ID (Optional)</Label>
                  <Input
                    id="participant-certid"
                    placeholder="Auto-generated if empty (e.g. CERT-2026-001)"
                    value={newCertId}
                    onChange={(e) => setNewCertId(e.target.value)}
                    className="text-xs font-mono"
                  />
                </div>

                {/* Instant Send Checkbox */}
                <div className="p-3 rounded-lg border bg-primary/5 border-primary/20">
                  <label htmlFor="send-immediately-check" className="flex items-start gap-2.5 cursor-pointer">
                    <input
                      id="send-immediately-check"
                      type="checkbox"
                      checked={sendImmediately}
                      onChange={(e) => setSendImmediately(e.target.checked)}
                      className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <div className="space-y-0.5">
                      <span className="text-xs font-semibold text-foreground flex items-center gap-1">
                        <Sparkles className="h-3 w-3 text-primary" />
                        Send Certificate Email Immediately
                      </span>
                      <p className="text-[11px] text-muted-foreground">
                        Generates PDF certificate on the fly and dispatches via connected Gmail account within seconds.
                      </p>
                    </div>
                  </label>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAddModal(false)}
                    disabled={addingParticipant}
                    className="text-xs"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="gradient"
                    size="sm"
                    disabled={addingParticipant}
                    className="text-xs gap-1.5"
                  >
                    {addingParticipant ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        {sendImmediately ? 'Generating & Sending...' : 'Adding...'}
                      </>
                    ) : (
                      <>
                        {sendImmediately ? <Send className="h-3.5 w-3.5" /> : <UserPlus className="h-3.5 w-3.5" />}
                        {sendImmediately ? 'Add & Send Certificate Now' : 'Add to Queue'}
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal 2: Extend Campaign via Excel / CSV */}
      <AnimatePresence>
        {showUploadModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="bg-card w-full max-w-lg rounded-xl border shadow-xl overflow-hidden"
            >
              <div className="p-4 border-b flex items-center justify-between bg-muted/40">
                <div className="flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
                  <h3 className="font-semibold text-sm text-foreground">Extend Campaign Roster</h3>
                </div>
                <button
                  onClick={() => setShowUploadModal(false)}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <form onSubmit={handleUploadSubmit} className="p-4 space-y-4">
                {uploadError && (
                  <div className="p-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-700 dark:text-red-300">
                    {uploadError}
                  </div>
                )}

                {uploadResult && (
                  <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs space-y-1 text-emerald-800 dark:text-emerald-300">
                    <p className="font-semibold flex items-center gap-1.5">
                      <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                      Roster Successfully Extended!
                    </p>
                    <p>{uploadResult.message}</p>
                    <div className="flex items-center gap-3 pt-1 text-[11px] font-mono text-emerald-700 dark:text-emerald-400">
                      <span>Imported: <strong>{uploadResult.imported_count}</strong></span>
                      <span>Duplicates Skipped: <strong>{uploadResult.duplicates_skipped}</strong></span>
                      <span>Total Enrolled: <strong>{uploadResult.total_recipients}</strong></span>
                    </div>
                  </div>
                )}

                <div className="p-3 rounded-lg bg-muted/40 border border-border/80 text-xs text-muted-foreground space-y-1.5">
                  <div className="flex items-center gap-1.5 font-semibold text-foreground">
                    <ShieldCheck className="h-4 w-4 text-emerald-500" />
                    Automatic Deduplication Guaranteed
                  </div>
                  <p>
                    You can upload an updated full sheet or an append-only sheet. CertFlow automatically compares every email against existing recipients. Any participant who already received a certificate will <strong>not</strong> be duplicated or resent by mistake.
                  </p>
                </div>

                {/* File Picker */}
                <div className="border-2 border-dashed border-border rounded-xl p-6 text-center hover:bg-muted/20 transition-colors">
                  <input
                    type="file"
                    id="extend-file-input"
                    accept=".csv, .xlsx, .xls"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <label htmlFor="extend-file-input" className="cursor-pointer space-y-2 block">
                    <div className="h-10 w-10 mx-auto rounded-full bg-primary/10 flex items-center justify-center text-primary">
                      <UploadCloud className="h-5 w-5" />
                    </div>
                    {uploadFile ? (
                      <div>
                        <p className="text-xs font-semibold text-foreground">{uploadFile.name}</p>
                        <p className="text-[11px] text-muted-foreground">{(uploadFile.size / 1024).toFixed(1)} KB — Click to change</p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-xs font-semibold text-foreground">Click to select CSV or Excel file</p>
                        <p className="text-[11px] text-muted-foreground">Supported formats: .xlsx, .xls, .csv (Max 10MB)</p>
                      </div>
                    )}
                  </label>
                </div>

                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>Required column: <code>email</code> or <code>recipient_email</code></span>
                  <span>Optional column: <code>name</code></span>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2 border-t">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowUploadModal(false)}
                    disabled={uploading}
                    className="text-xs"
                  >
                    {uploadResult ? 'Done' : 'Cancel'}
                  </Button>
                  <Button
                    type="submit"
                    variant="gradient"
                    size="sm"
                    disabled={uploading || !uploadFile}
                    className="text-xs gap-1.5"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Importing & Deduplicating...
                      </>
                    ) : (
                      <>
                        <UploadCloud className="h-3.5 w-3.5" />
                        Import & Extend Campaign
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </Card>
  )
}
