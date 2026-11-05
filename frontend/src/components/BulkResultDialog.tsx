import Close from '@mui/icons-material/Close'
import { Alert, Box, Button, Dialog, DialogContent, DialogTitle, IconButton, LinearProgress, Table, TableBody, TableCell, TableHead, TableRow, Typography } from '@mui/material'
import { useBatch, useRetryMessage } from '../api/hooks'
import { StatusChip } from './StatusChip'
import { useToast } from './Toast'

/** Per-candidate outcome of a send. Updates live while messages are still moving. */
export function BulkResultDialog({ batchId, onClose }: { batchId: number | null; onClose: () => void }) {
  const batch = useBatch(batchId, true)
  const retry = useRetryMessage()
  const { notify } = useToast()
  const data = batch.data
  const summary = data?.summary

  return (
    <Dialog open={batchId !== null} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 4, pt: 3, fontWeight: 700, fontSize: 20 }}>
        Message results
        <IconButton aria-label="Close" onClick={onClose}>
          <Close />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ px: 4, pb: 3 }}>
        {batch.isError && <Alert severity="error">We couldn&rsquo;t load the results. {batch.error.message}</Alert>}
        {!data && !batch.isError && <LinearProgress />}
        {data && summary && (
          <>
            <Typography sx={{ mb: 2 }}>
              {summary.succeeded} of {summary.total} sent
              {summary.failed > 0 && `, ${summary.failed} failed`}
              {summary.pending > 0 && `, ${summary.pending} still sending`}.
            </Typography>
            <Box sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Candidate</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Details</TableCell>
                    <TableCell />
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.messages.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell>{m.candidate.name}</TableCell>
                      <TableCell>
                        <StatusChip status={m.status} retrying={m.status === 'queued' && !!m.last_error} />
                      </TableCell>
                      <TableCell sx={{ color: m.status === 'failed' ? 'error.main' : 'text.secondary', fontSize: 13 }}>
                        {m.status === 'failed'
                          ? m.failure_message
                          : m.status === 'queued' && m.last_error
                            ? `${m.last_error} Retrying automatically.`
                            : ''}
                      </TableCell>
                      <TableCell align="right">
                        {m.status === 'failed' && m.retryable && (
                          <Button
                            size="small"
                            disabled={retry.isPending}
                            onClick={() => retry.mutate(m.id, { onError: (e) => notify({ title: 'Couldn’t retry the message', description: e.message, severity: 'error' }) })}
                          >
                            Retry
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
