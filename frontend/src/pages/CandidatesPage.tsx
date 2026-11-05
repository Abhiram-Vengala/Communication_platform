import Search from '@mui/icons-material/Search'
import { Alert, Box, Button, InputAdornment, TextField, Typography } from '@mui/material'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useBatch, useCandidates, useProviderHealth } from '../api/hooks'
import type { Batch, Candidate, CandidateFilters } from '../api/types'
import { AddCandidateDialog } from '../components/AddCandidateDialog'
import { BulkResultDialog } from '../components/BulkResultDialog'
import { CandidateTable } from '../components/CandidateTable'
import { DeleteCandidatesDialog } from '../components/DeleteCandidatesDialog'
import { HistoryDrawer } from '../components/HistoryDrawer'
import { ProviderHealth } from '../components/ProviderHealth'
import { SendMessageDrawer } from '../components/SendMessageDrawer'
import { useToast } from '../components/Toast'
import { formatDateTime } from '../utils/format'

const EMPTY_FILTERS: CandidateFilters = { search: '', name: '', phone: '', code: '', status: [], lastMessageFrom: '', lastMessageTo: '' }
const HEADER_BUTTON = { bgcolor: '#3d7edb', '&:hover': { bgcolor: '#316cc0' } }

/** Waits for a sent batch to settle, then reports how it went. Renders nothing. */
function BatchWatcher({ batchId, onDone }: { batchId: number; onDone: (batch: Batch) => void }) {
  const { data } = useBatch(batchId)
  useEffect(() => {
    if (data && data.summary.pending === 0) onDone(data)
  }, [data, onDone])
  return null
}

