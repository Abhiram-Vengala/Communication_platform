import { describe, expect, it } from 'vitest'
import {
  formatDate,
  formatDateTime,
  formatPhone,
  initials,
  isValidEmail,
  isValidPhone,
  toE164,
  unknownPlaceholders,
} from './format'

describe('phone helpers', () => {
  it('formats Indian numbers like the design', () => {
    expect(formatPhone('+919876543210')).toBe('+91 9876543210')
    expect(formatPhone('+14155550123')).toBe('+14155550123')
  })

  it('normalises typed numbers to E.164', () => {
    expect(toE164('98765 43210')).toBe('+919876543210')
    expect(toE164('+91 98765-43210')).toBe('+919876543210')
    expect(toE164('919876543210')).toBe('+919876543210')
    expect(toE164('0044 20 7946 0958')).toBe('+442079460958')
  })

  it('validates', () => {
    expect(isValidPhone('9876543210')).toBe(true)
    expect(isValidPhone('12345')).toBe(false)
    expect(isValidPhone('+1 415 555 0123')).toBe(true)
    expect(isValidPhone('abc')).toBe(false)
  })
})

describe('other helpers', () => {
  it('validates emails', () => {
    expect(isValidEmail('a@b.co')).toBe(true)
    expect(isValidEmail('a@b')).toBe(false)
  })

  it('formats dates (local time)', () => {
    const d = new Date(2026, 9, 12, 21, 5)
    expect(formatDate(d.toISOString())).toBe('12-10-2026')
    expect(formatDateTime(d.toISOString())).toBe('12-10-2026 | 9:05 PM')
    expect(formatDateTime(new Date(2026, 0, 1, 0, 7).toISOString())).toBe('01-01-2026 | 12:07 AM')
  })

  it('builds initials', () => {
    expect(initials('Krishna Khandelwal')).toBe('KK')
    expect(initials('Madonna')).toBe('M')
  })

  it('finds unknown placeholders', () => {
    expect(unknownPlaceholders('Hi {{first_name}} {{ salary }} {{salary}}')).toEqual(['salary'])
  })
})
