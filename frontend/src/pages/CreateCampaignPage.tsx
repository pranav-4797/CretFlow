import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ArrowLeft,
  FolderPlus,
  UploadCloud,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Mail,
  Loader2,
  Sparkles,
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
}

export default function CreateCampaignPage() {
  const navigate = useNavigate()

  const [campaignName, setCampaignName] = useState('')
  const [description, setDescription] = useState('')
  const [subjectTemplate, setSubjectTemplate] = useState('Your Certificate of Completion: {{name}}')
  const [bodyTemplate, setBodyTemplate] = useState(
    'Hi {{name}},\n\nCongratulations on completing the event! Please find your certificate attached.\n\nBest regards,\nCertFlow Team'
  )

  const [file, setFile] = useState<File | null>(null)
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

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!campaignName.trim()) {
      setError('Please provide a campaign name.')
      return
    }

    setIsSubmitting(true)
    setError(null)

    try {
      // 1. Create the Campaign in Firestore
      const campaignPayload = {
        name: campaignName.trim(),
        campaign_name: campaignName.trim(),
        description: description.trim() || undefined,
        subject_template: subjectTemplate.trim(),
        body_template: bodyTemplate.trim(),
      }

      const created = await api.post<CampaignResponse>('/api/campaigns', campaignPayload)
      const campaignId = created.id || created.campaign_id

      // 2. Upload Participant Spreadsheet if provided
      if (file && campaignId) {
        const formData = new FormData()
        formData.append('file', file)
        await api.upload(`/api/participants/${campaignId}/upload`, formData)
      }

      toast.success(
        'Campaign created successfully!',
        file
          ? `Created "${campaignName}" and imported participant spreadsheet.`
          : `Created campaign "${campaignName}".`
      )

      navigate('/campaigns', { replace: true })
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
            Set up your certificate distribution campaign, email templates, and recipients.
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
        {/* Card 1: Basic Campaign Info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              1. Campaign Details
            </CardTitle>
            <CardDescription>
              Name your campaign to organize participant certificates and reports.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="campaignName">
                Campaign Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="campaignName"
                placeholder="e.g. Annual Tech Summit 2026 Certificates"
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
                placeholder="Internal notes or event description..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                maxLength={500}
              />
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Email Templates */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Mail className="h-4 w-4 text-primary" />
              2. Email Dispatch Template
            </CardTitle>
            <CardDescription>
              Customize the email subject and body sent with attached certificate PDFs. Use variables like{' '}
              <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{'{{name}}'}</code>.
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
              <Label htmlFor="bodyTemplate">Email Body Message</Label>
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

        {/* Card 3: Participant Spreadsheet Upload */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4 text-primary" />
              3. Recipients & Spreadsheet Upload (Optional)
            </CardTitle>
            <CardDescription>
              Upload your participant roster (.csv, .xlsx, or .xls). Must contain a column with recipient emails.
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

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <Link to="/campaigns">
            <Button type="button" variant="ghost">
              Cancel
            </Button>
          </Link>
          <Button type="submit" variant="gradient" disabled={isSubmitting} className="min-w-36 gap-2">
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <FolderPlus className="h-4 w-4" />
                Create Campaign
              </>
            )}
          </Button>
        </div>
      </form>
    </div>
  )
}
