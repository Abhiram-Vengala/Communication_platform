import { ThemeProvider } from '@mui/material'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Candidate } from '../api/types'
import { ToastProvider } from '../components/Toast'
import { theme } from '../theme'
import CandidatesPage from './CandidatesPage'

const candidate = (id: number, name: string, extra: Partial<Candidate> = {}): Candidate => ({
  id,
  code: `A${id}B${id}C${id}`,
  name,
  phone: `+9198765432${id}0`,
  email: `${name.split(' ')[0].toLowerCase()}@example.com`,
  created_at: '2026-10-01T10:00:00Z',
  last_message_at: null,
  last_message_status: null,
  ...extra,
})

let db: Candidate[]
let calls: { url: string; method: string; body: any }[]

function json(data: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }))
}

function mockApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: string, init: RequestInit = {}) => {
      const url = String(input)
      const method = init.method ?? 'GET'
      const body = init.body ? JSON.parse(String(init.body)) : undefined
      calls.push({ url, method, body })

      if (url.startsWith('/api/provider-health/')) {
        return json({ status: 'operational', providers: [], stats: { sent: 0, delivered: 0, read: 0, failed: 0, pending: 0 } })
      }
      if (url.startsWith('/api/templates/')) return json({ count: 0, next: null, previous: null, results: [] })
      if (url === '/api/candidates/bulk-delete/') {
        db = db.filter((c) => !body.ids.includes(c.id))
        return json({ deleted: body.ids.length })
      }
      if (url.startsWith('/api/candidates/') && method === 'POST') {
        if (body.email === 'taken@example.com') {
          return json({ error: { code: 'validation_error', message: 'fix', fields: { email: 'A candidate with this email already exists.' } } }, 400)
        }
        const created = candidate(db.length + 10, body.name, { phone: body.phone, email: body.email })
        db = [created, ...db]
        return json(created, 201)
      }
      if (/^\/api\/candidates\/\d+\/messages\//.test(url)) return json({ count: 0, next: null, previous: null, results: [] })
      if (url.startsWith('/api/candidates/')) return json({ count: db.length, next: null, previous: null, results: db })
      if (url === '/api/messages/bulk/') {
        const messages = body.candidate_ids.map((id: number, i: number) => ({
          id: i + 1,
          candidate: db.find((c) => c.id === id),
          status: 'queued',
          failure_message: '',
          last_error: '',
          retryable: false,
          scheduled_for: null,
        }))
        return json({ id: 5, body: body.body, provider: body.provider, created_at: '', summary: { total: messages.length, pending: messages.length, succeeded: 0, failed: 0, by_status: {} }, messages }, 201)
      }
      if (url.startsWith('/api/batches/')) {
        const sent = calls.findLast((c) => c.url === '/api/messages/bulk/')!
        const messages = sent.body.candidate_ids.map((id: number, i: number) => ({
          id: i + 1,
          candidate: db.find((c) => c.id === id),
          status: i === 0 ? 'failed' : 'sent',
          failure_message: 'The phone number or email looks invalid.',
          last_error: '',
          retryable: false,
        }))
        const failed = messages.filter((m: any) => m.status === 'failed').length
        return json({ id: 5, body: sent.body.body, provider: 'whatsapp', created_at: '', summary: { total: messages.length, pending: 0, succeeded: messages.length - failed, failed, by_status: {} }, messages })
      }
      return json({ error: { code: 'not_found', message: 'nope' } }, 404)
    }),
  )
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider theme={theme}>
        <ToastProvider>
          <CandidatesPage />
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  calls = []
  db = [
    candidate(1, 'Krishna Khandelwal', { last_message_at: '2026-10-12T10:00:00Z', last_message_status: 'read' }),
    candidate(2, 'Urvashi Soni', { last_message_at: '2026-10-15T10:00:00Z', last_message_status: 'failed' }),
    candidate(3, 'Aditya Kumar'),
  ]
  mockApi()
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('CandidatesPage', () => {
  it('lists candidates with status chips and NA for never-messaged', async () => {
    renderPage()
    expect(await screen.findByText('Krishna Khandelwal')).toBeTruthy()
    expect(screen.getByTestId('status-read')).toBeTruthy()
    expect(screen.getByTestId('status-failed')).toBeTruthy()
    expect(screen.getAllByText('NA')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Send message' })).toHaveProperty('disabled', true)
  })

  it('shows the empty state when there are no candidates', async () => {
    db = []
    renderPage()
    expect(await screen.findByText('No candidates added')).toBeTruthy()
  })

  it('shows a retry option when the list fails to load', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('offline'))))
    renderPage()
    expect(await screen.findByText(/can’t reach the server|can't reach the server/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeTruthy()
  })

  it('adds a candidate: validates, normalises the phone and shows server errors', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Krishna Khandelwal')
    await user.click(screen.getByRole('button', { name: 'Add candidate' }))
    const dialog = await screen.findByRole('dialog')
    const submit = within(dialog).getByRole('button', { name: 'Add candidate' })
    expect(submit).toHaveProperty('disabled', true)

    await user.type(within(dialog).getByLabelText(/Candidate Name/), 'Taylor Swift')
    await user.type(within(dialog).getByLabelText(/Mobile Number/), '12345')
    await user.type(within(dialog).getByLabelText(/Email/), 'taken@example.com')
    await user.click(submit)
    expect(await within(dialog).findByText(/valid mobile number/i)).toBeTruthy()

    await user.clear(within(dialog).getByLabelText(/Mobile Number/))
    await user.type(within(dialog).getByLabelText(/Mobile Number/), '98765 43210')
    await user.click(submit)
    expect(await within(dialog).findByText('A candidate with this email already exists.')).toBeTruthy()

    await user.clear(within(dialog).getByLabelText(/Email/))
    await user.type(within(dialog).getByLabelText(/Email/), 'taylor@example.com')
    await user.click(submit)
    expect(await screen.findByText('Candidate added')).toBeTruthy()
    const post = calls.findLast((c) => c.method === 'POST' && c.url === '/api/candidates/')!
    expect(post.body).toEqual({ name: 'Taylor Swift', phone: '+919876543210', email: 'taylor@example.com' })
  })

  it('sends to several candidates and reports partial failure per candidate', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Krishna Khandelwal')
    await user.click(screen.getByLabelText('Select Krishna Khandelwal'))
    await user.click(screen.getByLabelText('Select Aditya Kumar'))
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    const drawer = await screen.findByRole('presentation', {}, { timeout: 2000 }).catch(() => document.body)
    expect(within(drawer as HTMLElement).getByText('2 Recipients')).toBeTruthy()
    const send = screen.getByRole('button', { name: 'Send to 2 candidates' })
    expect(send).toHaveProperty('disabled', true)
    await user.type(screen.getByLabelText('Message'), 'Interview tomorrow')
    await user.click(send)

    await waitFor(() => expect(calls.some((c) => c.url === '/api/messages/bulk/')).toBe(true))
    const request = calls.find((c) => c.url === '/api/messages/bulk/')!
    expect(request.body).toMatchObject({ candidate_ids: [1, 3], body: 'Interview tomorrow', provider: 'whatsapp' })

    expect(await screen.findByText('Some messages failed', {}, { timeout: 4000 })).toBeTruthy()
    await user.click(await screen.findByRole('button', { name: 'View details' }))
    const results = await screen.findByText('Message results')
    expect(results).toBeTruthy()
    expect(await screen.findByText('1 of 2 sent, 1 failed.')).toBeTruthy()
    expect(screen.getByText('The phone number or email looks invalid.')).toBeTruthy()
  })

  it('uses single and plural copy when deleting', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Krishna Khandelwal')
    await user.click(screen.getByLabelText('Select Krishna Khandelwal'))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Are you sure you want to delete this Candidate?')).toBeTruthy()
    expect(screen.getByText(/communication history with Krishna Khandelwal/)).toBeTruthy()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByText('Are you sure you want to delete this Candidate?')).toBeNull())

    await user.click(screen.getByLabelText('Select Urvashi Soni'))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Are you sure you want to delete 2 Candidates?')).toBeTruthy()
    await user.click(screen.getAllByRole('button', { name: 'Delete' }).at(-1)!)
    expect(await screen.findByText('Candidates deleted')).toBeTruthy()
    expect(calls.find((c) => c.url === '/api/candidates/bulk-delete/')!.body).toEqual({ ids: [1, 2] })
  })

  it('opens the history drawer with the empty state', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByText('Aditya Kumar'))
    expect(await screen.findByText('Communication history')).toBeTruthy()
    expect(await screen.findByText('No communication history')).toBeTruthy()
    expect(screen.getByText('Candidate ID: A3B3C3')).toBeTruthy()
  })
})
