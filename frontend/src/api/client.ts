const BASE = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? '/api'

export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>

  constructor(message: string, status = 0, code = 'error', fields: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

function flattenFields(raw: unknown): Record<string, string> {
  if (!raw || typeof raw !== 'object') return {}
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    out[key] = Array.isArray(value) ? String(value[0]) : String(value)
  }
  return out
}

export async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...rest,
      headers: { ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    })
  } catch {
    throw new ApiError("We can't reach the server. Check your connection and try again.", 0, 'network')
  }

  if (response.status === 204) return undefined as T
  let data: any = null
  try {
    data = await response.json()
  } catch {
    /* non-JSON body */
  }
  if (!response.ok) {
    const error = data?.error
    throw new ApiError(
      error?.message ?? 'Something went wrong. Please try again.',
      response.status,
      error?.code ?? 'error',
      flattenFields(error?.fields),
    )
  }
  return data as T
}

export function toQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}
