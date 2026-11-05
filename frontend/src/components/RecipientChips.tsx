import { Avatar, Box, Chip, Typography } from '@mui/material'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { initials } from '../utils/format'

const GAP = 8

/**
 * Recipient chips that flow over at most two lines. Anything that doesn't fit collapses into "+ n".
 * Measures the real layout (chip widths vary), then trims the list before the browser paints.
 */
export function RecipientChips({ names }: { names: string[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const key = names.join('\u0000')
  const [visible, setVisible] = useState(names.length)
  const [measuring, setMeasuring] = useState(true)

  useLayoutEffect(() => {
    setVisible(names.length)
    setMeasuring(true)
  }, [key]) // eslint-disable-line react-hooks/exhaustive-deps

  useLayoutEffect(() => {
    if (!measuring) return
    const chips = Array.from(ref.current?.children ?? []) as HTMLElement[]
    if (chips.length) {
      const top = chips[0].offsetTop
      const row = chips[0].offsetHeight + GAP
      const firstHidden = chips.findIndex((chip) => chip.offsetTop - top >= row * 2 - 1)
      // Leave one slot free so the "+ n" label fits at the end of line two.
      setVisible(firstHidden === -1 ? names.length : Math.max(1, firstHidden - 1))
    }
    setMeasuring(false)
  }, [measuring, names.length])

  useEffect(() => {
    const onResize = () => {
      setVisible(names.length)
      setMeasuring(true)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [names.length])

  const shown = measuring ? names : names.slice(0, visible)
  const hidden = names.length - shown.length

  return (
    <Box ref={ref} sx={{ display: 'flex', flexWrap: 'wrap', gap: `${GAP}px`, alignItems: 'center' }} data-testid="recipient-chips">
      {shown.map((name, index) => (
        <Chip
          key={`${name}-${index}`}
          label={name}
          avatar={<Avatar sx={{ fontSize: 11 }}>{initials(name)}</Avatar>}
          sx={{ bgcolor: '#eceff1', maxWidth: 220 }}
        />
      ))}
      {hidden > 0 && <Typography variant="body2">+ {hidden}</Typography>}
    </Box>
  )
}
