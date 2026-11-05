import Close from '@mui/icons-material/Close'
import { Alert, Box, Button, CircularProgress, Divider, Drawer, IconButton, Skeleton, Typography } from '@mui/material'
import { useRef } from 'react'
import { useCandidateHistory, useRetryMessage } from '../api/hooks'
import type { Candidate, Message } from '../api/types'
import { formatDateTime, formatPhone } from '../utils/format'
import { EmptyState } from './EmptyState'
import { StatusChip } from './StatusChip'
import { useToast } from './Toast'

function HistoryEntry({ message }: { message: Message }) {
  const retry = useRetryMessage()
  const { notify } = useToast()
  const retrying = message.status === 'queued' && !!message.last_error
  const when = message.status === 'scheduled' && message.scheduled_for ? message.scheduled_for : message.created_at

  return (
    <Box sx={{ py: 2.5, borderBottom: '1px solid #c8c8c8' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.25 }}>
        <Typography sx={{ fontSize: 12, letterSpacing: 0.6, color: 'text.secondary' }}>{formatDateTime(when)}</Typography>
        <StatusChip status={message.status} retrying={retrying} />
      </Box>
      <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', fontSize: 16 }}>{message.body}</Typography>

      {message.status === 'scheduled' && message.scheduled_for && (
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
          Scheduled to send on {formatDateTime(message.scheduled_for)}
        </Typography>
      )}
      {retrying && (
        <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'text.secondary' }}>
          {message.last_error} We&rsquo;ll retry automatically (attempt {message.attempts}).
        </Typography>
      )}
      {message.status === 'failed' && (
        <Box sx={{ mt: 1.25 }}>
          <Typography variant="body2" sx={{ color: 'error.main' }}>
            {message.failure_message || 'The message couldn’t be sent.'}
          </Typography>
          {message.retryable ? (
            <Button
              size="small"
              variant="outlined"
              sx={{ mt: 1 }}
              disabled={retry.isPending}
              onClick={() =>
                retry.mutate(message.id, {
                  onError: (error) => notify({ title: 'Couldn’t retry the message', description: error.message, severity: 'error' }),
                })
              }
            >
              {retry.isPending ? 'Retrying...' : 'Retry'}
            </Button>
          ) : (
            <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'text.secondary' }}>
              This can&rsquo;t be retried. Check the candidate&rsquo;s details and send a new message.
            </Typography>
          )}
        </Box>
      )}
    </Box>
  )
}

export function HistoryDrawer({ candidate, onClose }: { candidate: Candidate | null; onClose: () => void }) {
  // Keep showing the last candidate while the drawer slides out.
  const shown = useRef<Candidate | null>(candidate)
  if (candidate) shown.current = candidate
  const current = shown.current

  const history = useCandidateHistory(candidate?.id ?? null)
  const messages = history.data?.pages.flatMap((page) => page.results) ?? []

  return (
    <Drawer anchor="right" open={!!candidate} onClose={onClose} slotProps={{ paper: { sx: { width: { xs: '100%', sm: 642 } } } }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 5, pt: 4, pb: 2 }}>
        <Typography sx={{ fontSize: 20, fontWeight: 700 }}>Communication history</Typography>
        <IconButton aria-label="Close" onClick={onClose}>
          <Close />
        </IconButton>
      </Box>

      {current && (
        <Box sx={{ px: 5, pb: 4, overflow: 'auto', flex: 1 }}>
          <Typography sx={{ fontSize: 12, color: 'text.secondary', letterSpacing: 0.5, mt: 1 }}>Candidate ID: {current.code}</Typography>
          <Typography sx={{ fontSize: 24, fontWeight: 700, mt: 1 }}>{current.name}</Typography>
          <Typography sx={{ mt: 0.5 }}>{formatPhone(current.phone)}</Typography>
          <Typography sx={{ mt: 1, mb: 3, overflowWrap: 'anywhere' }}>{current.email}</Typography>
          <Divider sx={{ borderColor: '#c8c8c8' }} />

          {history.isLoading && (
            <Box sx={{ pt: 2 }}>
              {[0, 1, 2].map((i) => (
                <Box key={i} sx={{ py: 2.5 }}>
                  <Skeleton width={140} />
                  <Skeleton height={48} />
                </Box>
              ))}
            </Box>
          )}
          {history.isError && (
            <Alert severity="error" sx={{ mt: 3 }} action={<Button color="inherit" size="small" onClick={() => history.refetch()}>Try again</Button>}>
              We couldn&rsquo;t load the communication history. {history.error.message}
            </Alert>
          )}
          {history.isSuccess && messages.length === 0 && (
            <Box sx={{ mt: 8 }}>
              <EmptyState title="No communication history" description="You have not communicated with this candidate yet. When you send them a message, it will appear here." />
            </Box>
          )}
          {messages.map((message) => (
            <HistoryEntry key={message.id} message={message} />
          ))}
          {history.hasNextPage && (
            <Box sx={{ textAlign: 'center', pt: 2 }}>
              <Button onClick={() => history.fetchNextPage()} disabled={history.isFetchingNextPage} startIcon={history.isFetchingNextPage ? <CircularProgress size={14} /> : undefined}>
                Load older messages
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Drawer>
  )
}
