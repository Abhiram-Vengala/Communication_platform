const pad = (n: number) => String(n).padStart(2, '0')

/** "+919876543210" -> "+91 9876543210" (as in the design). Other numbers are shown as stored. */
export function formatPhone(e164: string): string {
  const match = /^\+91(\d{10})$/.exec(e164)
  return match ? `+91 ${match[1]}` : e164
}

/**
 * Turn what a recruiter types into E.164 for the API.
 * 10 digits are assumed to be Indian numbers (+91); anything else must carry its country code.
 */
export function toE164(raw: string): string {
  const cleaned = raw.replace(/[\s\-().]/g, '')
  if (cleaned.startsWith('+')) return cleaned
  if (cleaned.startsWith('00')) return `+${cleaned.slice(2)}`
  if (/^\d{10}$/.test(cleaned)) return `+91${cleaned}`
  if (/^91\d{10}$/.test(cleaned)) return `+${cleaned}`
  return cleaned
}

export function isValidPhone(raw: string): boolean {
  return /^\+[1-9]\d{7,14}$/.test(toE164(raw))
}

export function isValidEmail(value: string): boolean {
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())
}

/** 12-10-2026 */
export function formatDate(iso: string): string {
  const d = new Date(iso)
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`
}

/** 9:47 AM */
export function formatTime(iso: string): string {
  const d = new Date(iso)
  const hours = d.getHours()
  return `${hours % 12 || 12}:${pad(d.getMinutes())} ${hours >= 12 ? 'PM' : 'AM'}`
}

export function formatDateTime(iso: string): string {
  return `${formatDate(iso)} | ${formatTime(iso)}`
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}

/** Value for <input type="datetime-local"> */
export function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

const PLACEHOLDERS = ['name', 'first_name', 'email', 'phone']
export function unknownPlaceholders(body: string): string[] {
  const found = [...body.matchAll(/\{\{\s*(\w+)\s*\}\}/g)].map((m) => m[1])
  return [...new Set(found.filter((p) => !PLACEHOLDERS.includes(p)))]
}
