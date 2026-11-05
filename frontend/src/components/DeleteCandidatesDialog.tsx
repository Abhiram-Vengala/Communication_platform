import Close from '@mui/icons-material/Close'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Typography } from '@mui/material'
import { useEffect } from 'react'
import { useDeleteCandidates } from '../api/hooks'
import type { Candidate } from '../api/types'

export function DeleteCandidatesDialog({
  open,
  candidates,
  onClose,
  onDeleted,
}: {
  open: boolean
  candidates: Candidate[]
  onClose: () => void
  onDeleted: (deleted: Candidate[]) => void
}) {
  const remove = useDeleteCandidates()
  useEffect(() => {
    if (open) remove.reset()
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const single = candidates.length === 1
  const confirm = () =>
    remove.mutate(
      candidates.map((c) => c.id),
      {
        onSuccess: () => {
          onDeleted(candidates)
          onClose()
        },
      },
    )

  return (
    <Dialog open={open} onClose={remove.isPending ? undefined : onClose} fullWidth maxWidth={false} slotProps={{ paper: { sx: { width: 584, maxWidth: 'calc(100% - 32px)' } } }}>
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 5, pt: 4, fontWeight: 700, fontSize: 20 }}>
        Delete Candidate
        <IconButton aria-label="Close" onClick={onClose} disabled={remove.isPending}>
          <Close />
        </IconButton>
      </DialogTitle>
      <DialogContent sx={{ px: 5, pb: 4 }}>
        <Box sx={{ pt: 1 }}>
          <Typography sx={{ fontSize: 17, mb: 0.5 }}>
            {single ? 'Are you sure you want to delete this Candidate?' : `Are you sure you want to delete ${candidates.length} Candidates?`}
          </Typography>
          <Typography variant="body2" sx={{ fontSize: 13 }}>
            {single
              ? `This action cannot be undone, and you’ll lose all communication history with ${candidates[0]?.name}.`
              : 'This action cannot be undone, and you’ll lose all communication history with these candidates.'}
          </Typography>
          {remove.isError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {remove.error.message}
            </Alert>
          )}
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 5, py: 3, borderTop: '1px solid #eee' }}>
        <Button variant="outlined" onClick={onClose} disabled={remove.isPending}>
          Cancel
        </Button>
        <Button variant="contained" color="error" onClick={confirm} disabled={remove.isPending}>
          {remove.isPending ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
