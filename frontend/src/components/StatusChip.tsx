import Check from '@mui/icons-material/Check'
import DoneAll from '@mui/icons-material/DoneAll'
import ErrorOutlined from '@mui/icons-material/ErrorOutlined'
import HourglassEmpty from '@mui/icons-material/HourglassEmpty'
import Schedule from '@mui/icons-material/Schedule'
import { Chip } from '@mui/material'
import type { ReactElement } from 'react'
import type { MessageStatus } from '../api/types'

const CONFIG: Record<MessageStatus, { label: string; bg: string; color: string; icon?: ReactElement }> = {
  scheduled: { label: 'Scheduled', bg: '#f3e5f5', color: '#6a1b9a', icon: <Schedule /> },
  queued: { label: 'Queued', bg: '#eeeeee', color: '#616161', icon: <HourglassEmpty /> },
  sending: { label: 'Sending', bg: '#eeeeee', color: '#616161', icon: <HourglassEmpty /> },
  sent: { label: 'Sent', bg: '#e3f2fd', color: '#1565c0' },
  delivered: { label: 'Delivered', bg: '#e0f2f1', color: '#00695c', icon: <DoneAll /> },
  read: { label: 'Read', bg: '#e6f4ea', color: '#2e7d32', icon: <Check /> },
  failed: { label: 'Failed', bg: '#fdeaea', color: '#d32f2f', icon: <ErrorOutlined /> },
}

/** `retrying` is a queued message that failed once and will be re-sent automatically. */
export function StatusChip({ status, retrying = false }: { status: MessageStatus; retrying?: boolean }) {
  const config = CONFIG[status]
  const label = retrying ? 'Retrying' : config.label
  return (
    <Chip
      size="small"
      label={label}
      icon={config.icon}
      data-testid={`status-${status}`}
      sx={{
        bgcolor: config.bg,
        color: config.color,
        height: 24,
        fontSize: 12,
        '& .MuiChip-icon': { color: 'inherit', fontSize: 16, ml: '8px' },
        '& .MuiChip-label': { px: config.icon ? '8px' : '10px' },
      }}
    />
  )
}