export default function CandidatesPage() {
  const { notify } = useToast()
  const [filters, setFilters] = useState<CandidateFilters>(EMPTY_FILTERS)
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(10)
  const [selected, setSelected] = useState<Map<number, Candidate>>(new Map())
  const [addOpen, setAddOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [sendOpen, setSendOpen] = useState(false)
  const [historyCandidate, setHistoryCandidate] = useState<Candidate | null>(null)
  const [resultBatchId, setResultBatchId] = useState<number | null>(null)
  const [tracked, setTracked] = useState<number[]>([])

  const candidates = useCandidates(filters, page, pageSize)
  const health = useProviderHealth()
  const rows = candidates.data?.results ?? []
  const total = candidates.data?.count ?? 0
  const selectedList = useMemo(() => [...selected.values()], [selected])

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((f) => (f.search === searchInput.trim() ? f : { ...f, search: searchInput.trim() }))
      setPage(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  // After deleting the last row of a page, step back instead of showing an empty page.
  useEffect(() => {
    if (candidates.data && !candidates.isPlaceholderData && rows.length === 0 && page > 0) setPage((p) => p - 1)
  }, [candidates.data, candidates.isPlaceholderData, rows.length, page])

  const hasFilters = !!(filters.search || filters.name || filters.phone || filters.code || filters.status.length || filters.lastMessageFrom || filters.lastMessageTo)
  const changeFilters = (patch: Partial<CandidateFilters>) => {
    setFilters((f) => ({ ...f, ...patch }))
    setPage(0)
  }
  const clearFilters = () => {
    setSearchInput('')
    setFilters(EMPTY_FILTERS)
    setPage(0)
  }

  const toggle = (candidate: Candidate) =>
    setSelected((current) => {
      const next = new Map(current)
      if (next.has(candidate.id)) next.delete(candidate.id)
      else next.set(candidate.id, candidate)
      return next
    })
  const togglePage = () =>
    setSelected((current) => {
      const next = new Map(current)
      const all = rows.every((r) => next.has(r.id))
      rows.forEach((r) => (all ? next.delete(r.id) : next.set(r.id, r)))
      return next
    })

  const onSent = (batch: Batch, scheduled: boolean) => {
    setSendOpen(false)
    setSelected(new Map())
    const n = batch.summary.total
    if (scheduled) {
      const when = batch.messages[0]?.scheduled_for
      notify({ title: 'Message scheduled', description: `${n === 1 ? batch.messages[0].candidate.name : `${n} candidates`} will get it on ${when ? formatDateTime(when) : 'the chosen time'}.` })
    } else {
      notify({ title: 'Sending message', description: n === 1 ? `Sending to ${batch.messages[0].candidate.name}.` : `Sending to ${n} candidates. We’ll tell you how it went.`, severity: 'info' })
      setTracked((t) => [...t, batch.id])
    }
  }

  const onBatchDone = useCallback(
    (batch: Batch) => {
      setTracked((t) => t.filter((id) => id !== batch.id))
      const { total: n, failed, succeeded } = batch.summary
      const viewResults = { actionLabel: 'View details', onAction: () => setResultBatchId(batch.id) }
      if (failed === 0) {
        notify({ title: n === 1 ? 'Message sent' : 'Messages sent', description: n === 1 ? `Your message to ${batch.messages[0].candidate.name} was sent.` : `All ${n} messages were sent.` })
      } else if (failed === n) {
        notify({
          title: n === 1 ? 'Message failed' : 'Messages failed',
          description: n === 1 ? batch.messages[0].failure_message : `None of the ${n} messages could be sent.`,
          severity: 'error',
          ...viewResults,
        })
      } else {
        notify({ title: 'Some messages failed', description: `${succeeded} sent, ${failed} failed.`, severity: 'warning', ...viewResults })
      }
    },
    [notify],
  )

  const onDeleted = (deleted: Candidate[]) => {
    setSelected(new Map())
    notify(
      deleted.length === 1
        ? { title: 'Candidate deleted', description: `${deleted[0].name} and their communication history were removed.` }
        : { title: 'Candidates deleted', description: `${deleted.length} candidates and their communication history were removed.` },
    )
  }

  const none = selected.size === 0

  return (
    <Box sx={{ height: '100vh', display: 'flex', flexDirection: 'column', bgcolor: 'background.default' }}>
      <Box component="header" sx={{ bgcolor: '#fff', minHeight: 70, px: 3, py: 1, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Typography component="h1" variant="h1">
          Candidate communication
        </Typography>
        <ProviderHealth />
        <Box sx={{ flex: 1 }} />
        <Button variant="outlined" onClick={() => setAddOpen(true)}>
          Add candidate
        </Button>
        <Button variant="contained" sx={HEADER_BUTTON} disabled={none} onClick={() => setSendOpen(true)}>
          Send message
        </Button>
        <Button variant="contained" sx={HEADER_BUTTON} disabled={none} onClick={() => setDeleteOpen(true)}>
          Delete
        </Button>
        <TextField
          size="small"
          placeholder="Search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          sx={{ width: 233 }}
          slotProps={{
            htmlInput: { 'aria-label': 'Search candidates' },
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <Search fontSize="small" />
                </InputAdornment>
              ),
            },
          }}
        />
      </Box>

      {health.data?.status === 'down' && (
        <Alert severity="warning" sx={{ mt: 1, mx: 1, borderRadius: 0 }}>
          The messaging service is unavailable right now. Messages you send will wait in the queue and go out automatically once it&rsquo;s back.
        </Alert>
      )}

      <Box sx={{ flex: 1, minHeight: 0, m: 1, bgcolor: '#fff', display: 'flex', flexDirection: 'column' }}>
        <CandidateTable
          rows={rows}
          total={total}
          loading={candidates.isLoading}
          fetching={candidates.isFetching}
          error={candidates.isError && !candidates.data ? `We couldn’t load your candidates. ${candidates.error.message}` : null}
          onRetry={() => candidates.refetch()}
          hasFilters={hasFilters}
          onClearFilters={clearFilters}
          filters={filters}
          onFilterChange={changeFilters}
          selectedIds={new Set(selected.keys())}
          onToggle={toggle}
          onTogglePage={togglePage}
          onOpenHistory={setHistoryCandidate}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onPageSizeChange={(size) => {
            setPageSize(size)
            setPage(0)
          }}
        />
      </Box>

      <AddCandidateDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onAdded={(c) => {
          setPage(0)
          notify({ title: 'Candidate added', description: `${c.name} has been added to your candidates.` })
        }}
      />
      <DeleteCandidatesDialog open={deleteOpen} candidates={selectedList} onClose={() => setDeleteOpen(false)} onDeleted={onDeleted} />
      <SendMessageDrawer open={sendOpen} recipients={selectedList} onClose={() => setSendOpen(false)} onSent={onSent} />
      <HistoryDrawer candidate={historyCandidate} onClose={() => setHistoryCandidate(null)} />
      <BulkResultDialog batchId={resultBatchId} onClose={() => setResultBatchId(null)} />
      {tracked.map((id) => (
        <BatchWatcher key={id} batchId={id} onDone={onBatchDone} />
      ))}
    </Box>
  )
}
