import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Alert,
  Button,
  IconButton,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import api from '../api/client'
import errorMessage from '../api/errorMessage'
import SeverityChip from '../components/SeverityChip'

export default function ComparisonsPage() {
  const [comparisons, setComparisons] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    api
      .get('/comparisons/')
      .then((res) => setComparisons(res.data.results ?? res.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  return (
    <Stack spacing={3}>
      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h4">Comparisons</Typography>
        <IconButton onClick={load} title="Refresh">
          <RefreshIcon />
        </IconButton>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}
      {loading && <LinearProgress />}
      {!loading && comparisons.length === 0 && (
        <Typography color="text.secondary">
          No comparisons yet — open a service, upload two spec versions and use “Compare versions”.
        </Typography>
      )}

      {comparisons.length > 0 && (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Service</TableCell>
                <TableCell>Versions</TableCell>
                <TableCell>Summary</TableCell>
                <TableCell>Breaking</TableCell>
                <TableCell>When</TableCell>
                <TableCell />
              </TableRow>
            </TableHead>
            <TableBody>
              {comparisons.map((c) => (
                <TableRow key={c.id} hover>
                  <TableCell sx={{ fontWeight: 600 }}>{c.service_name}</TableCell>
                  <TableCell>
                    v{c.base_version} → v{c.target_version}
                  </TableCell>
                  <TableCell>
                    <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
                      {(['blocker', 'major', 'minor', 'info']).map(
                        (sev) =>
                          c.summary?.[sev] > 0 && (
                            <SeverityChip key={sev} value={sev} label={`${c.summary[sev]} ${sev}`} />
                          ),
                      )}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    {c.breaking > 0 ? (
                      <SeverityChip value="blocker" label={`${c.breaking} breaking`} />
                    ) : (
                      <SeverityChip value="approved" label="non-breaking" />
                    )}
                  </TableCell>
                  <TableCell>{new Date(c.created_at).toLocaleString()}</TableCell>
                  <TableCell align="right">
                    <Tooltip title="Open detail">
                      <Button
                        size="small"
                        component={RouterLink}
                        to={`/comparisons/${c.id}`}
                        endIcon={<ChevronRightIcon />}
                      >
                        Detail
                      </Button>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Stack>
  )
}
