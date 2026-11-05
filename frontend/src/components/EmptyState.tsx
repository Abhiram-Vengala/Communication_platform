import { Box, Typography } from '@mui/material'

function Illustration() {
  return (
    <svg width="220" height="150" viewBox="0 0 220 150" role="img" aria-label="Nothing here yet">
      <ellipse cx="110" cy="128" rx="80" ry="10" fill="#e8eef7" />
      <path d="M40 96 L110 120 L170 96 L100 72 Z" fill="#b6d4f2" />
      <path d="M40 96 L110 120 L110 128 L40 104 Z" fill="#8fb8e3" />
      <path d="M110 120 L170 96 L170 104 L110 128 Z" fill="#5f9bd8" />
      <circle cx="78" cy="94" r="7" fill="#fff" />
      <path d="M66 106 Q78 96 90 106" fill="#fff" />
      <rect x="100" y="88" width="34" height="3" rx="1.5" fill="#fff" />
      <rect x="100" y="96" width="26" height="3" rx="1.5" fill="#fff" />
      <path d="M128 52 q8 -26 16 0 q-8 6 -16 0z" fill="#4a90e2" />
      <path d="M132 50 q4 -30 8 0z" fill="#2f6fbf" />
      <rect x="126" y="52" width="20" height="18" rx="3" fill="#fff" stroke="#9ec3ec" />
      <circle cx="82" cy="116" r="12" fill="none" stroke="#1f4e8c" strokeWidth="4" />
      <line x1="72" y1="124" x2="56" y2="136" stroke="#1f4e8c" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', px: 3 }}>
      <Illustration />
      <Typography sx={{ fontWeight: 700, mt: 2 }}>{title}</Typography>
      <Typography variant="body2" sx={{ maxWidth: 360, fontSize: 15 }}>
        {description}
      </Typography>
    </Box>
  )
}
