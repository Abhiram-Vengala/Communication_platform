import Close from '@mui/icons-material/Close'
import { Alert, Box, Button, Drawer, FormControlLabel, IconButton, MenuItem, Stack, Switch, TextField, Typography } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { ApiError } from '../api/client'
import { useCreateTemplate, useSendMessages, useTemplates } from '../api/hooks'
import type { Batch, Candidate, Channel } from '../api/types'
import { toLocalInputValue, unknownPlaceholders } from '../utils/format'
import { RecipientChips } from './RecipientChips'

const MAX_LENGTH = 1600

interface Props {
  open: boolean
  recipients: Candidate[]
  onClose: () => void
  onSent: (batch: Batch, scheduled: boolean) => void
}

export function SendMessageDrawer({ open, recipients, onClose, onSent }: Props) {
  const [message, setMessage] = useState('')
  const [channel, setChannel] = useState<Channel>('whatsapp')
  const [templateId, setTemplateId] = useState('')
  const [schedule, setSchedule] = useState(false)
  const [scheduledFor, setScheduledFor] = useState('')
  const [fieldErrors, setFieldErrors] = useState<{ body?: string; scheduled_for?: string }>({})
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const send = useSendMessages()
  const templates = useTemplates()
  const createTemplate = useCreateTemplate()

  useEffect(() => {
    if (open) {
      setMessage('')
      setChannel('whatsapp')
      setTemplateId('')
      setSchedule(false)
      setScheduledFor('')
      setFieldErrors({})
      setFormError('')
      setSaving(false)
      send.reset()
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const names = useMemo(() => recipients.map((r) => r.name), [recipients])
  const count = recipients.length
  const busy = send.isPending
  const canSend = message.trim().length > 0 && count > 0 && !busy && (!schedule || !!scheduledFor)

  const validate = () => {
    const errors: typeof fieldErrors = {}
    const unknown = unknownPlaceholders(message)
    if (message.length > MAX_LENGTH) errors.body = `Messages can be up to ${MAX_LENGTH} characters.`
    else if (unknown.length) errors.body = `Unknown placeholder: ${unknown.map((p) => `{{${p}}}`).join(', ')}. Use {{name}}, {{first_name}}, {{email}} or {{phone}}.`
    if (schedule && new Date(scheduledFor).getTime() <= Date.now()) errors.scheduled_for = 'Pick a time in the future.'
    return errors
  }

  const submit = () => {
    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length) return
    setFormError('')
    send.mutate(
      {
        candidate_ids: recipients.map((r) => r.id),
        body: message.trim(),
        provider: channel,
        scheduled_for: schedule ? new Date(scheduledFor).toISOString() : null,
      },
      {
        onSuccess: (batch) => onSent(batch, schedule),
        onError: (error) => {
          if (error instanceof ApiError && Object.keys(error.fields).length) {
            setFieldErrors(error.fields)
            if (!error.fields.body && !error.fields.scheduled_for) setFormError(error.message)
          } else {
            setFormError(error.message)
          }
        },
      },
    )
  }

  const saveTemplate = () => {
    createTemplate.mutate(
      { name: templateName.trim(), body: message.trim() },
      {
        onSuccess: (template) => {
          setSaving(false)
          setTemplateName('')
          setTemplateId(String(template.id))
        },
      },
    )
  }

  const label = schedule ? 'Schedule' : count > 1 ? `Send to ${count} candidates` : 'Send'

  return (
    <Drawer anchor="right" open={open} onClose={busy ? undefined : onClose} slotProps={{ paper: { sx: { width: { xs: '100%', sm: 642 }, display: 'flex', flexDirection: 'column' } } }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 5, pt: 4, pb: 2 }}>
        <Typography sx={{ fontSize: 20, fontWeight: 700 }}>Send Message</Typography>
        <IconButton aria-label="Close" onClick={onClose} disabled={busy}>
          <Close />
        </IconButton>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', px: 5, pb: 3 }}>
        <Typography sx={{ mb: 1 }}>{count === 1 ? '1 Recipient' : `${count} Recipients`}</Typography>
        <RecipientChips names={names} />

        <Typography sx={{ mt: 4 }}>
          Message <span style={{ color: '#d32f2f' }}>*</span>
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mb: 1, color: 'text.secondary' }}>
          Type, or paste the message you want to send.
        </Typography>
        <TextField
          multiline
          rows={7}
          fullWidth
          placeholder="Type or paste here..."
          value={message}
          onChange={(e) => {
            setMessage(e.target.value)
            if (fieldErrors.body) setFieldErrors({ ...fieldErrors, body: undefined })
          }}
          error={!!fieldErrors.body}
          helperText={fieldErrors.body ?? `Personalise with {{first_name}} or {{name}}. ${message.length}/${MAX_LENGTH}`}
          sx={{ '& textarea': { resize: 'vertical !important' } }}
          slotProps={{ htmlInput: { 'aria-label': 'Message' } }}
        />

        <Stack spacing={2.5} sx={{ mt: 4 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField select size="small" label="Send via" value={channel} onChange={(e) => setChannel(e.target.value as Channel)} sx={{ flex: 1 }}>
              <MenuItem value="whatsapp">WhatsApp</MenuItem>
              <MenuItem value="email">Email</MenuItem>
            </TextField>
            <TextField
              select
              size="small"
              label="Template"
              value={templateId}
              onChange={(e) => {
                setTemplateId(e.target.value)
                const picked = templates.data?.results.find((t) => String(t.id) === e.target.value)
                if (picked) setMessage(picked.body)
              }}
              sx={{ flex: 1 }}
              helperText={templates.isError ? 'Templates could not be loaded.' : templates.data?.results.length === 0 ? 'No templates yet.' : undefined}
            >
              {(templates.data?.results ?? []).map((t) => (
                <MenuItem key={t.id} value={String(t.id)}>
                  {t.name}
                </MenuItem>
              ))}
            </TextField>
          </Stack>

          {saving ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
              <TextField
                size="small"
                autoFocus
                label="Template name"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                error={createTemplate.isError}
                helperText={createTemplate.isError ? (createTemplate.error as ApiError).fields?.name ?? (createTemplate.error as ApiError).fields?.body ?? createTemplate.error.message : undefined}
                sx={{ flex: 1 }}
              />
              <Button variant="contained" size="small" sx={{ height: 40 }} disabled={!templateName.trim() || createTemplate.isPending} onClick={saveTemplate}>
                Save
              </Button>
              <Button size="small" sx={{ height: 40 }} onClick={() => setSaving(false)}>
                Cancel
              </Button>
            </Stack>
          ) : (
            <Box>
              <Button size="small" disabled={!message.trim()} onClick={() => setSaving(true)}>
                Save as template
              </Button>
            </Box>
          )}

          <Box>
            <FormControlLabel control={<Switch checked={schedule} onChange={(e) => {
              setSchedule(e.target.checked)
              if (e.target.checked && !scheduledFor) setScheduledFor(toLocalInputValue(new Date(Date.now() + 3600_000)))
            }} />} label="Schedule for later" />
            {schedule && (
              <TextField
                size="small"
                type="datetime-local"
                fullWidth
                value={scheduledFor}
                onChange={(e) => setScheduledFor(e.target.value)}
                error={!!fieldErrors.scheduled_for}
                helperText={fieldErrors.scheduled_for}
                slotProps={{ htmlInput: { min: toLocalInputValue(new Date()) } }}
                sx={{ mt: 1 }}
              />
            )}
          </Box>
        </Stack>

        {formError && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {formError}
          </Alert>
        )}
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2, px: 5, py: 3, borderTop: '1px solid #eee' }}>
        <Button variant="outlined" onClick={onClose} disabled={busy}>
          Cancel
        </Button>
        <Button variant="contained" onClick={submit} disabled={!canSend}>
          {busy ? 'Sending...' : label}
        </Button>
      </Box>
    </Drawer>
  )
}
