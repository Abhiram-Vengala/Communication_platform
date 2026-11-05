import FilterList from '@mui/icons-material/FilterList'
import { Box, Button, Checkbox, FormControlLabel, IconButton, Popover, Stack, TextField, Typography } from '@mui/material'
import { useState } from 'react'

const STATUS_OPTIONS = [
  { value: 'sent', label: 'Sent' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'read', label: 'Read' },
  { value: 'failed', label: 'Failed' },
  { value: 'queued', label: 'Queued' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'none', label: 'No messages yet' },
]

type Props =
  | { kind: 'text'; label: string; value: string; onApply: (value: string) => void }
  | { kind: 'status'; label: string; value: string[]; onApply: (value: string[]) => void }
  | { kind: 'date'; label: string; value: [string, string]; onApply: (value: [string, string]) => void }

export function ColumnFilter(props: Props) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [text, setText] = useState('')
  const [statuses, setStatuses] = useState<string[]>([])
  const [range, setRange] = useState<[string, string]>(['', ''])

  const active =
    props.kind === 'text' ? !!props.value : props.kind === 'status' ? props.value.length > 0 : !!(props.value[0] || props.value[1])

  const open = (el: HTMLElement) => {
    if (props.kind === 'text') setText(props.value)
    if (props.kind === 'status') setStatuses(props.value)
    if (props.kind === 'date') setRange(props.value)
    setAnchor(el)
  }
  const close = () => setAnchor(null)

  const apply = () => {
    if (props.kind === 'text') props.onApply(text)
    if (props.kind === 'status') props.onApply(statuses)
    if (props.kind === 'date') props.onApply(range)
    close()
  }
  const clear = () => {
    if (props.kind === 'text') props.onApply('')
    if (props.kind === 'status') props.onApply([])
    if (props.kind === 'date') props.onApply(['', ''])
    close()
  }

  return (
    <>
      <IconButton
        size="small"
        aria-label={`Filter by ${props.label}`}
        onClick={(e) => open(e.currentTarget)}
        sx={{ color: active ? 'primary.main' : '#757575' }}
      >
        <FilterList fontSize="small" />
      </IconButton>
      <Popover open={!!anchor} anchorEl={anchor} onClose={close} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
        <Box sx={{ p: 2, width: 260 }}>
          <Typography sx={{ fontWeight: 700, mb: 1.5 }}>Filter by {props.label.toLowerCase()}</Typography>
          {props.kind === 'text' && (
            <TextField
              autoFocus
              fullWidth
              size="small"
              placeholder="Contains..."
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && apply()}
            />
          )}
          {props.kind === 'status' && (
            <Stack>
              {STATUS_OPTIONS.map((option) => (
                <FormControlLabel
                  key={option.value}
                  label={option.label}
                  control={
                    <Checkbox
                      size="small"
                      checked={statuses.includes(option.value)}
                      onChange={(_, checked) =>
                        setStatuses((current) => (checked ? [...current, option.value] : current.filter((s) => s !== option.value)))
                      }
                    />
                  }
                />
              ))}
            </Stack>
          )}
          {props.kind === 'date' && (
            <Stack spacing={1.5}>
              <TextField size="small" type="date" label="From" value={range[0]} onChange={(e) => setRange([e.target.value, range[1]])} slotProps={{ inputLabel: { shrink: true } }} />
              <TextField size="small" type="date" label="To" value={range[1]} onChange={(e) => setRange([range[0], e.target.value])} slotProps={{ inputLabel: { shrink: true } }} />
            </Stack>
          )}
          <Stack direction="row" spacing={1} sx={{ mt: 2, justifyContent: 'flex-end' }}>
            <Button size="small" onClick={clear}>
              Clear
            </Button>
            <Button size="small" variant="contained" onClick={apply}>
              Apply
            </Button>
          </Stack>
        </Box>
      </Popover>
    </>
  )
}
