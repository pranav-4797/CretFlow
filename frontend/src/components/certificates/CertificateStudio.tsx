import React, { useEffect, useState, useRef } from 'react'
import { motion } from 'framer-motion'
import {
  Award,
  Upload,
  Sparkles,
  Sliders,
  Type,
  Palette,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Eye,
  Send,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  templateService,
  TemplateConfig,
  TemplateResponse,
} from '@/services/templates'

interface CertificateStudioProps {
  campaignId: string
  campaignName: string
  onSwitchToEmail?: () => void
}

const FONT_OPTIONS = [
  { id: 'PlayfairDisplay', name: 'Playfair Display', category: 'Luxury Serif', sample: 'John Doe' },
  { id: 'GreatVibes', name: 'Great Vibes', category: 'Calligraphy / Script', sample: 'John Doe' },
  { id: 'Cinzel', name: 'Cinzel', category: 'Academic / Roman', sample: 'JOHN DOE' },
  { id: 'Montserrat', name: 'Montserrat', category: 'Modern Geometric', sample: 'John Doe' },
  { id: 'AlexBrush', name: 'Alex Brush', category: 'Flowing Cursive', sample: 'John Doe' },
]

const COLOR_SWATCHES = [
  { name: 'Dark Slate', hex: '#1e293b' },
  { name: 'Pure Obsidian', hex: '#0f172a' },
  { name: 'Luxury Gold', hex: '#b45309' },
  { name: 'Royal Navy', hex: '#1e3a8a' },
  { name: 'Deep Emerald', hex: '#065f46' },
  { name: 'Burgundy', hex: '#831843' },
]

