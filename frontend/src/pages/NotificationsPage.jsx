import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import DeleteIcon from '@mui/icons-material/Delete'
import api from '../api/client'
import errorMessage from '../api/errorMessage'

const EVENT_COLORS = {
  'publish.approved': 'success',
  'publish.blocked': 'error',
  'publish.rejected': 'warning',
}

export default function NotificationsPage() {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    api
      .get('/webhook-events/')
      .then((res) => setEvents(res.data.results ?? res.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  const clear = async () => {
    await api.delete('/webhook-events/')
    load()
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h4">Notifications</Typography>
        <Stack direction="row" spacing={1}>
          <IconButton onClick={load} title="Refresh">
            <RefreshIcon />
          </IconButton>
          <Button startIcon={<DeleteIcon />} color="error" onClick={clear} disabled={events.length === 0}>
            Clear
          </Button>
        </Stack>
      </Stack>

      <Typography variant="body2" color="text.secondary">
        Every publishing decision is POSTed to the built-in receiver
        (<code>/api/webhook-events/receive/</code>) — this is what an external webhook consumer
        would receive.
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}
      {loading && <LinearProgress />}
      {!loading && events.length === 0 && (
        <Typography color="text.secondary">No notifications received yet.</Typography>
      )}

      <Stack spacing={1.5}>
        {events.map((event) => (
          <Box key={event.id} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Chip
                size="small"
                color={EVENT_COLORS[event.body?.event] || 'default'}
                label={event.body?.event || 'unknown'}
              />
              {event.body?.service && (
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {event.body.service} v{event.body.version}
                </Typography>
              )}
              {event.body?.affected_consumers?.length > 0 && (
                <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
                  {event.body.affected_consumers.map((name) => (
                    <Chip key={name} size="small" color="error" variant="outlined" label={name} />
                  ))}
                </Stack>
              )}
              <Box sx={{ flexGrow: 1 }} />
              <Typography variant="caption" color="text.secondary">
                #{event.id} · {new Date(event.received_at).toLocaleString()}
              </Typography>
            </Stack>
            {event.body?.blocked_reasons?.length > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                {event.body.blocked_reasons.join(' · ')}
              </Typography>
            )}
            <Box
              component="pre"
              sx={{
                mt: 1,
                mb: 0,
                fontSize: 11,
                fontFamily: 'monospace',
                overflow: 'auto',
                color: 'text.secondary',
              }}
            >
              {JSON.stringify(event.body, null, 2)}
            </Box>
          </Box>
        ))}
      </Stack>
    </Stack>
  )
}
