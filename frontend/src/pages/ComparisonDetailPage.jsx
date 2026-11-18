import { useEffect, useState } from 'react'
import { Link as RouterLink, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Chip,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import api from '../api/client'
import errorMessage from '../api/errorMessage'
import SeverityChip from '../components/SeverityChip'

export default function ComparisonDetailPage() {
  const { comparisonId } = useParams()
  const [comparison, setComparison] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get(`/comparisons/${comparisonId}/`)
      .then((res) => setComparison(res.data))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false))
  }, [comparisonId])

  if (loading) return <LinearProgress />
  if (error) return <Alert severity="error">{error}</Alert>
  if (!comparison) return null

  return (
    <Stack spacing={3}>
      <Button component={RouterLink} to="/comparisons" startIcon={<ArrowBackIcon />} sx={{ alignSelf: 'flex-start' }}>
        All comparisons
      </Button>

      <Stack>
        <Typography variant="h4">
          {comparison.service_name}: v{comparison.base_version} → v{comparison.target_version}
        </Typography>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', mt: 1 }}>
          {(['blocker', 'major', 'minor', 'info']).map(
            (sev) =>
              comparison.summary?.[sev] > 0 && (
                <SeverityChip key={sev} value={sev} label={`${comparison.summary[sev]} ${sev}`} />
              ),
          )}
          <SeverityChip
            value={comparison.breaking > 0 ? 'blocker' : 'approved'}
            label={comparison.breaking > 0 ? `${comparison.breaking} breaking` : 'non-breaking'}
          />
        </Stack>
      </Stack>

      {comparison.changes.length === 0 ? (
        <Alert severity="success">No changes detected between these versions.</Alert>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Severity</TableCell>
                <TableCell>Change</TableCell>
                <TableCell>Location</TableCell>
                <TableCell>Side</TableCell>
                <TableCell>Explanation</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {comparison.changes.map((change) => (
                <TableRow key={change.id} hover>
                  <TableCell>
                    <Stack spacing={0.5}>
                      <SeverityChip value={change.severity} />
                      {change.breaking && <Chip size="small" color="error" label="breaking" />}
                    </Stack>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {change.change_type}
                    </Typography>
                    {change.field_path && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace' }}>
                        {change.field_path}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                      {change.location}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" label={change.side} />
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">{change.explanation}</Typography>
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
