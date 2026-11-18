import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Grid,
  IconButton,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import RefreshIcon from '@mui/icons-material/Refresh'
import api from '../api/client'
import errorMessage from '../api/errorMessage'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

const EMPTY_USE = { provider: '', method: 'GET', path: '', sends: '', reads: '' }

export default function ConsumersPage() {
  const [consumers, setConsumers] = useState([])
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([api.get('/consumers/'), api.get('/services/')])
      .then(([cRes, sRes]) => {
        setConsumers(cRes.data.results ?? cRes.data)
        setServices(sRes.data.results ?? sRes.data)
        setError(null)
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h4">Consumers</Typography>
        <Stack direction="row" spacing={1}>
          <IconButton onClick={load} title="Refresh">
            <RefreshIcon />
          </IconButton>
          <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
            Register consumer
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {loading && <LinearProgress />}
      {!loading && consumers.length === 0 && (
        <Typography color="text.secondary">
          No consumers registered yet. A consumer declares which provider endpoints it calls and
          which fields it sends/reads — that's what powers impact analysis.
        </Typography>
      )}

      <Grid container spacing={2}>
        {consumers.map((consumer) => (
          <Grid key={consumer.id} size={{ xs: 12, md: 6 }}>
            <Stack spacing={1} sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 2 }}>
              <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="h6">{consumer.name}</Typography>
                <Chip size="small" variant="outlined" label={`team: ${consumer.team}`} />
              </Stack>
              <Divider />
              {consumer.uses.length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No declared uses.
                </Typography>
              )}
              {consumer.uses.map((use) => (
                <Stack key={use.id} spacing={0.5}>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                    <Chip size="small" color="primary" label={use.method} sx={{ minWidth: 64 }} />
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {use.provider}
                      {use.path}
                    </Typography>
                  </Stack>
                  <Typography variant="caption" color="text.secondary">
                    sends: {use.sends.length ? use.sends.join(', ') : '—'} · reads:{' '}
                    {use.reads.length ? use.reads.join(', ') : '—'}
                  </Typography>
                </Stack>
              ))}
            </Stack>
          </Grid>
        ))}
      </Grid>

      <RegisterConsumerDialog open={open} onClose={() => setOpen(false)} services={services} onSaved={load} />
    </Stack>
  )
}

function RegisterConsumerDialog({ open, onClose, services, onSaved }) {
  const [name, setName] = useState('')
  const [team, setTeam] = useState('')
  const [uses, setUses] = useState([{ ...EMPTY_USE }])
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const setUse = (index, field, value) =>
    setUses((list) => list.map((u, i) => (i === index ? { ...u, [field]: value } : u)))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const payload = {
        consumer: name,
        team,
        uses: uses.map((u) => ({
          provider: u.provider,
          method: u.method,
          path: u.path,
          sends: u.sends.split(',').map((s) => s.trim()).filter(Boolean),
          reads: u.reads.split(',').map((s) => s.trim()).filter(Boolean),
        })),
      }
      await api.post('/consumers/', payload)
      setName('')
      setTeam('')
      setUses([{ ...EMPTY_USE }])
      onClose()
      onSaved()
    } catch (err) {
      setError(errorMessage(err, 'Registration failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <form onSubmit={submit}>
        <DialogTitle>Register a consumer</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <Stack direction="row" spacing={2}>
              <TextField
                label="Consumer name"
                placeholder="mobile-app"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                fullWidth
              />
              <TextField
                label="Team"
                placeholder="Mobile"
                value={team}
                onChange={(e) => setTeam(e.target.value)}
                required
                fullWidth
              />
            </Stack>

            <Typography variant="subtitle2">Declared uses</Typography>
            {uses.map((use, index) => (
              <Stack key={index} spacing={1.5} sx={{ p: 1.5, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                  <TextField
                    select
                    label="Provider"
                    value={use.provider}
                    onChange={(e) => setUse(index, 'provider', e.target.value)}
                    sx={{ minWidth: 160 }}
                    required
                  >
                    {services.map((s) => (
                      <MenuItem key={s.id} value={s.name}>
                        {s.name}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select
                    label="Method"
                    value={use.method}
                    onChange={(e) => setUse(index, 'method', e.target.value)}
                    sx={{ minWidth: 110 }}
                  >
                    {METHODS.map((m) => (
                      <MenuItem key={m} value={m}>
                        {m}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    label="Path"
                    placeholder="/quotes/{id}"
                    value={use.path}
                    onChange={(e) => setUse(index, 'path', e.target.value)}
                    required
                    fullWidth
                    slotProps={{ input: { sx: { fontFamily: 'monospace' } } }}
                  />
                  <IconButton
                    onClick={() => setUses((list) => list.filter((_, i) => i !== index))}
                    disabled={uses.length === 1}
                    title="Remove use"
                  >
                    <DeleteIcon />
                  </IconButton>
                </Stack>
                <Stack direction="row" spacing={1.5}>
                  <TextField
                    label="Sends (comma separated)"
                    placeholder="vehicle.make, rider.age"
                    value={use.sends}
                    onChange={(e) => setUse(index, 'sends', e.target.value)}
                    fullWidth
                  />
                  <TextField
                    label="Reads (comma separated)"
                    placeholder="premium.total, status"
                    value={use.reads}
                    onChange={(e) => setUse(index, 'reads', e.target.value)}
                    fullWidth
                  />
                </Stack>
              </Stack>
            ))}
            <Button
              startIcon={<AddIcon />}
              onClick={() => setUses((list) => [...list, { ...EMPTY_USE }])}
              sx={{ alignSelf: 'flex-start' }}
            >
              Add use
            </Button>
            <Typography variant="caption" color="text.secondary">
              Field paths use dots for nesting and [] for array items, e.g. premium.breakdown[].amount.
              Re-registering an existing consumer name replaces its uses.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            {submitting ? 'Registering…' : 'Register'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
