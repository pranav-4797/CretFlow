import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  FolderPlus,
  UploadCloud,
  FileSpreadsheet,
  ClipboardCheck,
  CheckCircle2,
  AlertCircle,
  Mail,
  Loader2,
  Sparkles,
  Check,
  Sliders,
  Percent,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { api } from '@/services/api'
import { toast } from '@/hooks/use-toast'

interface CampaignResponse {
  id: string
  campaign_id: string
  name: string
  campaign_name: string
  campaign_type?: string
}

export default function CreateCampaignPage() {
  const navigate = useNavigate()

  // Step 1: Campaign Type
  const [campaignType, setCampaignType] = useState<'spreadsheet' | 'google_forms'>('spreadsheet')

  // Step 2: Basic Details
  const [campaignName, setCampaignName] = useState('')
  const [description, setDescription] = useState('')

  // Step 3 (Spreadsheet): Email Dispatch & File
  const [subjectTemplate, setSubjectTemplate] = useState('Your Certificate of Completion: {{name}}')
  const [bodyTemplate, setBodyTemplate] = useState(
    'Hi {{name}},\n\nCongratulations on completing the event! Please find your certificate attached.\n\nBest regards,\nCertFlow Team'
  )
  const [file, setFile] = useState<File | null>(null)

  // Step 3 (Google Forms): Quiz / Form Webhook Settings
  const [passingScore, setPassingScore] = useState<number>(60)
  const [showScoreInEmail, setShowScoreInEmail] = useState<boolean>(true)
  const [quizSubjectTemplate, setQuizSubjectTemplate] = useState(
    'Congratulations {{name}}! Here is your Certificate for {{event_name}}'
  )
  const [quizBodyTemplate, setQuizBodyTemplate] = useState(
    'Dear {{name}},\n\nCongratulations on passing the {{event_name}} assessment!\n\nScore: {{score}} / {{total_score}} ({{percentage}}%)\n\nYour verified Certificate of Achievement has been issued and is attached to this email. You can verify its authenticity using Certificate ID: {{certificate_id}}.\n\nBest regards,\nCertFlow Team'
  )

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0]
      const lower = selected.name.toLowerCase()
      if (!lower.endsWith('.csv') && !lower.endsWith('.xlsx') && !lower.endsWith('.xls')) {
        setError('Only .csv, .xlsx, or .xls files are supported.')
        return
      }
      if (selected.size > 10 * 1024 * 1024) {
        setError('File size exceeds maximum limit of 10MB.')
        return
      }
      setError(null)
      setFile(selected)
    }
  }

  const insertVariable = (varName: string, target: 'spreadsheet_body' | 'quiz_body') => {
    const token = `{{${varName}}}`
    if (target === 'spreadsheet_body') {
      setBodyTemplate((prev) => `${prev} ${token}`)
    } else {
      setQuizBodyTemplate((prev) => `${prev} ${token}`)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!campaignName.trim()) {
      setError('Please provide a campaign name.')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      // 1. Create the Campaign in Firestore with campaign_type
      const campaignPayload = {
        name: campaignName.trim(),
        campaign_name: campaignName.trim(),
        description: description.trim() || undefined,
        campaign_type: campaignType,
        subject_template: campaignType === 'spreadsheet' ? subjectTemplate.trim() : quizSubjectTemplate.trim(),
        body_template: campaignType === 'spreadsheet' ? bodyTemplate.trim() : quizBodyTemplate.trim(),
      }

      const created = await api.post<CampaignResponse>('/api/campaigns', campaignPayload)
      const campaignId = created.id || created.campaign_id

      if (campaignType === 'spreadsheet') {
        // 2a. Upload Participant Spreadsheet if provided
        if (file && campaignId) {
          const formData = new FormData()
          formData.append('file', file)
          await api.upload(`/api/participants/${campaignId}/upload`, formData)
        }

        toast.success(
          'Campaign created successfully!',
          file
            ? `Created spreadsheet campaign "${campaignName}" and imported roster.`
            : `Created spreadsheet campaign "${campaignName}". Ready to design templates!`
        )

        // Navigate to Certificate Studio to design certificate for this campaign
        navigate(`/campaigns?tab=certificate_studio&id=${campaignId}`, { replace: true })
      } else {
        // 2b. Initialize Webhook Configuration for Google Forms Quiz
        try {
          await api.post(`/api/webhooks/config/${campaignId}`, {
            passing_score: Number(passingScore) || 60,
            auto_email: true,
            quiz_email_subject: quizSubjectTemplate.trim(),
            quiz_email_body: quizBodyTemplate.trim(),
            show_score_in_email: showScoreInEmail,
          })
        } catch (webhookErr) {
          console.warn('Could not save initial webhook config:', webhookErr)
        }

        toast.success(
          'Google Forms Campaign created!',
          `Ready to connect your Google Form and auto-issue certificates upon submission.`
        )

        // Navigate directly to Google Forms Integration tab with Apps Script ready to copy
        navigate(`/campaigns?tab=google_forms&id=${campaignId}`, { replace: true })
      }
    } catch (err: any) {
      console.error('Failed to create campaign:', err)
      setError(err.detail || err.message || 'Failed to create campaign. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="page-container py-8 max-w-4xl">
      {/* Header with back button */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link
            to="/campaigns"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors mb-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Campaigns
          </Link>
          <h1 className="section-title flex items-center gap-2.5">
            <FolderPlus className="h-6 w-6 text-primary" />
            Create New Campaign
          </h1>
          <p className="section-description">
            Choose your workflow, configure delivery rules, and start issuing verified certificates.
          </p>
        </div>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-3"
        >
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
        </motion.div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Step 1: Visual Campaign Type Selector */}
        <Card className="border-2 shadow-xs">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              1. Choose Campaign Type
            </CardTitle>
            <CardDescription>
              Select how participants will be added and how certificates will be triggered.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Type Card A: Spreadsheet */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => setCampaignType('spreadsheet')}
                className={`relative p-5 rounded-xl border-2 cursor-pointer transition-all text-left flex flex-col justify-between ${
                  campaignType === 'spreadsheet'
                    ? 'border-primary bg-primary/5 ring-2 ring-primary/20 shadow-xs'
                    : 'border-border hover:border-muted-foreground/30 hover:bg-muted/30'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                    <FileSpreadsheet className="h-6 w-6" />
                  </div>
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950/80 dark:text-blue-300">
                    Batch Delivery
                  </span>
                </div>
                <div>
                  <h3 className="text-sm font-semibold flex items-center gap-1.5 mb-1">
                    Spreadsheet / Bulk Roster
                    {campaignType === 'spreadsheet' && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Upload a CSV/Excel participant roster. Best for webinars, conferences, workshops, and graduations with a known attendee list.
                  </p>
                </div>
              </div>

              {/* Type Card B: Google Form / Quiz Automation */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => setCampaignType('google_forms')}
                className={`relative p-5 rounded-xl border-2 cursor-pointer transition-all text-left flex flex-col justify-between ${
                  campaignType === 'google_forms'
                    ? 'border-indigo-500 bg-indigo-500/5 ring-2 ring-indigo-500/20 shadow-xs'
                    : 'border-border hover:border-muted-foreground/30 hover:bg-muted/30'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="p-2.5 rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                    <ClipboardCheck className="h-6 w-6" />
                  </div>
                  <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300">
                    Real-time Webhook
                  </span>
                </div>
                <div>
                  <h3 className="text-sm font-semibold flex items-center gap-1.5 mb-1 text-foreground">
                    Google Form / Quiz Automation
                    {campaignType === 'google_forms' && (
                      <Check className="h-4 w-4 text-indigo-600" />
                    )}
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Auto-issue certificates on form submit. Evaluates quiz score threshold and automatically emails certificates to passing respondents.
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Step 2: Campaign Details */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FolderPlus className="h-4 w-4 text-primary" />
              2. Campaign Name & Description
            </CardTitle>
            <CardDescription>
              Identify your campaign to organize participant certificates, logs, and analytics.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="campaignName">
                Campaign Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="campaignName"
                placeholder={
                  campaignType === 'spreadsheet'
                    ? 'e.g. Annual Tech Summit 2026 Certificates'
                    : 'e.g. Python Certification Exam — Google Form'
                }
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
                required
                maxLength={150}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description (Optional)</Label>
              <Textarea
                id="description"
                placeholder="Internal notes or event details..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                maxLength={500}
              />
            </div>
          </CardContent>
        </Card>

        {/* Step 3: Adaptive Configuration */}
        {campaignType === 'spreadsheet' ? (
          <>
            {/* Spreadsheet: Email Dispatch Template */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Mail className="h-4 w-4 text-primary" />
                  3. Email Dispatch Template
                </CardTitle>
                <CardDescription>
                  Configure the email message sent with the attached certificate PDF.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="subjectTemplate">Email Subject</Label>
                  <Input
                    id="subjectTemplate"
                    value={subjectTemplate}
                    onChange={(e) => setSubjectTemplate(e.target.value)}
                    placeholder="e.g. Your Certificate of Completion for {{name}}"
                    maxLength={200}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="bodyTemplate">Email Body Message</Label>
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span>Insert variable:</span>
                      <button
                        type="button"
                        onClick={() => insertVariable('name', 'spreadsheet_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[11px] font-mono"
                      >
                        {'{name}'}
                      </button>
                      <button
                        type="button"
                        onClick={() => insertVariable('event_name', 'spreadsheet_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[11px] font-mono"
                      >
                        {'{event_name}'}
                      </button>
                      <button
                        type="button"
                        onClick={() => insertVariable('certificate_id', 'spreadsheet_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[11px] font-mono"
                      >
                        {'{certificate_id}'}
                      </button>
                    </div>
                  </div>
                  <Textarea
                    id="bodyTemplate"
                    value={bodyTemplate}
                    onChange={(e) => setBodyTemplate(e.target.value)}
                    rows={4}
                    maxLength={3000}
                    required
                  />
                </div>
              </CardContent>
            </Card>

            {/* Spreadsheet: Upload Roster */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4 text-primary" />
                  4. Participant Spreadsheet Roster (Optional)
                </CardTitle>
                <CardDescription>
                  Upload your participant roster (.csv, .xlsx, or .xls). You can also upload or add participants later.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 text-center hover:bg-muted/30 transition-colors">
                  <UploadCloud className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-sm font-medium mb-1">
                    {file ? file.name : 'Choose a CSV or Excel spreadsheet'}
                  </p>
                  <p className="text-xs text-muted-foreground mb-4">
                    {file
                      ? `${(file.size / 1024).toFixed(1)} KB — ready to import`
                      : 'Supported formats: .csv, .xlsx, .xls (up to 10MB)'}
                  </p>

                  <label htmlFor="file-upload" className="cursor-pointer">
                    <Button type="button" variant="outline" size="sm" asChild>
                      <span>Select File</span>
                    </Button>
                    <input
                      id="file-upload"
                      type="file"
                      accept=".csv,.xlsx,.xls"
                      className="sr-only"
                      onChange={handleFileChange}
                    />
                  </label>

                  {file && (
                    <div className="mt-3 flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                      <CheckCircle2 className="h-4 w-4" />
                      File selected. It will be imported automatically when the campaign is created.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            {/* Google Forms: Quiz Rules & Passing Score */}
            <Card className="border-indigo-200/50 dark:border-indigo-900/50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2 text-indigo-700 dark:text-indigo-400">
                  <Sliders className="h-4 w-4" />
                  3. Quiz Evaluation & Passing Threshold
                </CardTitle>
                <CardDescription>
                  Define the passing percentage required for respondents to automatically receive a certificate.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="passingScore" className="flex items-center gap-1.5 text-xs font-semibold">
                      <Percent className="h-3.5 w-3.5 text-indigo-600" />
                      Passing Score Threshold (%)
                    </Label>
                    <div className="flex items-center gap-3">
                      <Input
                        id="passingScore"
                        type="number"
                        min={0}
                        max={100}
                        value={passingScore}
                        onChange={(e) => setPassingScore(Number(e.target.value) || 0)}
                        className="w-28 font-mono text-base"
                      />
                      <span className="text-xs text-muted-foreground">
                        Participants scoring &ge; {passingScore}% receive a certificate.
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/20">
                    <div className="space-y-0.5">
                      <Label htmlFor="scoreToggle" className="text-xs font-semibold cursor-pointer">
                        Display Score in Email
                      </Label>
                      <p className="text-[11px] text-muted-foreground">
                        Mention score (e.g. 85/100) in recipient notification.
                      </p>
                    </div>
                    <input
                      id="scoreToggle"
                      type="checkbox"
                      checked={showScoreInEmail}
                      onChange={(e) => setShowScoreInEmail(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                    />
                  </div>
                </div>

                <div className="p-3.5 rounded-lg bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200/60 dark:border-indigo-900/40 text-xs text-indigo-900 dark:text-indigo-200 flex items-start gap-2.5">
                  <Sparkles className="h-4 w-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-semibold">Automatic Google Apps Script Generation:</span>
                    <p className="mt-0.5 text-indigo-800/80 dark:text-indigo-300/80 leading-relaxed">
                      After creating this campaign, you will be directed to the Google Forms setup tab with a customized Google Apps Script snippet ready to copy directly into your Google Form in 1 click!
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Google Forms: Quiz Email Template */}
            <Card className="border-indigo-200/50 dark:border-indigo-900/50">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2 text-indigo-700 dark:text-indigo-400">
                  <Mail className="h-4 w-4" />
                  4. Automated Quiz Congratulation Email
                </CardTitle>
                <CardDescription>
                  This email is dispatched automatically via your connected Gmail the moment a student passes your quiz.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="quizSubjectTemplate">Email Subject</Label>
                  <Input
                    id="quizSubjectTemplate"
                    value={quizSubjectTemplate}
                    onChange={(e) => setQuizSubjectTemplate(e.target.value)}
                    placeholder="Congratulations {{name}}! Here is your Certificate"
                    maxLength={200}
                    required
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="quizBodyTemplate">Email Message</Label>
                    <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                      <span>Insert:</span>
                      <button
                        type="button"
                        onClick={() => insertVariable('name', 'quiz_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px] font-mono"
                      >
                        {'{name}'}
                      </button>
                      <button
                        type="button"
                        onClick={() => insertVariable('score', 'quiz_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px] font-mono"
                      >
                        {'{score}'}
                      </button>
                      <button
                        type="button"
                        onClick={() => insertVariable('total_score', 'quiz_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px] font-mono"
                      >
                        {'{total_score}'}
                      </button>
                      <button
                        type="button"
                        onClick={() => insertVariable('percentage', 'quiz_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px] font-mono"
                      >
                        {'{percentage}'}
                      </button>
                      <button
                        type="button"
                        onClick={() => insertVariable('certificate_id', 'quiz_body')}
                        className="px-1.5 py-0.5 rounded bg-muted hover:bg-muted/80 text-[10px] font-mono"
                      >
                        {'{certificate_id}'}
                      </button>
                    </div>
                  </div>
                  <Textarea
                    id="quizBodyTemplate"
                    value={quizBodyTemplate}
                    onChange={(e) => setQuizBodyTemplate(e.target.value)}
                    rows={5}
                    maxLength={3000}
                    required
                  />
                </div>
              </CardContent>
            </Card>
          </>
        )}

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Link to="/campaigns">
            <Button type="button" variant="ghost">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            variant={campaignType === 'google_forms' ? 'default' : 'gradient'}
            disabled={isSubmitting}
            className={`min-w-44 gap-2 ${
              campaignType === 'google_forms'
                ? 'bg-indigo-600 hover:bg-indigo-700 text-white'
                : ''
            }`}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating Campaign...
              </>
            ) : campaignType === 'google_forms' ? (
              <>
                <ClipboardCheck className="h-4 w-4" />
                Create Form Campaign
              </>
            ) : (
              <>
                <FolderPlus className="h-4 w-4" />
                Create Spreadsheet Campaign
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
