import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import CheckIcon from '@mui/icons-material/Check'
import CloseIcon from '@mui/icons-material/Close'
import api from '../api/client'
import errorMessage from '../api/errorMessage'
import SeverityChip from '../components/SeverityChip'

export default function PublishingPage() {
  const [attempts, setAttempts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [decision, setDecision] = useState(null) // {attempt, action}
  const [banner, setBanner] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    api
      .get('/publishing-attempts/')
      .then((res) => setAttempts(res.data.results ?? res.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  const decided = (message) => {
    setDecision(null)
    setBanner({ severity: 'success', message })
    load()
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h4">Publishing</Typography>
        <IconButton onClick={load} title="Refresh">
          <RefreshIcon />
        </IconButton>
      </Stack>

      {banner && (
        <Alert severity={banner.severity} onClose={() => setBanner(null)}>
          {banner.message}
        </Alert>
      )}
      {error && <Alert severity="error">{error}</Alert>}
      {loading && <LinearProgress />}
      {!loading && attempts.length === 0 && (
        <Typography color="text.secondary">
          No publishing attempts yet — open a service and press “Publish” on one of its versions.
        </Typography>
      )}

      {attempts.length > 0 && (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Attempt</TableCell>
                <TableCell>Version</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Reasons / outcome</TableCell>
                <TableCell>Decision</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {attempts.map((attempt) => (
                <TableRow key={attempt.id} hover>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      #{attempt.id} · {attempt.service_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {new Date(attempt.created_at).toLocaleString()}
                    </Typography>
                  </TableCell>
                  <TableCell>v{attempt.version}</TableCell>
                  <TableCell>
                    <SeverityChip value={attempt.status} />
                  </TableCell>
                  <TableCell sx={{ maxWidth: 380 }}>
                    {attempt.status === 'approved' && !attempt.comment && (
                      <Typography variant="body2" color="text.secondary">
                        No affected consumers — auto-approved.
                      </Typography>
                    )}
                    {attempt.blocked_reasons?.map((reason, i) => (
                      <Typography key={i} variant="body2" color="text.secondary">
                        • {reason}
                      </Typography>
                    ))}
                    {attempt.affected_consumers?.length > 0 && (
                      <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap', mt: 0.5 }}>
                        {attempt.affected_consumers.map((name) => (
                          <Chip key={name} size="small" color="error" variant="outlined" label={name} />
                        ))}
                      </Stack>
                    )}
                    {attempt.comment && (
                      <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                        “{attempt.comment}”
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {attempt.decided_by ? (
                      <>
                        <Typography variant="body2">{attempt.decided_by}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {attempt.decided_at ? new Date(attempt.decided_at).toLocaleString() : ''}
                        </Typography>
                      </>
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell align="right">
                    {attempt.status === 'blocked' ? (
                      <Stack direction="row" spacing={1} sx={{ justifyContent: 'flex-end' }}>
                        <Button
                          size="small"
                          color="success"
                          startIcon={<CheckIcon />}
                          onClick={() => setDecision({ attempt, action: 'approve' })}
                        >
                          Approve
                        </Button>
                        <Button
                          size="small"
                          color="error"
                          startIcon={<CloseIcon />}
                          onClick={() => setDecision({ attempt, action: 'reject' })}
                        >
                          Reject
                        </Button>
                      </Stack>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        decided
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <DecisionDialog
        decision={decision}
        onClose={() => setDecision(null)}
        onDone={decided}
      />
    </Stack>
  )
}

function DecisionDialog({ decision, onClose, onDone }) {
  const [comment, setComment] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    setComment('')
    setError(null)
  }, [decision])

  if (!decision) return null
  const { attempt, action } = decision
  const isApprove = action === 'approve'

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.post(`/publishing-attempts/${attempt.id}/${action}/`, { comment })
      onDone(
        isApprove
          ? `Attempt #${attempt.id} approved — v${attempt.version} is now published.`
          : `Attempt #${attempt.id} rejected — v${attempt.version} stays unpublished.`,
      )
    } catch (err) {
      setError(errorMessage(err, 'Decision failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={submit}>
        <DialogTitle>
          {isApprove ? 'Approve' : 'Reject'} attempt #{attempt.id} (v{attempt.version} of{' '}
          {attempt.service_name})
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            {isApprove && (
              <Alert severity="warning">
                Approving publishes this version even though {attempt.affected_consumers.length} consumer(s)
                are affected.
              </Alert>
            )}
            <TextField
              label="Reviewer comment"
              placeholder="Reviewed with the mobile team — coordinated release"
              multiline
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              autoFocus
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" color={isApprove ? 'success' : 'error'} disabled={submitting}>
            {submitting ? 'Saving…' : isApprove ? 'Approve & publish' : 'Reject'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}
