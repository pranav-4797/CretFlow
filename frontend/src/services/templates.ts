import { api } from '@/services/api'

export interface TemplateConfig {
  font_family: string
  font_size: number
  font_color: string
  name_x_percent: number
  name_y_percent: number
  text_align: 'center' | 'left' | 'right'
  show_cert_id: boolean
  cert_id_x_percent: number
  cert_id_y_percent: number
  show_date: boolean
  date_x_percent: number
  date_y_percent: number
}

export interface TemplateResponse {
  campaign_id: string
  has_template: boolean
  template_image_url?: string
  template_drive_file_id?: string
  config: TemplateConfig
}

export interface TemplateUploadResponse {
  campaign_id: string
  message: string
  template_image_url?: string
  template_drive_file_id?: string
  width: number
  height: number
  config: TemplateConfig
}

export interface TemplatePreviewResponse {
  preview_data_url: string
  sample_name: string
  config: TemplateConfig
}

export interface GenerateCertificatesResponse {
  campaign_id: string
  total_participants: number
  generated_count: number
  skipped_count: number
  failed_count: number
  message: string
}

export const templateService = {
  /** Get certificate template and config for a campaign */
  getTemplate: (campaignId: string) =>
    api.get<TemplateResponse>(`/api/templates/${campaignId}`),

  /** Upload a certificate template image */
  uploadTemplate: (campaignId: string, formData: FormData) =>
    api.upload<TemplateUploadResponse>(`/api/templates/${campaignId}/upload`, formData),

  /** Save template design coordinates and typography */
  saveConfig: (campaignId: string, config: TemplateConfig) =>
    api.put<{ success: boolean; message: string; config: TemplateConfig }>(
      `/api/templates/${campaignId}/config`,
      config,
    ),

  /** Generate live sample preview */
  previewTemplate: (campaignId: string, sampleName: string, config: TemplateConfig) =>
    api.post<TemplatePreviewResponse>(`/api/templates/${campaignId}/preview`, {
      sample_name: sampleName,
      config,
    }),

  /** Bulk generate certificates in Google Shared Drive */
  generateCertificates: (campaignId: string, overrideExisting: boolean = false) =>
    api.post<GenerateCertificatesResponse>(`/api/certificates/${campaignId}/generate`, {
      campaign_id: campaignId,
      override_existing: overrideExisting,
    }),
}
