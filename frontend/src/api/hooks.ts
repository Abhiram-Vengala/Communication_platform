import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request, toQuery } from './client'
import type {
  Batch,
  Candidate,
  CandidateFilters,
  Channel,
  Message,
  MessageStatus,
  MessageTemplate,
  Paginated,
  ProviderHealth,
} from './types'

const IN_FLIGHT: (MessageStatus | null)[] = ['queued', 'sending', 'sent', 'delivered']

export function useCandidates(filters: CandidateFilters, page: number, pageSize: number) {
  const query = toQuery({
    search: filters.search.trim(),
    name: filters.name.trim(),
    phone: filters.phone.trim(),
    code: filters.code.trim(),
    status: filters.status.join(','),
    last_message_from: filters.lastMessageFrom,
    last_message_to: filters.lastMessageTo,
    page: page + 1,
    page_size: pageSize,
  })
  return useQuery({
    queryKey: ['candidates', query],
    queryFn: () => request<Paginated<Candidate>>(`/candidates/${query}`),
    placeholderData: keepPreviousData,
    // Statuses change after sending (sent -> delivered -> read), so poll while anything is in flight.
    refetchInterval: (q) => (q.state.data?.results.some((c) => IN_FLIGHT.includes(c.last_message_status)) ? 4000 : false),
  })
}

export function useCreateCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; phone: string; email: string }) =>
      request<Candidate>('/candidates/', { method: 'POST', json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['candidates'] }),
  })
}

export function useDeleteCandidates() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ids: number[]) => request<{ deleted: number }>('/candidates/bulk-delete/', { method: 'POST', json: { ids } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['candidates'] }),
  })
}

export function useCandidateHistory(candidateId: number | null) {
  return useInfiniteQuery({
    queryKey: ['history', candidateId],
    enabled: candidateId !== null,
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      request<Paginated<Message>>(`/candidates/${candidateId}/messages/${toQuery({ page: pageParam, page_size: 20 })}`),
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
    refetchInterval: (q) => {
      const first = q.state.data?.pages[0]?.results ?? []
      return first.some((m) => IN_FLIGHT.includes(m.status)) ? 4000 : false
    },
  })
}

export interface SendPayload {
  candidate_ids: number[]
  body: string
  provider: Channel
  scheduled_for?: string | null
}

export function useSendMessages() {
  const qc = useQueryClient()
  return useMutation({
    // One endpoint for one or many recipients: a single send is simply a batch of one.
    mutationFn: (payload: SendPayload) => request<Batch>('/messages/bulk/', { method: 'POST', json: payload }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['candidates'] })
      qc.invalidateQueries({ queryKey: ['history'] })
    },
  })
}

export function useBatch(batchId: number | null, live = false) {
  return useQuery({
    queryKey: ['batch', batchId],
    enabled: batchId !== null,
    queryFn: () => request<Batch>(`/batches/${batchId}/`),
    refetchInterval: (q) => (live ? 3000 : q.state.data && q.state.data.summary.pending === 0 ? false : 2000),
  })
}

export function useRetryMessage() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (messageId: number) => request<Message>(`/messages/${messageId}/retry/`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['candidates'] })
      qc.invalidateQueries({ queryKey: ['history'] })
      qc.invalidateQueries({ queryKey: ['batch'] })
    },
  })
}

export function useTemplates() {
  return useQuery({
    queryKey: ['templates'],
    queryFn: () => request<Paginated<MessageTemplate>>('/templates/?page_size=100'),
  })
}

export function useCreateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; body: string }) => request<MessageTemplate>('/templates/', { method: 'POST', json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }),
  })
}

export function useProviderHealth() {
  return useQuery({
    queryKey: ['provider-health'],
    queryFn: () => request<ProviderHealth>('/provider-health/'),
    refetchInterval: 10000,
  })
}