export function CertificateStudio({ campaignId, campaignName, onSwitchToEmail }: CertificateStudioProps) {
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)

  const [templateData, setTemplateData] = useState<TemplateResponse | null>(null)
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
  })

  const [sampleName, setSampleName] = useState('Jane Doe')
  const [livePreviewUrl, setLivePreviewUrl] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ success: boolean; message: string } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load existing template data
  const loadTemplate = async () => {
    try {
      setLoading(true)
      const res = await templateService.getTemplate(campaignId)
      setTemplateData(res)
      if (res.config) {
        setConfig((prev) => ({ ...prev, ...res.config }))
      }
      if (res.template_image_url) {
        setLivePreviewUrl(res.template_image_url)
      }
    } catch (err: any) {
      console.warn('No existing template loaded:', err)
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
      // Trigger a live preview with current config
      handleGeneratePreview(res.config)
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to upload certificate template.' })
    } finally {
      setUploading(false)
    }
  }

  // Handle generating live preview from backend
  const handleGeneratePreview = async (overrideConfig?: TemplateConfig) => {
    const activeConfig = overrideConfig || config
    try {
      setPreviewLoading(true)
      const res = await templateService.previewTemplate(campaignId, sampleName, activeConfig)
      setLivePreviewUrl(res.preview_data_url)
    } catch (err: any) {
      console.error('Failed to generate live preview:', err)
    } finally {
      setPreviewLoading(false)
    }
  }

  // Save config
  const handleSaveConfig = async () => {
    try {
      setSavingConfig(true)
      await templateService.saveConfig(campaignId, config)
      setFeedback({ success: true, message: 'Template design saved successfully.' })
      handleGeneratePreview()
    } catch (err: any) {
      setFeedback({ success: false, message: err.message || 'Failed to save configuration.' })
    } finally {
      setSavingConfig(false)
    }
  }

  // Bulk generate certificates in Google Drive
  const handleGenerateAll = async () => {
    try {
      setGenerating(true)
      setFeedback(null)
      // Save config first
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
    <div className="space-y-6">
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

      {/* Main Studio Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Visual Canvas / Preview */}
        <div className="lg:col-span-7 space-y-4">
          <Card className="overflow-hidden">
            <CardHeader className="py-3 px-4 border-b flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm flex items-center gap-2">
                  <Award className="h-4 w-4 text-primary" />
                  Certificate Studio — {campaignName}
                </CardTitle>
                <CardDescription className="text-[11px]">
                  Real-time preview with recipient name rendered using chosen font
                </CardDescription>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleGeneratePreview()}
                  disabled={previewLoading || !templateData?.has_template}
                  className="gap-1.5 text-xs h-7"
                >
                  {previewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Eye className="h-3 w-3" />}
                  Refresh Preview
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  className="gap-1.5 text-xs h-7"
                >
                  {uploading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Upload className="h-3 w-3" />}
                  {templateData?.has_template ? 'Change Template' : 'Upload Template'}
                </Button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/jpg"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </div>
            </CardHeader>

            <CardContent className="p-4 bg-muted/20">
              {livePreviewUrl ? (
                <div className="relative rounded-lg border bg-white dark:bg-card shadow-sm overflow-hidden flex items-center justify-center">
                  <img
                    src={livePreviewUrl}
                    alt="Certificate Preview"
                    className="w-full h-auto max-h-[480px] object-contain"
                  />
                  {previewLoading && (
                    <div className="absolute inset-0 bg-background/60 backdrop-blur-xs flex items-center justify-center">
                      <div className="flex items-center gap-2 bg-card p-3 rounded-lg border shadow-lg text-xs">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        <span>Rendering sample with {config.font_family}...</span>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed rounded-xl p-12 text-center flex flex-col items-center justify-center space-y-3 cursor-pointer hover:border-primary/50 transition-colors bg-background"
                >
                  <div className="p-3 rounded-full bg-primary/10 text-primary">
                    <Upload className="h-6 w-6" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">Upload Certificate Background Template</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Upload your blank certificate design image (PNG or JPG, up to 20MB)
                    </p>
                  </div>
                  <Button variant="gradient" size="sm" className="gap-2">
                    <Upload className="h-3.5 w-3.5" />
                    Browse Image File
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Sample Participant Name Field */}
          <div className="flex items-center gap-3 p-3 rounded-lg border bg-card text-xs">
            <Label htmlFor="sample-name" className="text-xs font-medium shrink-0">Sample Name:</Label>
            <Input
              id="sample-name"
              value={sampleName}
              onChange={(e) => setSampleName(e.target.value)}
              placeholder="e.g. John Doe"
              className="h-8 text-xs max-w-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleGeneratePreview()}
              disabled={previewLoading || !templateData?.has_template}
              className="h-8 text-xs shrink-0"
            >
              Update Preview
            </Button>
          </div>
        </div>

        {/* Right Column: Typography & Layout Controls */}
        <div className="lg:col-span-5 space-y-4">
          <Card>
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm flex items-center gap-2">
                <Sliders className="h-4 w-4 text-primary" />
                Typography & Position
              </CardTitle>
              <CardDescription className="text-[11px]">
                Customize font style, name placement coordinates, and color
              </CardDescription>
            </CardHeader>

            <CardContent className="p-4 space-y-5">
              {/* Font Family Selector */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold flex items-center gap-1.5">
                  <Type className="h-3.5 w-3.5 text-primary" />
                  Font Style
                </Label>
                <div className="grid grid-cols-1 gap-2">
                  {FONT_OPTIONS.map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      onClick={() => {
                        const newConfig = { ...config, font_family: f.id }
                        setConfig(newConfig)
                        handleGeneratePreview(newConfig)
                      }}
                      className={`flex items-center justify-between p-2.5 rounded-lg border text-left transition-all ${
                        config.font_family === f.id
                          ? 'border-primary bg-primary/5 text-primary ring-1 ring-primary'
                          : 'border-border/60 hover:border-primary/40 bg-card'
                      }`}
                    >
                      <div>
                        <div className="text-xs font-medium">{f.name}</div>
                        <div className="text-[10px] text-muted-foreground">{f.category}</div>
                      </div>
                      <span className="text-sm font-semibold tracking-wide" style={{ fontFamily: 'serif' }}>
                        {f.sample}
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Font Size & Color */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="font-size" className="text-xs font-medium">Font Size ({config.font_size}pt)</Label>
                  <input
                    id="font-size"
                    type="range"
                    min="24"
                    max="120"
                    step="2"
                    value={config.font_size}
                    onChange={(e) => {
                      const newConfig = { ...config, font_size: parseInt(e.target.value) }
                      setConfig(newConfig)
                    }}
                    onMouseUp={() => handleGeneratePreview()}
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="font-color" className="text-xs font-medium">Hex Color</Label>
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      id="font-color"
                      value={config.font_color}
                      onChange={(e) => {
                        const newConfig = { ...config, font_color: e.target.value }
                        setConfig(newConfig)
                      }}
                      onBlur={() => handleGeneratePreview()}
                      className="h-8 w-8 rounded border cursor-pointer p-0.5"
                    />
                    <Input
                      value={config.font_color}
                      onChange={(e) => setConfig({ ...config, font_color: e.target.value })}
                      onBlur={() => handleGeneratePreview()}
                      className="h-8 text-xs font-mono"
                    />
                  </div>
                </div>
              </div>

              {/* Color Presets */}
              <div className="space-y-1.5">
                <Label className="text-[11px] text-muted-foreground flex items-center gap-1">
                  <Palette className="h-3 w-3" />
                  Color Swatches
                </Label>
                <div className="flex items-center gap-2">
                  {COLOR_SWATCHES.map((swatch) => (
                    <button
                      key={swatch.hex}
                      type="button"
                      title={swatch.name}
                      onClick={() => {
                        const newConfig = { ...config, font_color: swatch.hex }
                        setConfig(newConfig)
                        handleGeneratePreview(newConfig)
                      }}
                      className={`h-6 w-6 rounded-full border shadow-xs transition-transform ${
                        config.font_color.toLowerCase() === swatch.hex.toLowerCase() ? 'scale-125 ring-2 ring-primary ring-offset-1' : 'hover:scale-110'
                      }`}
                      style={{ backgroundColor: swatch.hex }}
                    />
                  ))}
                </div>
              </div>

              {/* Coordinates Sliders */}
              <div className="space-y-3 pt-2 border-t">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <Label htmlFor="x-pos">Horizontal Position (X: {config.name_x_percent}%)</Label>
                    <span className="text-[10px] text-muted-foreground">50% = Center</span>
                  </div>
                  <input
                    id="x-pos"
                    type="range"
                    min="10"
                    max="90"
                    step="0.5"
                    value={config.name_x_percent}
                    onChange={(e) => setConfig({ ...config, name_x_percent: parseFloat(e.target.value) })}
                    onMouseUp={() => handleGeneratePreview()}
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <Label htmlFor="y-pos">Vertical Position (Y: {config.name_y_percent}%)</Label>
                    <span className="text-[10px] text-muted-foreground">Lower = Top, Higher = Bottom</span>
                  </div>
                  <input
                    id="y-pos"
                    type="range"
                    min="15"
                    max="85"
                    step="0.5"
                    value={config.name_y_percent}
                    onChange={(e) => setConfig({ ...config, name_y_percent: parseFloat(e.target.value) })}
                    onMouseUp={() => handleGeneratePreview()}
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer"
                  />
                </div>
              </div>

              {/* Actions */}
              <div className="pt-3 border-t space-y-2">
                <Button
                  onClick={handleSaveConfig}
                  disabled={savingConfig || !templateData?.has_template}
                  variant="outline"
                  className="w-full gap-2 text-xs"
                >
                  {savingConfig ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  Save Design Coordinates
                </Button>

                <Button
                  onClick={handleGenerateAll}
                  disabled={generating || !templateData?.has_template}
                  variant="gradient"
                  className="w-full gap-2 text-xs py-5"
                >
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Generating & Saving to Google Shared Drive...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Generate All Participant Certificates
                    </>
                  )}
                </Button>

                {onSwitchToEmail && (
                  <Button
                    onClick={onSwitchToEmail}
                    variant="ghost"
                    size="sm"
                    className="w-full gap-1.5 text-xs text-primary"
                  >
                    <Send className="h-3.5 w-3.5" />
                    Go to Email Distributor →
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
