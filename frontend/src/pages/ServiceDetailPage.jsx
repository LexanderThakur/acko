import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import PublishIcon from '@mui/icons-material/Publish'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import VisibilityIcon from '@mui/icons-material/Visibility'
import api from '../api/client'
import errorMessage from '../api/errorMessage'
import SeverityChip from '../components/SeverityChip'

export default function ServiceDetailPage() {
  const { serviceId } = useParams()
  const navigate = useNavigate()

  const [service, setService] = useState(null)
  const [specs, setSpecs] = useState([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState(null)

  const [uploadOpen, setUploadOpen] = useState(false)
  const [compareOpen, setCompareOpen] = useState(false)
  const [viewingSpec, setViewingSpec] = useState(null)
  const [publishResult, setPublishResult] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([api.get(`/services/${serviceId}/`), api.get(`/services/${serviceId}/specs/`)])
      .then(([svcRes, specRes]) => {
        setService(svcRes.data)
        setSpecs(specRes.data.results ?? specRes.data)
        setPageError(null)
      })
      .catch((err) => setPageError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [serviceId])

  useEffect(load, [load])

  const attemptPublish = async (specId) => {
    try {
      const { data } = await api.post('/publishing-attempts/', { spec_version_id: specId })
      setPublishResult(data)
      load()
    } catch (err) {
      setPublishResult({ _error: errorMessage(err) })
    }
  }

  if (loading) return <LinearProgress />
  if (pageError) return <Alert severity="error">{pageError}</Alert>
  if (!service) return null

  return (
    <Stack spacing={3}>
      <Button component={RouterLink} to="/services" startIcon={<ArrowBackIcon />} sx={{ alignSelf: 'flex-start' }}>
        All services
      </Button>

      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <Stack>
          <Typography variant="h4">{service.name}</Typography>
          <Typography variant="body2" color="text.secondary">
            Owner: {service.owner_team}
            {service.description ? ` · ${service.description}` : ''}
          </Typography>
          <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
            {service.published_version ? (
              <Chip color="success" size="small" label={`published: v${service.published_version}`} />
            ) : (
              <Chip size="small" variant="outlined" label="nothing published yet" />
            )}
          </Stack>
        </Stack>
        <Stack direction="row" spacing={1}>
          <Button variant="contained" startIcon={<UploadFileIcon />} onClick={() => setUploadOpen(true)}>
            Upload spec
          </Button>
          <Button variant="outlined" startIcon={<CompareArrowsIcon />} onClick={() => setCompareOpen(true)}>
            Compare versions
          </Button>
        </Stack>
      </Stack>

      {specs.length === 0 ? (
        <Typography color="text.secondary">
          No spec versions uploaded yet — click “Upload spec” to add v1.
        </Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Version</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Title</TableCell>
                <TableCell>Uploaded</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {specs.map((spec) => (
                <TableRow key={spec.id}>
                  <TableCell sx={{ fontWeight: 600 }}>v{spec.version}</TableCell>
                  <TableCell>
                    <SeverityChip value={spec.status} />
                  </TableCell>
                  <TableCell>{spec.title || '—'}</TableCell>
                  <TableCell>{new Date(spec.created_at).toLocaleString()}</TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                      <Button size="small" startIcon={<VisibilityIcon />} onClick={() => setViewingSpec(spec.id)}>
                        View
                      </Button>
                      <Button size="small" startIcon={<PublishIcon />} onClick={() => attemptPublish(spec.id)}>
                        Publish
                      </Button>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <UploadSpecDialog open={uploadOpen} onClose={() => setUploadOpen(false)} serviceId={serviceId} onUploaded={load} />
      <CompareDialog
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
        specs={specs}
        onCompared={(comparison) => navigate(`/comparisons/${comparison.id}`)}
      />
      <SpecViewDialog serviceId={serviceId} specId={viewingSpec} onClose={() => setViewingSpec(null)} />
      <PublishResultDialog result={publishResult} onClose={() => setPublishResult(null)} />
    </Stack>
  )
}

function UploadSpecDialog({ open, onClose, serviceId, onUploaded }) {
  const [mode, setMode] = useState('paste')
  const [specText, setSpecText] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setSpecText('')
    setFile(null)
    setError(null)
    setMode('paste')
  }

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      if (mode === 'file') {
        if (!file) throw new Error('choose a .yaml/.yml/.json file first')
        const data = new FormData()
        data.append('file', file)
        await api.post(`/services/${serviceId}/specs/`, data)
      } else {
        if (!specText.trim()) throw new Error('paste the OpenAPI text first')
        await api.post(`/services/${serviceId}/specs/`, { spec_text: specText })
      }
      reset()
      onClose()
      onUploaded()
    } catch (err) {
      setError(errorMessage(err, 'Upload rejected — check the spec'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <form onSubmit={submit}>
        <DialogTitle>Upload a spec version</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <Tabs value={mode} onChange={(_, v) => setMode(v)}>
              <Tab value="paste" label="Paste text" />
              <Tab value="file" label="Upload file" />
            </Tabs>

            {mode === 'paste' ? (
              <TextField
                label="OpenAPI 3.0 YAML or JSON"
                placeholder="openapi: 3.0.3 ..."
                multiline
                rows={16}
                value={specText}
                onChange={(e) => setSpecText(e.target.value)}
                fullWidth
                slotProps={{ input: { sx: { fontFamily: 'monospace', fontSize: 13 } } }}
              />
            ) : (
              <Stack spacing={1}>
                <Button variant="outlined" component="label" startIcon={<UploadFileIcon />}>
                  {file ? file.name : 'Choose .yaml / .yml / .json file'}
                  <input
                    type="file"
                    hidden
                    accept=".yaml,.yml,.json,text/yaml,application/json"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </Button>
                <Typography variant="caption" color="text.secondary">
                  The file wins if both are provided; max 2 MB, OpenAPI 3.0.x with `info.version`.
                </Typography>
              </Stack>
            )}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            {submitting ? 'Uploading…' : 'Upload'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

function CompareDialog({ open, onClose, specs, onCompared }) {
  const [baseId, setBaseId] = useState('')
  const [targetId, setTargetId] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const { data } = await api.post('/comparisons/', {
        base_spec_id: Number(baseId),
        target_spec_id: Number(targetId),
      })
      onClose()
      onCompared(data)
    } catch (err) {
      setError(errorMessage(err, 'Comparison failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>Compare two versions</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              select
              label="Base version (old)"
              value={baseId}
              onChange={(e) => setBaseId(e.target.value)}
              required
            >
              {specs.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  v{s.version} (#{s.id})
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="Target version (new)"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              required
            >
              {specs.map((s) => (
                <MenuItem key={s.id} value={s.id}>
                  v{s.version} (#{s.id})
                </MenuItem>
              ))}
            </TextField>
            <Typography variant="caption" color="text.secondary">
              Both versions must belong to this service.
            </Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={submitting || !baseId || !targetId}>
            {submitting ? 'Comparing…' : 'Compare'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

function SpecViewDialog({ serviceId, specId, onClose }) {
  const [spec, setSpec] = useState(null)
  const [tab, setTab] = useState('spec')
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!specId) return
    setSpec(null)
    setTab('spec')
    api
      .get(`/services/${serviceId}/specs/${specId}/`)
      .then((res) => setSpec(res.data))
      .catch((err) => setError(errorMessage(err)))
  }, [serviceId, specId])

  return (
    <Dialog open={Boolean(specId)} onClose={onClose} fullWidth maxWidth="lg">
      <DialogTitle>
        Spec #{specId} {spec ? `— v${spec.version}` : ''}
      </DialogTitle>
      <DialogContent>
        {error && <Alert severity="error">{error}</Alert>}
        {spec && (
          <>
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 1 }}>
              <Tab value="spec" label="Raw spec" />
              <Tab value="contract" label="Resolved contract" />
            </Tabs>
            <TextField
              multiline
              fullWidth
              rows={22}
              value={
                tab === 'spec' ? spec.spec : JSON.stringify(spec.contract ?? {}, null, 2)
              }
              slotProps={{ input: { readOnly: true, sx: { fontFamily: 'monospace', fontSize: 12 } } }}
            />
          </>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  )
}

export function PublishResultDialog({ result, onClose }) {
  if (!result) return null
  const failed = Boolean(result._error)
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Publishing attempt — {failed ? 'failed' : result.status}</DialogTitle>
      <DialogContent>
        {failed ? (
          <Alert severity="error">{result._error}</Alert>
        ) : (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1}>
              <SeverityChip value={result.status} />
              <Chip size="small" label={`v${result.version} · ${result.service_name}`} />
            </Stack>
            {result.affected_consumers?.length > 0 && (
              <Stack>
                <Typography variant="subtitle2">Affected consumers</Typography>
                <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }}>
                  {result.affected_consumers.map((name) => (
                    <Chip key={name} size="small" color="error" variant="outlined" label={name} />
                  ))}
                </Stack>
              </Stack>
            )}
            {result.blocked_reasons?.length > 0 && (
              <Stack>
                <Typography variant="subtitle2">Reasons</Typography>
                {result.blocked_reasons.map((r, i) => (
                  <Typography key={i} variant="body2" color="text.secondary">
                    • {r}
                  </Typography>
                ))}
              </Stack>
            )}
            {result.status === 'approved' && (
              <Alert severity="success">The version is now this service's published one.</Alert>
            )}
            {result.status === 'blocked' && (
              <Alert severity="warning">
                The version stays unpublished. Review it under Publishing (approve or reject).
              </Alert>
            )}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {result.status === 'blocked' && (
          <Button component={RouterLink} to="/publishing" onClick={onClose}>
            Go to publishing
          </Button>
        )}
        <Button onClick={onClose} variant="contained">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  )
}
