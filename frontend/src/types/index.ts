/**
 * Application-wide TypeScript type definitions.
 * Phase 1: Core foundation types.
 */

// ─── User / Auth ─────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  displayName: string | null
  photoURL: string | null
  createdAt: string
}

// ─── Campaign ─────────────────────────────────────────────────────────────────

export type CampaignStatus = 'draft' | 'active' | 'processing' | 'completed' | 'cancelled'

export interface Campaign {
  id: string
  userId: string
  name: string
  eventName: string
  organization: string
  eventDate: string | null
  status: CampaignStatus
  participantCount: number
  generatedCount: number
  sentCount: number
  failedCount: number
  createdAt: string
  updatedAt: string
}

// ─── Participant ───────────────────────────────────────────────────────────────

export type ParticipantStatus = 'pending' | 'processing' | 'generated' | 'failed'

export interface Participant {
  id: string
  campaignId: string
  name: string
  email: string
  college?: string
  department?: string
  course?: string
  rollNumber?: string
  organization?: string
  event?: string
  date?: string
  status: ParticipantStatus
  certificateId?: string
  createdAt: string
}

// ─── Certificate ──────────────────────────────────────────────────────────────

export type CertificateStatus = 'pending' | 'processing' | 'generated' | 'failed'

export interface Certificate {
  id: string
  certificateId: string // e.g. CERT-2026-000001
  campaignId: string
  participantId: string
  status: CertificateStatus
  fileUrl?: string
  generatedAt?: string
  failureReason?: string
  retryCount: number
  createdAt: string
}

// ─── Email Log ────────────────────────────────────────────────────────────────

export type EmailStatus = 'pending' | 'processing' | 'sent' | 'failed' | 'retrying' | 'cancelled'

export interface EmailLog {
  id: string
  campaignId: string
  participantId: string
  certificateId: string
  status: EmailStatus
  subject: string
  sentAt?: string
  failureReason?: string
  retryCount: number
  createdAt: string
}

// ─── Template ─────────────────────────────────────────────────────────────────

export interface TemplateField {
  id: string
  variable: string // e.g. '{{name}}'
  label: string    // e.g. 'Name'
  x: number        // percentage of canvas width
  y: number        // percentage of canvas height
  fontFamily: string
  fontSize: number
  fontWeight: 'normal' | 'bold'
  fontStyle: 'normal' | 'italic'
  color: string
  alignment: 'left' | 'center' | 'right'
}

export interface CertificateTemplate {
  id: string
  campaignId: string
  imageUrl: string
  width: number   // original image width in px
  height: number  // original image height in px
  fields: TemplateField[]
  createdAt: string
  updatedAt: string
}

// ─── API Responses ───────────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T
  message?: string
}

export interface ApiError {
  detail: string
  status: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

export interface DashboardStats {
  totalCampaigns: number
  totalParticipants: number
  certificatesGenerated: number
  emailsSent: number
  emailsFailed: number
  emailsPending: number
}

// ─── Column Mapping ──────────────────────────────────────────────────────────

export interface ColumnMapping {
  name: string | null
  email: string | null
  college?: string | null
  department?: string | null
  course?: string | null
  rollNumber?: string | null
  organization?: string | null
  event?: string | null
  date?: string | null
}

export interface ParticipantImportResult {
  totalRows: number
  validRows: number
  invalidRows: number
  duplicateRows: number
  errors: ImportError[]
  preview: Participant[]
}

export interface ImportError {
  row: number
  field: string
  message: string
}

// ─── Gmail ───────────────────────────────────────────────────────────────────

export interface GmailConnection {
  id: string
  userId: string
  email: string
  isConnected: boolean
  connectedAt?: string
  expiresAt?: string
}

// ─── Report ──────────────────────────────────────────────────────────────────

export interface CampaignReport {
  campaignId: string
  campaignName: string
  eventName: string
  organization: string
  generatedAt: string
  summary: {
    total: number
    generated: number
    sent: number
    failed: number
    pending: number
  }
  rows: ReportRow[]
}

export interface ReportRow {
  participantName: string
  email: string
  certificateId?: string
  certificateStatus: CertificateStatus
  emailStatus: EmailStatus
  sentAt?: string
  failureReason?: string
  retryCount: number
}
