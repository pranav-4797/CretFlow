import React, { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Award,
  Upload,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Eye,
  Send,
  FileCheck,
  Download,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  templateService,
  TemplateConfig,
  TemplateResponse,
} from '@/services/templates'
import { CanvaCertificateEditor } from './CanvaCertificateEditor'
import { api } from '@/services/api'

interface CertificateStudioProps {
  campaignId: string
  campaignName: string
  onSwitchToEmail?: () => void
}

export function CertificateStudio({ campaignId, campaignName, onSwitchToEmail }: CertificateStudioProps) {
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)

  const [templateData, setTemplateData] = useState<TemplateResponse | null>(null)
  const [availableVariables, setAvailableVariables] = useState<string[]>([])
  const [activeViewMode, setActiveViewMode] = useState<'canva_editor' | 'rendered_proof'>('canva_editor')

  const [config, setConfig] = useState<TemplateConfig>({
    font_family: 'PlayfairDisplay',
    font_size: 64,
    font_color: '#1e293b',
    name_x_percent: 50.0,
    name_y_percent: 48.0,
    text_align: 'center',
    show_cert_id: true,
    cert_id_x_percent: 88.0,
    cert_id_y_percent: 92.0,
    show_date: false,
    date_x_percent: 15.0,
    date_y_percent: 92.0,
    fields: [],
  })

  const sampleName = 'Rahul Sharma'
  const [livePreviewUrl, setLivePreviewUrl] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ success: boolean; message: string } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load existing template data & campaign variables
  const loadTemplate = async () => {
    if (!campaignId || campaignId === 'default_campaign') {
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      const [res, campRes] = await Promise.all([
        templateService.getTemplate(campaignId),
        api.get<any>(`/api/campaigns/${campaignId}`).catch(() => null),
      ])

      setTemplateData(res)
      if (campRes && Array.isArray(campRes.available_variables)) {
        setAvailableVariables(campRes.available_variables)
      }

      if (res.config) {
        setConfig((prev) => ({ ...prev, ...res.config }))
      }

      if (res.has_template) {
        if (res.template_image_url) {
          setLivePreviewUrl(res.template_image_url)
        }
      } else {
        setLivePreviewUrl(null)
      }
    } catch (err: any) {
      console.warn('No existing template loaded:', err)
      setTemplateData(null)
      setLivePreviewUrl(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTemplate()
  }, [campaignId])

  // Handle template file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      setFeedback(null)
      const formData = new FormData()
      formData.append('file', file)
      const res = await templateService.uploadTemplate(campaignId, formData)
      setTemplateData({
        campaign_id: campaignId,
        has_template: true,
        template_image_url: res.template_image_url,
        template_drive_file_id: res.template_drive_file_id,
        config: res.config,
      })
      if (res.template_image_url) {
        setLivePreviewUrl(res.template_image_url)
      }
      setFeedback({ success: true, message: 'Certificate background template uploaded successfully!' })
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to upload certificate template.' })
    } finally {
      setUploading(false)
    }
  }

  const [downloadingPdf, setDownloadingPdf] = useState(false)

  // Handle generating backend live preview (proof mode)
  const handleGenerateProof = async (overrideConfig?: TemplateConfig) => {
    const activeConfig = overrideConfig || config
    try {
      setPreviewLoading(true)
      // Auto-save active configuration to Firestore so edits are never lost
      await templateService.saveConfig(campaignId, activeConfig).catch((err) => {
        console.warn('Could not auto-save config before generating proof:', err)
      })

      const res = await templateService.previewTemplate(
        campaignId,
        sampleName,
        activeConfig,
        {
          college: 'MIT Academy of Engineering',
          rank: '1st Prize Winner',
          event_name: campaignName,
        }
      )
      setLivePreviewUrl(res.preview_data_url)
      setActiveViewMode('rendered_proof')
    } catch (err: any) {
      console.error('Failed to generate live proof preview:', err)
      setFeedback({ success: false, message: 'Could not generate preview proof.' })
    } finally {
      setPreviewLoading(false)
    }
  }

  // Handle downloading actual sample PDF proof
  const handleDownloadProofPdf = async () => {
    try {
      setDownloadingPdf(true)
      const blob = await templateService.downloadSamplePdf(
        campaignId,
        sampleName,
        config,
        {
          college: 'MIT Academy of Engineering',
          rank: '1st Prize Winner',
          event_name: campaignName,
        }
      )
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `certificate_proof_${campaignName.toLowerCase().replace(/[^a-z0-9]/g, '_')}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error('Failed to download proof PDF:', err)
      setFeedback({ success: false, message: 'Could not download certificate PDF.' })
    } finally {
      setDownloadingPdf(false)
    }
  }

  // Save config
  const handleSaveConfig = async () => {
    try {
      setSavingConfig(true)
      await templateService.saveConfig(campaignId, config)
      setFeedback({ success: true, message: 'Canva design configuration saved successfully!' })
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to save configuration.' })
    } finally {
      setSavingConfig(false)
    }
  };

  // Bulk generate certificates in Google Drive
  const handleGenerateAll = async () => {
    try {
      setGenerating(true)
      setFeedback(null)
      await templateService.saveConfig(campaignId, config)
      const res = await templateService.generateCertificates(campaignId, true)
      setFeedback({
        success: true,
        message: `Generated ${res.generated_count} personalized certificate PDFs in Google Shared Drive!`,
      })
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to generate certificates.' })
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-3">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <p className="text-xs text-muted-foreground">Loading Certificate Studio...</p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {/* Feedback banner */}
      {feedback && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className={`p-3.5 rounded-lg border text-xs flex items-center justify-between gap-2 ${
            feedback.success
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-600 dark:text-emerald-400'
              : 'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400'
          }`}
        >
          <div className="flex items-center gap-2">
            {feedback.success ? <CheckCircle2 className="h-4 w-4 shrink-0" /> : <AlertCircle className="h-4 w-4 shrink-0" />}
            <span>{feedback.message}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="text-muted-foreground hover:text-foreground text-xs font-semibold">✕</button>
        </motion.div>
      )}

      {/* Studio Header Card */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="py-3 px-4 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Award className="h-4 w-4 text-primary" />
              Certificate Studio — {campaignName}
            </CardTitle>
            <CardDescription className="text-[11px]">
              Drag and drop text elements visually like Canva to design certificates with dynamic attendee details.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* View Mode Switcher */}
            {templateData?.has_template && (
              <div className="flex items-center border rounded-lg p-0.5 bg-muted/40 text-xs">
                <button
                  type="button"
                  onClick={() => setActiveViewMode('canva_editor')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors ${
                    activeViewMode === 'canva_editor'
                      ? 'bg-primary text-primary-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Canva Visual Editor
                </button>
                <button
                  type="button"
                  onClick={() => handleGenerateProof()}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors flex items-center gap-1 ${
                    activeViewMode === 'rendered_proof'
                      ? 'bg-primary text-primary-foreground shadow-xs'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {previewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Eye className="h-3 w-3" />}
                  Final PDF Proof
                </button>
              </div>
            )}

            {templateData?.has_template && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleGenerateAll}
                disabled={generating}
                className="gap-1.5 text-xs h-7"
                title="Bulk generate all participant certificates in Google Drive"
              >
                {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Award className="h-3 w-3 text-primary" />}
                Generate in Drive
              </Button>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="gap-1.5 text-xs h-7"
            >
              {uploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
              {templateData?.has_template ? 'Change Background' : 'Upload Template'}
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/jpg"
              className="hidden"
              onChange={handleFileUpload}
            />

            {onSwitchToEmail && (
              <Button
                onClick={onSwitchToEmail}
                variant="ghost"
                size="sm"
                className="gap-1.5 text-xs h-7 text-primary"
              >
                <Send className="h-3 w-3" />
                Go to Distribution →
              </Button>
            )}
          </div>
        </CardHeader>

        <CardContent className="p-4">
          {templateData?.has_template ? (
            activeViewMode === 'canva_editor' ? (
              /* Canva Visual Drag-and-Drop Workspace */
              <CanvaCertificateEditor
                templateImageUrl={templateData.template_image_url || livePreviewUrl || ''}
                config={config}
                availableVariables={availableVariables}
                sampleData={{
                  name: sampleName,
                  college: 'MIT Academy of Engineering',
                  rank: '1st Prize Winner',
                  event_name: campaignName,
                  certificate_id: 'CERT-2026-001',
                  date: new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }),
                }}
                onChange={(updatedConfig) => setConfig(updatedConfig)}
                onSave={handleSaveConfig}
                isSaving={savingConfig}
              />
            ) : (
              /* Rendered Final PDF Proof View */
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground flex items-center gap-1.5">
                      <FileCheck className="h-4 w-4 text-emerald-600" />
                      Server Pillow Render Proof
                    </span>
                    <span className="text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                      Sample: {sampleName}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="default"
                      onClick={handleDownloadProofPdf}
                      disabled={downloadingPdf}
                      className="text-xs h-7 gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs cursor-pointer"
                    >
                      {downloadingPdf ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
                      Download Sample PDF
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setActiveViewMode('canva_editor')}
                      className="text-xs h-7 cursor-pointer"
                    >
                      ← Back to Canva Editor
                    </Button>
                  </div>
                </div>

                <div className="rounded-xl border bg-zinc-900 shadow-md p-2 flex items-center justify-center overflow-auto max-h-[750px]">
                  <img
                    src={livePreviewUrl || templateData.template_image_url}
                    alt="Proof Preview"
                    className="w-full h-auto max-h-[720px] object-contain rounded-lg shadow-sm"
                  />
                </div>
              </div>
            )
          ) : (
            /* Blank Upload Template State */
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed rounded-xl p-16 text-center flex flex-col items-center justify-center space-y-3 cursor-pointer hover:border-primary/50 transition-colors bg-muted/20"
            >
              <div className="p-4 rounded-full bg-primary/10 text-primary">
                <Upload className="h-8 w-8" />
              </div>
              <div>
                <p className="text-base font-semibold text-foreground">Upload Certificate Background Template</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
                  Upload your blank certificate design image (PNG or JPG). You can then visually drag and drop recipient name, college, date, rank, and custom fields anywhere on top of it.
                </p>
              </div>
              <Button variant="gradient" size="sm" className="gap-2 text-xs">
                <Upload className="h-3.5 w-3.5" />
                Browse Image File
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
