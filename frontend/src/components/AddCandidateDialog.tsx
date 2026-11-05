import Close from '@mui/icons-material/Close'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Stack, TextField } from '@mui/material'
import { useEffect, useState } from 'react'
import { ApiError } from '../api/client'
import { useCreateCandidate } from '../api/hooks'
import type { Candidate } from '../api/types'
import { isValidEmail, isValidPhone, toE164 } from '../utils/format'

type Errors = Partial<Record<'name' | 'phone' | 'email', string>>

export function AddCandidateDialog({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: (candidate: Candidate) => void }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [formError, setFormError] = useState('')
  const create = useCreateCandidate()

  useEffect(() => {
    if (open) {
      setName('')
      setPhone('')
      setEmail('')
      setErrors({})
      setFormError('')
      create.reset()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const validate = (): Errors => {
    const next: Errors = {}
    if (name.trim().length < 2) next.name = 'Enter the candidate’s full name.'
    if (!isValidPhone(phone)) next.phone = 'Enter a valid mobile number. Add the country code if it isn’t +91.'
    if (!isValidEmail(email)) next.email = 'Enter a valid email address.'
    return next
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const found = validate()
    setErrors(found)
    if (Object.keys(found).length) return
    setFormError('')
    create.mutate(
      { name: name.trim(), phone: toE164(phone), email: email.trim() },
      {
        onSuccess: (candidate) => {
          onAdded(candidate)
          onClose()
        },
        onError: (error) => {
          if (error instanceof ApiError && Object.keys(error.fields).length) {
            setErrors(error.fields as Errors)
          } else {
            setFormError(error.message)
          }
        },
      },
    )
  }

  const canSubmit = name.trim() && phone.trim() && email.trim() && !create.isPending

  return (
    <Dialog open={open} onClose={create.isPending ? undefined : onClose} fullWidth maxWidth={false} slotProps={{ paper: { sx: { width: 584, maxWidth: 'calc(100% - 32px)' } } }}>
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 5, pt: 4, fontWeight: 700, fontSize: 20 }}>
          Add Candidate
          <IconButton aria-label="Close" onClick={onClose} disabled={create.isPending}>
            <Close />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ px: 5, pt: '16px !important', pb: 4 }}>
          <Stack spacing={4}>
            {formError && <Alert severity="error">{formError}</Alert>}
            <TextField label="Candidate Name" required autoFocus value={name} onChange={(e) => setName(e.target.value)} error={!!errors.name} helperText={errors.name} />
            <TextField
              label="Mobile Number"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              error={!!errors.phone}
              helperText={errors.phone ?? 'Use +91 for India. For other countries, include the country code.'}
              slotProps={{ htmlInput: { inputMode: 'tel' } }}
            />
            <TextField label="Email" required type="email" value={email} onChange={(e) => setEmail(e.target.value)} error={!!errors.email} helperText={errors.email} />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 5, py: 3, borderTop: '1px solid #eee' }}>
          <Button variant="outlined" onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={!canSubmit}>
            {create.isPending ? 'Adding...' : 'Add candidate'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  )
}
