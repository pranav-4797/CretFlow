import React, { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import {
  FileText,
  Copy,
  Check,
  ExternalLink,
  Save,
  Send,
  Sparkles,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  CheckCircle2,
  Terminal,
  Loader2,
  Mail,
  Eye,
  Code,
  Tag,
  EyeOff,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { api, API_BASE_URL } from '@/services/api'
import { useToast } from '@/hooks/use-toast'

interface GoogleFormsIntegrationProps {
  campaignId: string
  campaignName: string
}

interface WebhookConfig {
  passing_score: number
  auto_email: boolean
  webhook_secret?: string
  quiz_email_subject?: string
  quiz_email_body?: string
  show_score_in_email: boolean
}

interface SimulationResult {
  status: string
  recipient_name: string
  recipient_email: string
  score: number
  total_score: number
  score_percentage: number
  passing_threshold_percentage: number
  passed: boolean
  certificate_id?: string
  email_sent: boolean
  message: string
}

export const GoogleFormsIntegration: React.FC<GoogleFormsIntegrationProps> = ({
  campaignId,
  campaignName,
}) => {
  const { toast } = useToast()

  // Tab state for the right column
  const [rightTab, setRightTab] = useState<'email_template' | 'script'>('email_template')

  // Configuration state
  const [config, setConfig] = useState<WebhookConfig>({
    passing_score: 60,
    auto_email: true,
    webhook_secret: '',
    quiz_email_subject: 'Congratulations on Passing {{event_name}}! Here is your Certificate',
    quiz_email_body: 'You have successfully passed the assessment for {{event_name}}! Your official certificate has been generated and is attached to this email as a high-resolution PDF.',
    show_score_in_email: true,
  })
  const [loadingConfig, setLoadingConfig] = useState(false)
  const [savingConfig, setSavingConfig] = useState(false)
  const [copiedUrl, setCopiedUrl] = useState(false)
  const [copiedScript, setCopiedScript] = useState(false)

  // Simulation test state
  const [simName, setSimName] = useState('John Doe')
  const [simEmail, setSimEmail] = useState('student@example.com')
  const [simScore, setSimScore] = useState(85)
  const [simTotalScore, setSimTotalScore] = useState(100)
  const [simulating, setSimulating] = useState(false)
  const [simResult, setSimResult] = useState<SimulationResult | null>(null)

  const webhookUrl = `${API_BASE_URL}/api/webhooks/google-form/${campaignId}`

  // Fetch configuration on load or campaignId change
  useEffect(() => {
    if (!campaignId) return
    let isMounted = true
    async function fetchConfig() {
      try {
        setLoadingConfig(true)
        const data = await api.get<WebhookConfig>(`/api/webhooks/config/${campaignId}`)
        if (isMounted && data) {
          setConfig({
            passing_score: data.passing_score ?? 60,
            auto_email: data.auto_email ?? true,
            webhook_secret: data.webhook_secret || '',
            quiz_email_subject: data.quiz_email_subject || 'Congratulations on Passing {{event_name}}! Here is your Certificate',
            quiz_email_body: data.quiz_email_body || 'You have successfully passed the assessment for {{event_name}}! Your official certificate has been generated and is attached to this email as a high-resolution PDF.',
            show_score_in_email: data.show_score_in_email ?? true,
          })
        }
      } catch (err) {
        console.warn('Could not load webhook config, defaulting:', err)
      } finally {
        if (isMounted) setLoadingConfig(false)
      }
    }
    fetchConfig()
    return () => {
      isMounted = false
    }
  }, [campaignId])

  const handleSaveConfig = async () => {
    try {
      setSavingConfig(true)
      await api.put(`/api/webhooks/config/${campaignId}`, {
        passing_score: Number(config.passing_score),
        auto_email: Boolean(config.auto_email),
        webhook_secret: config.webhook_secret ? config.webhook_secret.trim() : null,
        quiz_email_subject: config.quiz_email_subject ? config.quiz_email_subject.trim() : null,
        quiz_email_body: config.quiz_email_body ? config.quiz_email_body.trim() : null,
        show_score_in_email: Boolean(config.show_score_in_email),
      })
      toast({
        title: 'Settings Saved',
        description: 'Quiz certification criteria and email template updated successfully.',
      })
    } catch (err: any) {
      toast({
        title: 'Failed to save',
        description: err.message || 'Error updating webhook configuration',
        variant: 'destructive',
      })
    } finally {
      setSavingConfig(false)
    }
  }

  const handleInsertVariable = (tag: string) => {
    setConfig(prev => ({
      ...prev,
      quiz_email_body: (prev.quiz_email_body || '') + ` ${tag} `,
    }))
  }

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(webhookUrl)
    setCopiedUrl(true)
    toast({ title: 'Webhook URL Copied', description: 'Paste it in your Google Apps Script.' })
    setTimeout(() => setCopiedUrl(false), 2500)
  }

  const appsScriptCode = `/**
 * Google Apps Script for Automated CertFlow Certificate Issuance
 * Campaign: ${campaignName}
 * Webhook URL: ${webhookUrl}
 */
function onFormSubmit(e) {
  var WEBHOOK_URL = "${webhookUrl}";
  var SECRET_TOKEN = "${config.webhook_secret || ''}";

  try {
    var response = null;
    if (e && e.response) {
      response = e.response;
    } else {
      // Allows testing with the "▶ Run" button in Apps Script editor
      var form = FormApp.getActiveForm();
      var allResponses = form.getResponses();
      if (allResponses.length === 0) {
        Logger.log("⚠️ No submissions found in form yet.");
        return;
      }
      response = allResponses[allResponses.length - 1];
    }

    var respondentEmail = response.getRespondentEmail() || "";
    var itemResponses = response.getItemResponses();
    var recipientName = "";
    var totalEarnedScore = 0;
    var totalPossibleScore = 0;

    for (var i = 0; i < itemResponses.length; i++) {
      var ir = itemResponses[i];
      var item = ir.getItem();
      var title = item.getTitle().toLowerCase();
      var answer = ir.getResponse();

      // Extract Name and Email
      if (title.indexOf("name") !== -1 || title.indexOf("student") !== -1) {
        if (!recipientName) recipientName = String(answer).trim();
      }
      if (!respondentEmail && (title.indexOf("email") !== -1 || title.indexOf("mail") !== -1)) {
        respondentEmail = String(answer).trim();
      }

      // Calculate score safely across all questions
      try {
        var score = ir.getScore();
        if (score !== null && score !== undefined) {
          totalEarnedScore += Number(score);
          var maxPts = (typeof item.getPoints === "function") ? item.getPoints() : 20;
          totalPossibleScore += Number(maxPts || 20);
        }
      } catch (errScore) {}
    }

    if (totalPossibleScore === 0) {
      totalEarnedScore = 100;
      totalPossibleScore = 100;
    }

    if (!recipientName) {
      recipientName = respondentEmail ? respondentEmail.split("@")[0] : "Student";
    }

    Logger.log("Sending: Student=" + recipientName + ", Email=" + respondentEmail + ", Score=" + totalEarnedScore + "/" + totalPossibleScore);

    // Send to CertFlow Webhook
    var payload = {
      recipient_name: recipientName,
      recipient_email: respondentEmail,
      score: totalEarnedScore,
      total_score: totalPossibleScore,
      webhook_secret: SECRET_TOKEN || undefined
    };

    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    var res = UrlFetchApp.fetch(WEBHOOK_URL, options);
    Logger.log("✅ CertFlow Response: " + res.getContentText());
  } catch (err) {
    Logger.log("❌ CertFlow Webhook Error: " + err.toString());
  }
}`

  const handleCopyScript = () => {
    navigator.clipboard.writeText(appsScriptCode)
    setCopiedScript(true)
    toast({ title: 'Code Copied', description: 'Ready to paste into Google Apps Script!' })
    setTimeout(() => setCopiedScript(false), 2500)
  }

  const handleRunSimulation = async () => {
    if (!simName.trim() || !simEmail.trim()) {
      toast({ title: 'Missing details', description: 'Please enter a name and valid email address.', variant: 'destructive' })
      return
    }

    try {
      setSimulating(true)
      setSimResult(null)
      const res = await api.post<SimulationResult>(`/api/webhooks/google-form/${campaignId}`, {
        recipient_name: simName.trim(),
        recipient_email: simEmail.trim(),
        score: Number(simScore),
        total_score: Number(simTotalScore),
        webhook_secret: config.webhook_secret ? config.webhook_secret.trim() : undefined,
      })
      setSimResult(res)
      if (res.passed) {
        toast({
          title: 'Quiz Passed! Certificate Issued',
          description: `Generated certificate ${res.certificate_id || ''} for ${res.recipient_name}.`,
        })
      } else {
        toast({
          title: 'Quiz Score Below Threshold',
          description: `Score of ${res.score_percentage}% is below ${res.passing_threshold_percentage}%. No certificate issued.`,
        })
      }
    } catch (err: any) {
      toast({
        title: 'Simulation Error',
        description: err.message || 'Failed to submit test quiz entry',
        variant: 'destructive',
      })
    } finally {
      setSimulating(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-xl border bg-gradient-to-r from-indigo-50/50 via-purple-50/30 to-blue-50/40 p-6 dark:from-indigo-950/20 dark:via-purple-950/10 dark:to-blue-950/20">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-300 mb-1">
              <Sparkles className="w-3.5 h-3.5" />
              Automated Quiz & Exam Issuance
            </div>
            <h2 className="text-xl font-bold tracking-tight text-foreground">
              Google Forms & Quiz Automation
            </h2>
            <p className="text-sm text-muted-foreground max-w-2xl">
              Connect your Google Form quiz to <strong>{campaignName}</strong>. Whenever students take
              the test, CertFlow evaluates their score. If they meet or beat your passing threshold,
              their personalized certificate is generated and emailed to them immediately with the PDF
              attached.
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Webhook Setup & Passing Score Settings (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Webhook URL Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Terminal className="w-4 h-4 text-indigo-500" />
                Live Webhook Endpoint
              </CardTitle>
              <CardDescription>
                Public endpoint triggered by Google Apps Script on each form submission
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-muted px-3 py-2 rounded-md text-xs font-mono break-all border select-all">
                  {webhookUrl}
                </code>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCopyUrl}
                  className="shrink-0 gap-1.5"
                >
                  {copiedUrl ? <Check className="w-4 h-4 text-emerald-500" /> : <Copy className="w-4 h-4" />}
                  {copiedUrl ? 'Copied' : 'Copy'}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Rules & Threshold Settings */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-500" />
                Certification Criteria
              </CardTitle>
              <CardDescription>
                Configure the qualifying score and automatic email dispatching
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {loadingConfig ? (
                <div className="flex items-center justify-center py-6 text-muted-foreground gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading settings...
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <Label htmlFor="passing_score" className="text-sm font-medium">
                        Passing Score Threshold
                      </Label>
                      <span className="text-sm font-bold text-indigo-600 dark:text-indigo-400">
                        {config.passing_score}%
                      </span>
                    </div>
                    <input
                      type="range"
                      id="passing_score"
                      min="0"
                      max="100"
                      step="5"
                      value={config.passing_score}
                      onChange={(e) =>
                        setConfig({ ...config, passing_score: Number(e.target.value) })
                      }
                      className="w-full accent-indigo-600 cursor-pointer"
                    />
                    <p className="text-xs text-muted-foreground">
                      Students scoring &ge; {config.passing_score}% will automatically earn a
                      certificate. Students below will be logged without issuing.
                    </p>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                    <div className="space-y-0.5">
                      <div className="text-sm font-medium">Auto-Send Certificate via Gmail</div>
                      <div className="text-xs text-muted-foreground">
                        Emails official PDF immediately upon passing
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={config.auto_email}
                      onChange={(e) => setConfig({ ...config, auto_email: e.target.checked })}
                      className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="webhook_secret" className="text-xs font-medium text-muted-foreground">
                      Security Secret Token (Optional)
                    </Label>
                    <Input
                      id="webhook_secret"
                      placeholder="e.g. quiz-secret-pass-2026"
                      value={config.webhook_secret || ''}
                      onChange={(e) => setConfig({ ...config, webhook_secret: e.target.value })}
                      className="text-xs font-mono"
                    />
                    <p className="text-[11px] text-muted-foreground">
                      If set, incoming submissions must provide this exact token.
                    </p>
                  </div>

                  <Button
                    onClick={handleSaveConfig}
                    disabled={savingConfig}
                    className="w-full gap-2"
                  >
                    {savingConfig ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    Save Automation Settings
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          {/* Test Simulator */}
          <Card className="border-indigo-100 dark:border-indigo-950">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Send className="w-4 h-4 text-indigo-500" />
                Live Form Submission Simulator
              </CardTitle>
              <CardDescription>
                Simulate a student completing your Google Form quiz in real time
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Student Full Name</Label>
                  <Input
                    value={simName}
                    onChange={(e) => setSimName(e.target.value)}
                    placeholder="Jane Doe"
                    className="text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Student Email</Label>
                  <Input
                    type="email"
                    value={simEmail}
                    onChange={(e) => setSimEmail(e.target.value)}
                    placeholder="jane@example.com"
                    className="text-xs"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Achieved Score</Label>
                  <Input
                    type="number"
                    value={simScore}
                    onChange={(e) => setSimScore(Number(e.target.value))}
                    className="text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Max Achievable Score</Label>
                  <Input
                    type="number"
                    value={simTotalScore}
                    onChange={(e) => setSimTotalScore(Number(e.target.value))}
                    className="text-xs"
                  />
                </div>
              </div>

              <Button
                variant="secondary"
                size="sm"
                onClick={handleRunSimulation}
                disabled={simulating}
                className="w-full gap-2 font-medium"
              >
                {simulating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                Run Test Submission
              </Button>

              {simResult && (
                <motion.div
                  initial={{ opacity: 0, y: 5 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`p-3 rounded-lg border text-xs space-y-1.5 ${
                    simResult.passed
                      ? 'bg-emerald-50/70 border-emerald-200 text-emerald-950 dark:bg-emerald-950/20 dark:border-emerald-800 dark:text-emerald-200'
                      : 'bg-amber-50/70 border-amber-200 text-amber-950 dark:bg-amber-950/20 dark:border-amber-800 dark:text-amber-200'
                  }`}
                >
                  <div className="flex items-center gap-2 font-semibold">
                    {simResult.passed ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-amber-600" />
                    )}
                    {simResult.passed ? 'Status: Qualified & Issued' : 'Status: Below Passing Threshold'}
                  </div>
                  <p>{simResult.message}</p>
                  <div className="text-[11px] opacity-80 pt-1 border-t border-current/10 flex justify-between">
                    <span>
                      Score: {simResult.score}/{simResult.total_score} ({simResult.score_percentage}%)
                    </span>
                    <span>
                      Passing Threshold: {simResult.passing_threshold_percentage}%
                    </span>
                  </div>
                  {simResult.certificate_id && (
                    <div className="text-[11px] font-mono text-indigo-700 dark:text-indigo-300">
                      Certificate ID: {simResult.certificate_id}
                    </div>
                  )}
                </motion.div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Email Template Customizer & Copy-Paste Apps Script (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {/* Right Column Tab Switcher */}
          <div className="flex items-center justify-between border-b pb-3">
            <div className="flex gap-1.5 p-1 bg-muted/60 rounded-lg">
              <button
                type="button"
                onClick={() => setRightTab('email_template')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  rightTab === 'email_template'
                    ? 'bg-background text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Mail className="w-3.5 h-3.5 text-indigo-500" />
                Customize Quiz Email
              </button>
              <button
                type="button"
                onClick={() => setRightTab('script')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  rightTab === 'script'
                    ? 'bg-background text-foreground shadow-xs'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Code className="w-3.5 h-3.5 text-indigo-500" />
                Google Apps Script
              </button>
            </div>
            <span className="text-[11px] text-muted-foreground hidden sm:inline">
              {rightTab === 'email_template' ? 'Custom Student Email Template' : 'Setup Code for Google Forms'}
            </span>
          </div>

          {rightTab === 'email_template' ? (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Mail className="w-4 h-4 text-indigo-500" />
                      Quiz Certificate Email Template
                    </CardTitle>
                    <CardDescription>
                      Edit the email subject, message body, and control whether students see their score
                    </CardDescription>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleSaveConfig}
                    disabled={savingConfig}
                    className="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white shrink-0"
                  >
                    {savingConfig ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    Save Template
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="space-y-5">
                {/* Score Visibility Toggle */}
                <div className="flex items-center justify-between p-3.5 rounded-lg border bg-muted/40">
                  <div className="space-y-0.5">
                    <div className="text-sm font-semibold flex items-center gap-1.5">
                      {config.show_score_in_email ? (
                        <Eye className="w-4 h-4 text-emerald-600" />
                      ) : (
                        <EyeOff className="w-4 h-4 text-muted-foreground" />
                      )}
                      Show Quiz Score to Student
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {config.show_score_in_email
                        ? 'Student will see their score breakdown (e.g. 80 / 100 (80%)) in the congratulations email.'
                        : 'Score breakdown will be hidden. Student only sees the congratulations and official Certificate ID.'}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    id="show_score_toggle"
                    checked={config.show_score_in_email}
                    onChange={(e) => setConfig({ ...config, show_score_in_email: e.target.checked })}
                    className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                  />
                </div>

                {/* Email Subject Line */}
                <div className="space-y-1.5">
                  <Label htmlFor="quiz_email_subject" className="text-xs font-semibold">
                    Email Subject Line
                  </Label>
                  <Input
                    id="quiz_email_subject"
                    value={config.quiz_email_subject || ''}
                    onChange={(e) => setConfig({ ...config, quiz_email_subject: e.target.value })}
                    placeholder="Congratulations on Passing {{event_name}}! Here is your Certificate"
                    className="text-xs"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Available tags: <code className="bg-muted px-1 rounded">{"{{event_name}}"}</code>, <code className="bg-muted px-1 rounded">{"{{name}}"}</code>, <code className="bg-muted px-1 rounded">{"{{score_percentage}}"}</code>
                  </p>
                </div>

                {/* Email Body Message */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="quiz_email_body" className="text-xs font-semibold">
                      Custom Congratulations Message
                    </Label>
                    <span className="text-[11px] text-muted-foreground">Supports multiline text</span>
                  </div>
                  <Textarea
                    id="quiz_email_body"
                    rows={4}
                    value={config.quiz_email_body || ''}
                    onChange={(e) => setConfig({ ...config, quiz_email_body: e.target.value })}
                    placeholder="Write your custom message here..."
                    className="text-xs font-sans leading-relaxed"
                  />
                  
                  {/* Variable chips */}
                  <div className="pt-1">
                    <div className="text-[11px] font-medium text-muted-foreground mb-1.5 flex items-center gap-1">
                      <Tag className="w-3 h-3 text-indigo-500" />
                      Click tag to insert:
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        { label: 'Student Name', tag: '{{name}}' },
                        { label: 'Event / Quiz Name', tag: '{{event_name}}' },
                        { label: 'Score', tag: '{{score}}' },
                        { label: 'Total Score', tag: '{{total_score}}' },
                        { label: 'Score %', tag: '{{score_percentage}}' },
                        { label: 'Certificate ID', tag: '{{certificate_id}}' },
                      ].map((item) => (
                        <button
                          key={item.tag}
                          type="button"
                          onClick={() => handleInsertVariable(item.tag)}
                          className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 hover:bg-indigo-100 transition-colors"
                        >
                          + {item.tag}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Real-time Email Preview */}
                <div className="space-y-2 pt-2 border-t">
                  <div className="text-xs font-semibold flex items-center gap-1.5 text-foreground">
                    <Eye className="w-3.5 h-3.5 text-indigo-500" />
                    Live Student Email Preview
                  </div>

                  <div className="rounded-lg border bg-white dark:bg-zinc-950 p-4 text-xs shadow-xs space-y-3 font-sans">
                    <div className="border-b pb-2 text-[11px] text-muted-foreground">
                      <span className="font-semibold text-foreground">Subject: </span>
                      {(config.quiz_email_subject || 'Congratulations on Passing {{event_name}}! Here is your Certificate')
                        .replace('{{event_name}}', campaignName)
                        .replace('{{name}}', 'Jane Doe')
                        .replace('{{score_percentage}}', '85%')}
                    </div>

                    <div className="space-y-2">
                      <h3 className="text-indigo-600 dark:text-indigo-400 font-bold text-sm">
                        Congratulations, Jane Doe! 🎓
                      </h3>
                      <p className="text-zinc-700 dark:text-zinc-300 whitespace-pre-line leading-relaxed">
                        {(config.quiz_email_body || 'You have successfully passed the assessment for {{event_name}}! Your official certificate has been generated and is attached to this email as a PDF.')
                          .replace('{{event_name}}', campaignName)
                          .replace('{{name}}', 'Jane Doe')
                          .replace('{{score}}', '85')
                          .replace('{{total_score}}', '100')
                          .replace('{{score_percentage}}', '85%')
                          .replace('{{certificate_id}}', 'CERT-8F29A10B')}
                      </p>
                    </div>

                    {/* Conditionally rendered score box */}
                    <div className="bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-md p-3 space-y-1">
                      {config.show_score_in_email ? (
                        <div className="text-zinc-700 dark:text-zinc-300">
                          <strong>Score:</strong> 85 / 100 (85%)
                        </div>
                      ) : null}
                      <div className="text-zinc-700 dark:text-zinc-300 font-mono text-[11px]">
                        <strong>Certificate ID:</strong> CERT-8F29A10B
                      </div>
                    </div>

                    <div className="border-t pt-2 text-[10px] text-zinc-400">
                      Attachment: <span className="font-mono text-indigo-600 dark:text-indigo-400 font-medium">Certificate_CERT-8F29A10B_Jane Doe.pdf</span>
                    </div>
                  </div>
                </div>

                <Button
                  onClick={handleSaveConfig}
                  disabled={savingConfig}
                  className="w-full gap-2 bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  {savingConfig ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  Save Email Template & Automation Settings
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <FileText className="w-4 h-4 text-indigo-500" />
                      Google Apps Script (Ready to Copy)
                    </CardTitle>
                    <CardDescription>
                      Pasted directly into your Google Form or Google Sheet script editor
                    </CardDescription>
                  </div>
                  <Button
                    size="sm"
                    onClick={handleCopyScript}
                    className="gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white shrink-0"
                  >
                    {copiedScript ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    {copiedScript ? 'Copied to Clipboard!' : 'Copy Script'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative rounded-lg bg-zinc-950 p-4 font-mono text-xs text-zinc-200 overflow-x-auto max-h-[380px] border border-zinc-800">
                  <pre>{appsScriptCode}</pre>
                </div>

                {/* 3 Step Setup Instructions */}
                <div className="rounded-lg border bg-muted/40 p-4 space-y-3">
                  <h4 className="text-sm font-semibold flex items-center gap-2 text-foreground">
                    <HelpCircle className="w-4 h-4 text-indigo-500" />
                    Quick Setup Guide (Takes 60 Seconds)
                  </h4>

                  <ol className="text-xs text-muted-foreground space-y-2 list-decimal list-inside pl-1">
                    <li>
                      <strong className="text-foreground">Open your Google Form:</strong> Click the
                      three dots (<strong>⋮</strong>) in the upper right corner &rarr; select{' '}
                      <span className="font-semibold text-foreground">Script editor</span> (or in the
                      linked Google Sheet, select{' '}
                      <span className="font-semibold text-foreground">Extensions &gt; Apps Script</span>).
                    </li>
                    <li>
                      <strong className="text-foreground">Paste the code:</strong> Delete any
                      sample code in the editor, paste the script copied above, and click the{' '}
                      <span className="font-semibold text-foreground">Save (💾)</span> icon.
                    </li>
                    <li>
                      <strong className="text-foreground">Add the Trigger:</strong> In the left
                      sidebar of Apps Script, click the alarm clock icon (
                      <span className="font-semibold text-foreground">Triggers ⏰</span>) &rarr; click{' '}
                      <span className="font-semibold text-foreground">Add Trigger</span> (bottom right).
                      <ul className="list-disc list-inside pl-4 pt-1 space-y-1">
                        <li>Choose which function to run: <code className="bg-muted px-1 rounded">onFormSubmit</code></li>
                        <li>Select event source: <code className="bg-muted px-1 rounded">From form</code></li>
                        <li>Select event type: <code className="bg-muted px-1 rounded">On form submit</code></li>
                      </ul>
                    </li>
                  </ol>

                  <div className="pt-2 text-[11px] text-muted-foreground border-t flex items-center justify-between">
                    <span>That&apos;s all! Every passing student will get their certificate instantly.</span>
                    <a
                      href="https://script.google.com"
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-indigo-600 hover:underline"
                    >
                      Open Google Apps Script <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
