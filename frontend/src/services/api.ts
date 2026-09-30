/**
 * Authenticated API client for CertFlow backend.
 *
 * Every protected request automatically attaches the Firebase ID token
 * via the Authorization: Bearer <token> header.
 *
 * Token refresh is handled by Firebase — if the token is close to expiry,
 * Firebase automatically fetches a fresh one before we read it.
 *
 * Usage:
 *   import { api } from '@/services/api'
 *   const campaigns = await api.get<Campaign[]>('/api/campaigns/')
 */

import { auth } from '@/lib/firebase'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ─── Error Type ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail)
    this.name = 'ApiError'
  }

  get isUnauthorized() { return this.status === 401 }
  get isForbidden() { return this.status === 403 }
  get isNotFound() { return this.status === 404 }
  get isServerError() { return this.status >= 500 }
}

// ─── Token Injection ──────────────────────────────────────────────────────────

/**
 * Get a fresh Firebase ID token from the currently signed-in user.
 * Returns null if no user is authenticated.
 *
 * Firebase automatically refreshes the token if it's within 5 minutes of expiry.
 */
async function getAuthToken(): Promise<string | null> {
  const user = auth.currentUser
  if (!user) return null
  try {
    return await user.getIdToken()
  } catch {
    // Token refresh failed (e.g. network error) — return null
    return null
  }
}

// ─── Core Request ─────────────────────────────────────────────────────────────

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  skipAuth = false,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (!skipAuth) {
    const token = await getAuthToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
  }

  const url = `${API_BASE_URL}${endpoint}`

  const response = await fetch(url, { ...options, headers })

  if (!response.ok) {
    let detail = `Request failed: ${response.status} ${response.statusText}`
    try {
      const errorBody = await response.json()
      detail = errorBody.detail ?? errorBody.message ?? detail
    } catch {
      // Couldn't parse error body
    }
    throw new ApiError(response.status, detail)
  }

  // Handle empty 204 responses
  if (response.status === 204) {
    return undefined as unknown as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  if (!contentType.includes('application/json')) {
    return {} as T
  }

  return response.json() as Promise<T>
}

// ─── File Upload ──────────────────────────────────────────────────────────────

async function uploadFile<T>(endpoint: string, formData: FormData): Promise<T> {
  const token = await getAuthToken()
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    let detail = 'Upload failed'
    try {
      const errorBody = await response.json()
      detail = errorBody.detail ?? detail
    } catch { /* empty */ }
    throw new ApiError(response.status, detail)
  }

  return response.json() as Promise<T>
}

// ─── Public API ───────────────────────────────────────────────────────────────

export const api = {
  /** GET request — authenticated */
  get: <T>(endpoint: string) =>
    request<T>(endpoint, { method: 'GET' }),

  /** GET request — no auth header */
  getPublic: <T>(endpoint: string) =>
    request<T>(endpoint, { method: 'GET' }, true),

  /** POST with JSON body */
  post: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: 'POST',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    }),

  /** PUT with JSON body */
  put: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: 'PUT',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    }),

  /** PATCH with JSON body */
  patch: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: 'PATCH',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    }),

  /** DELETE */
  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: 'DELETE' }),

  /** Multipart file upload */
  upload: <T>(endpoint: string, formData: FormData) =>
    uploadFile<T>(endpoint, formData),
}

export { API_BASE_URL }
