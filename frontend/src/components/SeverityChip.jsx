import { Chip } from '@mui/material'

const COLORS = {
  blocker: 'error',
  major: 'warning',
  minor: 'info',
  info: 'default',
  approved: 'success',
  blocked: 'error',
  rejected: 'default',
  published: 'success',
  draft: 'default',
}

export default function SeverityChip({ value, label }) {
  return (
    <Chip
      size="small"
      color={COLORS[value] || 'default'}
      label={label ?? value}
      variant={COLORS[value] ? 'filled' : 'outlined'}
    />
  )
}
