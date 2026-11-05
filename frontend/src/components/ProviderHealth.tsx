import { Box, Chip, Popover, Typography } from '@mui/material'
import { useState } from 'react'
import { useProviderHealth } from '../api/hooks'

const COLORS = { operational: '#2e7d32', degraded: '#ed6c02', down: '#d32f2f' }
const LABELS = { operational: 'Operational', degraded: 'Degraded', down: 'Unavailable' }

function Dot({ color }: { color: string }) {
  return <Box component="span" sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: color, display: 'inline-block' }} />
}

export function ProviderHealth() {
  const { data, isError } = useProviderHealth()
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)

  const status = data?.status
  const color = status ? COLORS[status] : '#9e9e9e'
  const label = status ? LABELS[status] : isError ? 'Status unknown' : 'Checking...'

  return (
    <>
      <Chip
        size="small"
        variant="outlined"
        clickable={!!data}
        onClick={(e) => data && setAnchor(e.currentTarget)}
        icon={<Dot color={color} />}
        label={`Messaging: ${label}`}
        sx={{ '& .MuiChip-icon': { ml: '8px' }, fontSize: 12 }}
      />
      <Popover open={!!anchor} anchorEl={anchor} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}>
        {data && (
          <Box sx={{ p: 2.5, width: 280 }}>
            <Typography sx={{ fontWeight: 700, mb: 1.5 }}>Communication service</Typography>
            {data.providers.map((p) => (
              <Box key={p.name} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
                <Dot color={COLORS[p.status]} />
                <Typography variant="body2">
                  {p.label}: {LABELS[p.status]}
                </Typography>
              </Box>
            ))}
            <Box sx={{ mt: 2, display: 'grid', gridTemplateColumns: '1fr auto', rowGap: 0.5 }}>
              {(
                [
                  ['Messages sent', data.stats.sent],
                  ['Messages delivered', data.stats.delivered],
                  ['Messages read', data.stats.read],
                  ['Messages failed', data.stats.failed],
                  ['In progress', data.stats.pending],
                ] as const
              ).map(([name, value]) => (
                <Box key={name} sx={{ display: 'contents' }}>
                  <Typography variant="body2">{name}</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {value}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        )}
      </Popover>
    </>
  )
}
