/**
 * Gmail & Email API Service with Firestore-backed Batch Engine & Pause/Resume Controls.
 */

import { api } from '@/services/api'

export interface GmailStatus {
  is_connected: boolean
  google_email?: string
  connected_at?: string
  last_used_at?: string
  scopes?: string
}

export interface GmailConnectResponse {
  authorization_url: string
}

export interface GmailTestEmailRequest {
  recipient_email: string
  subject?: string
  custom_message?: string
}

export interface GmailTestEmailResponse {
  success: boolean
  message: string
  message_id?: string
  sender: string
  recipient: string
}

export interface SendPreviewRequest {
  subject_template: string
  body_template: string
  sample_variables?: Record<string, any>
}

export interface SendPreviewResponse {
  rendered_subject: string
  rendered_html: string
  rendered_text: string
}

export interface SendCampaignRequest {
  campaign_id: string
  subject_template: string
  body_template: string
  batch_size?: number
  confirm: boolean
}

export interface SendCampaignResponse {
  campaign_id: string
  status: string
  queued_count: number
  message: string
}

export interface EmailLog {
  id?: string
  participant_id?: string
  user_id?: string
  campaign_id?: string
  recipient_email: string
  recipient_name?: string
  subject?: string
  status?: string
  email_status?: string
  attempt_count: number
  max_attempts?: number
  gmail_message_id?: string
  drive_file_id?: string
  certificate_filename?: string
  last_error_code?: string
  last_error_message?: string
  created_at?: string
  sent_at?: string
  updated_at?: string
}

export interface CampaignEmailStatus {
  campaign_id: string
  campaign_status?: string
  total_count: number
  sent_count: number
  failed_count: number
  queued_count: number
  processing_count: number
  retrying_count: number
  cancelled_count?: number
  unknown_count?: number
  recent_logs: EmailLog[]
}

export const gmailService = {
  /** Fetch Gmail connection status */
  getStatus: () => api.get<GmailStatus>('/api/gmail/status'),

  /** Get Google OAuth authorization URL */
  getConnectUrl: () => api.get<GmailConnectResponse>('/api/gmail/connect'),

  /** Disconnect Gmail account and revoke access */
  disconnect: () => api.post<{ success: boolean; message: string }>('/api/gmail/disconnect'),

  /** Send a test email to verify Gmail API delivery */
  sendTestEmail: (data: GmailTestEmailRequest) =>
    api.post<GmailTestEmailResponse>('/api/gmail/test', data),

  /** Preview rendered subject and HTML template */
  sendPreview: (data: SendPreviewRequest) =>
    api.post<SendPreviewResponse>('/api/gmail/send-preview', data),

  /** Enqueue campaign emails for batch sending */
  sendCampaign: (data: SendCampaignRequest) =>
    api.post<SendCampaignResponse>('/api/gmail/send-campaign', data),

  /** Get campaign email status and progress */
  getCampaignStatus: (campaignId: string) =>
    api.get<CampaignEmailStatus>(`/api/emails/${campaignId}/status`),

  /** Pause ongoing campaign batch sending */
  pauseCampaign: (campaignId: string) =>
    api.post<{ campaign_id: string; status: string; message: string }>(
      `/api/emails/${campaignId}/pause`,
    ),

  /** Resume paused campaign batch sending */
  resumeCampaign: (campaignId: string) =>
    api.post<{ campaign_id: string; status: string; message: string }>(
      `/api/emails/${campaignId}/resume`,
    ),

  /** Cancel ongoing campaign batch sending */
  cancelCampaign: (campaignId: string) =>
    api.post<{ campaign_id: string; status: string; message: string }>(
      `/api/emails/${campaignId}/cancel`,
    ),

  /** Retry eligible failed emails for a campaign */
  retryFailed: (campaignId: string) =>
    api.post<{ campaign_id: string; reset_count: number; message: string }>(
      `/api/emails/${campaignId}/retry`,
    ),

  /** Force explicit state and counter reconciliation */
  reconcileCampaign: (campaignId: string) =>
    api.post<CampaignEmailStatus>(`/api/emails/${campaignId}/reconcile`),
}
