export type MessageStatus = 'scheduled' | 'queued' | 'sending' | 'sent' | 'delivered' | 'read' | 'failed'
export type Channel = 'whatsapp' | 'email'

export interface Candidate {
  id: number
  code: string
  name: string
  phone: string
  email: string
  created_at: string
  last_message_at: string | null
  last_message_status: MessageStatus | null
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface CandidateBrief {
  id: number
  code: string
  name: string
  phone: string
  email: string
}

export interface Message {
  id: number
  candidate: CandidateBrief
  batch_id: number | null
  body: string
  provider: Channel
  status: MessageStatus
  failure_code: string
  failure_message: string
  retryable: boolean
  last_error: string
  attempts: number
  next_attempt_at: string | null
  scheduled_for: string | null
  created_at: string
  sent_at: string | null
  delivered_at: string | null
  read_at: string | null
}

export interface BatchSummary {
  total: number
  pending: number
  succeeded: number
  failed: number
  by_status: Partial<Record<MessageStatus, number>>
}

export interface Batch {
  id: number
  body: string
  provider: Channel
  created_at: string
  summary: BatchSummary
  messages: Message[]
}

export interface MessageTemplate {
  id: number
  name: string
  body: string
}

export interface ProviderHealth {
  status: 'operational' | 'degraded' | 'down'
  providers: { name: Channel; label: string; status: 'operational' | 'degraded' | 'down'; mode: string | null }[]
  stats: { sent: number; delivered: number; read: number; failed: number; pending: number }
}

export interface CandidateFilters {
  search: string
  name: string
  phone: string
  code: string
  status: string[] // includes 'none' for never messaged
  lastMessageFrom: string
  lastMessageTo: string
}
