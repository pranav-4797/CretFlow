import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AlertTriangle,
  Trash2,
  X,
  ArrowRight,
  ArrowLeft,
  Users,
  Award,
  ShieldAlert,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { api } from '@/services/api'
import { useToast } from '@/hooks/use-toast'

export interface CampaignToDelete {
  id?: string
  campaign_id?: string
  name?: string
  campaign_name?: string
  total_recipients?: number
  sent_count?: number
}

interface DeleteCampaignDialogProps {
  campaign: CampaignToDelete | null
  isOpen: boolean
  onClose: () => void
  onDeleted: (campaignId: string) => void
}

export function DeleteCampaignDialog({
  campaign,
  isOpen,
  onClose,
  onDeleted,
}: DeleteCampaignDialogProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [confirmInput, setConfirmInput] = useState('')
  const [isDeleting, setIsDeleting] = useState(false)
  const { toast } = useToast()

  if (!isOpen || !campaign) return null

  const campaignId = campaign.id || campaign.campaign_id || ''
  const campaignName = campaign.name || campaign.campaign_name || 'Untitled Campaign'
  const totalRecipients = campaign.total_recipients || 0
  const sentCount = campaign.sent_count || 0

  const handleClose = () => {
    if (isDeleting) return
    setStep(1)
    setConfirmInput('')
    onClose()
  }

  const normalizedInput = confirmInput.trim().toLowerCase()
  const isMatch =
    normalizedInput === 'delete' ||
    normalizedInput === campaignName.trim().toLowerCase()

  const handleDelete = async () => {
    if (!isMatch || isDeleting || !campaignId) return

    try {
      setIsDeleting(true)
      await api.delete(`/api/campaigns/${campaignId}`)

      toast({
        title: 'Campaign Deleted',
        description: `"${campaignName}" was permanently removed.`,
      })

      onDeleted(campaignId)
      handleClose()
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : 'Failed to delete campaign.'
      toast({
        variant: 'destructive',
        title: 'Deletion Failed',
        description: errorMsg,
      })
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm"
        />

        {/* Modal Dialog */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 10 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.18 }}
          className="relative w-full max-w-md bg-background border border-border rounded-2xl shadow-2xl overflow-hidden z-10"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-5 border-b border-border/60 bg-muted/20">
            <div className="flex items-center gap-2.5">
              <div
                className={`p-2 rounded-xl ${
                  step === 1
                    ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
                    : 'bg-destructive/10 text-destructive border border-destructive/20'
                }`}
              >
                {step === 1 ? (
                  <AlertTriangle className="h-5 w-5" />
                ) : (
                  <Trash2 className="h-5 w-5" />
                )}
              </div>
              <div>
                <h3 className="text-base font-semibold text-foreground">
                  {step === 1 ? 'Delete Campaign?' : 'Final Confirmation'}
                </h3>
                <span className="text-xs font-medium text-muted-foreground">
                  Step {step} of 2 verification
                </span>
              </div>
            </div>

            <button
              onClick={handleClose}
              disabled={isDeleting}
              className="rounded-lg p-1 text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {/* Body Content */}
          <div className="p-5 space-y-4">
            {step === 1 ? (
              // Step 1: Initial Warning & Summary
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Are you sure you want to delete{' '}
                  <strong className="text-foreground font-semibold">
                    "{campaignName}"
                  </strong>
                  ?
                </p>

                {/* Campaign Summary card */}
                <div className="p-3.5 rounded-xl bg-muted/40 border border-border/60 space-y-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 text-primary" /> Registered
                      Participants:
                    </span>
                    <span className="font-semibold text-foreground">
                      {totalRecipients}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Award className="h-3.5 w-3.5 text-emerald-500" /> Certificates
                      Sent:
                    </span>
                    <span className="font-semibold text-foreground">
                      {sentCount}
                    </span>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-700 dark:text-amber-300">
                  Deleting this campaign will detach all participant records and
                  stop active distribution tasks.
                </div>
              </div>
            ) : (
              // Step 2: Irreversible Warning & Name/DELETE confirmation
              <div className="space-y-4">
                <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 flex items-start gap-2.5">
                  <ShieldAlert className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <div className="text-xs text-destructive space-y-1">
                    <p className="font-semibold">This action cannot be undone.</p>
                    <p className="leading-relaxed">
                      All participant scores, certificates, and email tracking
                      logs will be permanently deleted from the database.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-foreground mb-1.5">
                    Type{' '}
                    <span className="font-bold underline text-destructive">
                      DELETE
                    </span>{' '}
                    or{' '}
                    <span className="font-bold text-foreground">
                      "{campaignName}"
                    </span>{' '}
                    to confirm:
                  </label>
                  <Input
                    autoFocus
                    placeholder={`Type DELETE or ${campaignName}`}
                    value={confirmInput}
                    onChange={(e) => setConfirmInput(e.target.value)}
                    className="h-9 text-xs"
                    disabled={isDeleting}
                  />
                  {confirmInput.length > 0 && !isMatch && (
                    <p className="text-[11px] text-destructive mt-1">
                      Text does not match. Please verify.
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Footer Controls */}
          <div className="flex items-center justify-end gap-2 p-4 border-t border-border/60 bg-muted/10">
            {step === 1 ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClose}
                  className="text-xs"
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => setStep(2)}
                  className="text-xs gap-1.5"
                >
                  Next: Confirm Deletion
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setStep(1)}
                  disabled={isDeleting}
                  className="text-xs gap-1.5"
                >
                  <ArrowLeft className="h-3.5 w-3.5" />
                  Back
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleDelete}
                  disabled={!isMatch || isDeleting}
                  loading={isDeleting}
                  className="text-xs gap-1.5 shadow-sm"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Permanently Delete
                </Button>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  )
}
