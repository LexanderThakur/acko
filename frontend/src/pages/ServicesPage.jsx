import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import api from '../api/client'
import errorMessage from '../api/errorMessage'

export default function ServicesPage() {
  const [services, setServices] = useState([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState(null)
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  const load = useCallback(() => {
    setLoading(true)
    api
      .get('/services/')
      .then((res) => setServices(res.data.results ?? res.data))
      .catch((err) => setPageError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h4">Services</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          Register service
        </Button>
      </Stack>

      {pageError && <Alert severity="error">{pageError}</Alert>}
      {loading && <Typography color="text.secondary">Loading…</Typography>}
      {!loading && services.length === 0 && (
        <Typography color="text.secondary">
          No services registered yet — click “Register service” to add the first API provider.
        </Typography>
      )}

      <Grid container spacing={2}>
        {services.map((svc) => (
          <Grid key={svc.id} size={{ xs: 12, sm: 6, md: 4 }}>
            <Card>
              <CardActionArea component={RouterLink} to={`/services/${svc.id}`}>
                <CardContent>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {svc.name}
                    </Typography>
                    {svc.published_version ? (
                      <Chip size="small" color="success" label={`v${svc.published_version} published`} />
                    ) : (
                      <Chip size="small" label="nothing published" variant="outlined" />
                    )}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    Owner: {svc.owner_team}
                  </Typography>
                  {svc.description && (
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {svc.description}
                    </Typography>
                  )}
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>

      <RegisterServiceDialog
        open={open}
        onClose={() => setOpen(false)}
        onCreated={(svc) => {
          setOpen(false)
          navigate(`/services/${svc.id}`)
        }}
        onReload={load}
      />
    </Stack>
  )
}

function RegisterServiceDialog({ open, onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', owner_team: '', description: '' })
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const change = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const { data } = await api.post('/services/', form)
      onCreated(data)
    } catch (err) {
      setError(errorMessage(err, 'Could not register the service'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>Register a service</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              label="Service name"
              placeholder="quote-api"
              value={form.name}
              onChange={change('name')}
              required
              autoFocus
            />
            <TextField
              label="Owner team"
              placeholder="Quotes team"
              value={form.owner_team}
              onChange={change('owner_team')}
              required
            />
            <TextField
              label="Description (optional)"
              multiline
              rows={2}
              value={form.description}
              onChange={change('description')}
            />
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
