import { api } from '@/services/api'

export interface Participant {
  id: string
  participant_id: string
  name: string
  recipient_name: string
  email: string
  recipient_email: string
  email_status: 'queued' | 'processing' | 'sent' | 'retrying' | 'failed' | 'unknown' | 'cancelled'
  status: string
  attempt_count: number
  certificate_id?: string
  gmail_message_id?: string
  certificate_drive_file_id?: string
  last_error_code?: string
  last_error_message?: string
  created_at?: string
  sent_at?: string
}

export interface ParticipantUploadResponse {
  campaign_id: string
  imported_count: number
  skipped_count: number
  duplicates_skipped: number
  total_recipients: number
  message: string
}

export const participantService = {
  list: (campaignId: string, statusFilter?: string, search?: string) => {
    let url = `/api/participants/${campaignId}?limit=500`
    if (statusFilter && statusFilter !== 'all') {
      url += `&status_filter=${statusFilter}`
    }
    if (search && search.trim()) {
      url += `&search=${encodeURIComponent(search.trim())}`
    }
    return api.get<Participant[]>(url)
  },

  add: (
    campaignId: string,
    data: {
      name: string
      email: string
      certificate_id?: string
      send_immediately?: boolean
    }
  ) => {
    return api.post<Participant>(`/api/participants/${campaignId}`, {
      recipient_name: data.name.trim(),
      recipient_email: data.email.trim(),
      certificate_id: data.certificate_id?.trim() || undefined,
      send_immediately: Boolean(data.send_immediately),
    })
  },

  upload: (campaignId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.upload<ParticipantUploadResponse>(`/api/participants/${campaignId}/upload`, formData)
  },

  sendSingle: (campaignId: string, participantId: string, forceResend: boolean = false) => {
    return api.post<{ success: boolean; status: string; message: string }>(
      `/api/participants/${campaignId}/${participantId}/send?force_resend=${forceResend}`
    )
  },

  delete: (campaignId: string, participantId: string) => {
    return api.delete<{ success: boolean; message: string }>(
      `/api/participants/${campaignId}/${participantId}`
    )
  },
}

