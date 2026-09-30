import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { cn, formatDate, isValidEmail, getInitials, formatFileSize, truncate } from '@/lib/utils'

// ─── Utils Tests ──────────────────────────────────────────────────────────────

describe('cn (class name merger)', () => {
  it('merges class names correctly', () => {
    expect(cn('foo', 'bar')).toBe('foo bar')
  })

  it('deduplicates conflicting Tailwind classes', () => {
    const result = cn('bg-red-500', 'bg-blue-500')
    expect(result).toBe('bg-blue-500')
  })

  it('handles conditional classes', () => {
    expect(cn('base', { 'active': true, 'inactive': false })).toBe('base active')
  })

  it('handles undefined and null', () => {
    expect(cn('base', undefined, null, 'extra')).toBe('base extra')
  })
})

describe('isValidEmail', () => {
  it('accepts valid emails', () => {
    expect(isValidEmail('user@example.com')).toBe(true)
    expect(isValidEmail('user.name+tag@domain.co.uk')).toBe(true)
    expect(isValidEmail('test123@gmail.com')).toBe(true)
  })

  it('rejects invalid emails', () => {
    expect(isValidEmail('notanemail')).toBe(false)
    expect(isValidEmail('@nodomain.com')).toBe(false)
    expect(isValidEmail('user@')).toBe(false)
    expect(isValidEmail('')).toBe(false)
  })
})

describe('getInitials', () => {
  it('returns initials for a full name', () => {
    expect(getInitials('Jane Doe')).toBe('JD')
    expect(getInitials('John')).toBe('J')
  })

  it('takes first two words', () => {
    expect(getInitials('Alice Bob Charlie')).toBe('AB')
  })

  it('uppercases initials', () => {
    expect(getInitials('jane doe')).toBe('JD')
  })
})

describe('truncate', () => {
  it('does not truncate short strings', () => {
    expect(truncate('hello', 10)).toBe('hello')
  })

  it('truncates long strings with ellipsis', () => {
    expect(truncate('hello world', 5)).toBe('hello...')
  })
})

describe('formatFileSize', () => {
  it('formats bytes', () => {
    expect(formatFileSize(0)).toBe('0 Bytes')
    expect(formatFileSize(1024)).toBe('1 KB')
    expect(formatFileSize(1048576)).toBe('1 MB')
  })
})

describe('formatDate', () => {
  it('formats an ISO date string', () => {
    const result = formatDate('2026-09-30')
    expect(result).toMatch(/Sep/)
    expect(result).toMatch(/2026/)
  })
})

// ─── Component Smoke Tests ────────────────────────────────────────────────────

// Minimal test to verify React renders without crashing
describe('NotFoundPage', async () => {
  const { default: NotFoundPage } = await import('@/pages/NotFoundPage')

  it('renders without crashing', () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    )
    expect(screen.getByText('404')).toBeDefined()
    expect(screen.getByText('Page not found')).toBeDefined()
  })
})

describe('LandingPage', async () => {
  const { default: LandingPage } = await import('@/pages/LandingPage')

  it('renders hero section', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )
    // Multiple "CertFlow" instances exist — use getAllByText
    const elements = screen.getAllByText(/CertFlow/)
    expect(elements.length).toBeGreaterThan(0)
  })

  it('has sign in link', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    )
    const signInLink = screen.getByText('Sign In')
    expect(signInLink).toBeDefined()
  })
})
