import {
  Alert,
  Box,
  Button,
  Checkbox,
  Link,
  LinearProgress,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  Typography,
} from '@mui/material'
import type { Candidate, CandidateFilters } from '../api/types'
import { GRID_LINE, LINK_COLOR } from '../theme'
import { formatDate, formatPhone } from '../utils/format'
import { ColumnFilter } from './ColumnFilter'
import { EmptyState } from './EmptyState'
import { StatusChip } from './StatusChip'

const HEADER_H = 48
const ROW_H = 41

interface Props {
  rows: Candidate[]
  total: number
  loading: boolean
  fetching: boolean
  error: string | null
  onRetry: () => void
  hasFilters: boolean
  onClearFilters: () => void
  filters: CandidateFilters
  onFilterChange: (patch: Partial<CandidateFilters>) => void
  selectedIds: Set<number>
  onToggle: (candidate: Candidate) => void
  onTogglePage: () => void
  onOpenHistory: (candidate: Candidate) => void
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
}

const NA = <Typography component="span" sx={{ color: '#9e9e9e' }}>NA</Typography>

export function CandidateTable(p: Props) {
  const allSelected = p.rows.length > 0 && p.rows.every((r) => p.selectedIds.has(r.id))
  const someSelected = p.rows.some((r) => p.selectedIds.has(r.id))
  const cell = { borderBottom: `1px solid ${GRID_LINE}`, height: ROW_H - 1, py: 0, fontSize: 14 }
  const headCell = { bgcolor: '#f5f5f5', fontWeight: 700, borderBottom: '1px solid #bdbdbd', height: HEADER_H, py: 0, fontSize: 14 }

  const filterHeader = (label: string, filter: React.ReactNode) => (
    <TableCell sx={headCell}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 1 }}>
        {label}
        {filter}
      </Box>
    </TableCell>
  )

  const showEmpty = !p.loading && !p.error && p.total === 0

  return (
    <>
      <Box sx={{ height: 2 }}>{p.fetching && !p.loading && <LinearProgress sx={{ height: 2 }} />}</Box>
      <Box
        sx={{
          position: 'relative',
          flex: 1,
          minHeight: 0,
          overflow: 'auto',
          // The faint row lines that continue below the last row, as in the design.
          backgroundImage: `linear-gradient(to bottom, transparent ${ROW_H - 1}px, ${GRID_LINE} ${ROW_H - 1}px)`,
          backgroundSize: `100% ${ROW_H}px`,
          backgroundPosition: `0 ${HEADER_H}px`,
          backgroundRepeat: 'repeat-y',
        }}
      >
        <Table stickyHeader sx={{ tableLayout: 'fixed', minWidth: 900 }} aria-label="Candidates">
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox" sx={{ ...headCell, width: 56 }}>
                <Checkbox
                  size="small"
                  checked={allSelected}
                  indeterminate={someSelected && !allSelected}
                  disabled={p.rows.length === 0}
                  onChange={p.onTogglePage}
                  slotProps={{ input: { 'aria-label': 'Select all candidates on this page' } }}
                />
              </TableCell>
              {filterHeader('Full name', <ColumnFilter kind="text" label="Full name" value={p.filters.name} onApply={(name) => p.onFilterChange({ name })} />)}
              {filterHeader('Mobile number', <ColumnFilter kind="text" label="Mobile number" value={p.filters.phone} onApply={(phone) => p.onFilterChange({ phone })} />)}
              {filterHeader(
                'Last message',
                <ColumnFilter
                  kind="date"
                  label="Last message"
                  value={[p.filters.lastMessageFrom, p.filters.lastMessageTo]}
                  onApply={([lastMessageFrom, lastMessageTo]) => p.onFilterChange({ lastMessageFrom, lastMessageTo })}
                />,
              )}
              {filterHeader('Status', <ColumnFilter kind="status" label="Status" value={p.filters.status} onApply={(status) => p.onFilterChange({ status })} />)}
              {filterHeader('Candidate ID', <ColumnFilter kind="text" label="Candidate ID" value={p.filters.code} onApply={(code) => p.onFilterChange({ code })} />)}
            </TableRow>
          </TableHead>
          <TableBody>
            {p.loading &&
              Array.from({ length: 6 }).map((_, i) => (
                <TableRow key={`s${i}`}>
                  <TableCell padding="checkbox" sx={cell} />
                  {Array.from({ length: 5 }).map((__, j) => (
                    <TableCell key={j} sx={cell}>
                      <Skeleton width={j === 3 ? 60 : '70%'} />
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            {!p.loading &&
              p.rows.map((c) => {
                const selected = p.selectedIds.has(c.id)
                return (
                  <TableRow key={c.id} selected={selected} hover sx={{ '&.Mui-selected, &.Mui-selected:hover': { bgcolor: '#e3f1fc' } }}>
                    <TableCell padding="checkbox" sx={cell}>
                      <Checkbox size="small" checked={selected} onChange={() => p.onToggle(c)} slotProps={{ input: { 'aria-label': `Select ${c.name}` } }} />
                    </TableCell>
                    <TableCell sx={{ ...cell, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <Link
                        component="button"
                        underline="hover"
                        onClick={() => p.onOpenHistory(c)}
                        sx={{ color: LINK_COLOR, fontWeight: 700, fontSize: 14, fontFamily: 'inherit', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}
                      >
                        {c.name}
                      </Link>
                    </TableCell>
                    <TableCell sx={cell}>{formatPhone(c.phone)}</TableCell>
                    <TableCell sx={cell}>{c.last_message_at ? formatDate(c.last_message_at) : NA}</TableCell>
                    <TableCell sx={cell}>{c.last_message_status ? <StatusChip status={c.last_message_status} /> : NA}</TableCell>
                    <TableCell sx={cell}>{c.code}</TableCell>
                  </TableRow>
                )
              })}
          </TableBody>
        </Table>

        {p.error && (
          <Box sx={{ p: 3 }}>
            <Alert severity="error" action={<Button color="inherit" size="small" onClick={p.onRetry}>Try again</Button>}>
              {p.error}
            </Alert>
          </Box>
        )}
        {showEmpty && (
          <Box sx={{ position: 'absolute', left: 0, right: 0, top: HEADER_H + 40, display: 'flex', justifyContent: 'center' }}>
            {p.hasFilters ? (
              <Box sx={{ textAlign: 'center' }}>
                <EmptyState title="No candidates found" description="Nothing matches your search or filters." />
                <Button sx={{ mt: 1 }} onClick={p.onClearFilters}>Clear search and filters</Button>
              </Box>
            ) : (
              <EmptyState title="No candidates added" description="When you add a candidate, they will appear here." />
            )}
          </Box>
        )}
      </Box>
      <TablePagination
        component="div"
        count={p.total}
        page={p.page}
        rowsPerPage={p.pageSize}
        rowsPerPageOptions={[10, 25, 50]}
        showFirstButton
        showLastButton
        onPageChange={(_, page) => p.onPageChange(page)}
        onRowsPerPageChange={(e) => p.onPageSizeChange(parseInt(e.target.value, 10))}
        labelDisplayedRows={({ from, to, count }) => `${from}-${to} of ${count}`}
        sx={{ flexShrink: 0, borderTop: p.total ? 'none' : `1px solid ${GRID_LINE}`, '& .MuiTablePagination-toolbar': { pl: 3 } }}
      />
    </>
  )
}
