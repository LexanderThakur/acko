import { useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Alert,
  Box,
  Button,
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Grid,
  LinearProgress,
  Stack,
  Typography,
} from '@mui/material'
import api from '../api/client'
import errorMessage from '../api/errorMessage'
import SeverityChip from '../components/SeverityChip'

function StatCard({ title, value, to, color = 'primary' }) {
  return (
    <Card>
      <CardActionArea component={RouterLink} to={to}>
        <CardContent>
          <Typography color="text.secondary" variant="body2">
            {title}
          </Typography>
          <Typography variant="h4" color={color === 'inherit' ? undefined : `${color}.main`}>
            {value}
          </Typography>
        </CardContent>
      </CardActionArea>
    </Card>
  )
}

export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.get('/services/'),
      api.get('/consumers/'),
      api.get('/comparisons/'),
      api.get('/publishing-attempts/'),
    ])
      .then(([s, c, cmp, att]) => {
        const attempts = att.data.results ?? att.data
        setStats({
          services: s.data.results ?? s.data,
          consumers: c.data.results ?? c.data,
          comparisons: cmp.data.results ?? cmp.data,
          attempts,
        })
      })
      .catch((err) => setError(errorMessage(err)))
  }, [])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!stats) return <LinearProgress />

  const breaking = stats.comparisons.reduce((sum, cmp) => sum + (cmp.breaking || 0), 0)
  const blocked = stats.attempts.filter((a) => a.status === 'blocked')
  const published = stats.services.filter((s) => s.published_version)

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Dashboard</Typography>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Services" value={stats.services.length} to="/services" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Consumers" value={stats.consumers.length} to="/consumers" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Comparisons" value={stats.comparisons.length} to="/comparisons" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Breaking changes" value={breaking} to="/comparisons" color="error" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Published versions"
            value={`${published.length}/${stats.services.length}`}
            to="/services"
            color="success"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Blocked attempts" value={blocked.length} to="/publishing" color="warning" />
        </Grid>
      </Grid>

      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6">Recent comparisons</Typography>
        <Button component={RouterLink} to="/comparisons" size="small">
          View all
        </Button>
      </Stack>
      {stats.comparisons.length === 0 && (
        <Typography color="text.secondary">
          Nothing yet — register a service, upload two spec versions and compare them.
        </Typography>
      )}
      <Stack spacing={1}>
        {stats.comparisons.slice(0, 5).map((cmp) => (
          <Card key={cmp.id}>
            <CardActionArea component={RouterLink} to={`/comparisons/${cmp.id}`}>
              <CardContent>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                  <Typography sx={{ fontWeight: 600 }}>
                    {cmp.service_name} v{cmp.base_version} → v{cmp.target_version}
                  </Typography>
                  {(['blocker', 'major', 'minor', 'info']).map(
                    (sev) =>
                      cmp.summary?.[sev] > 0 && (
                        <SeverityChip key={sev} value={sev} label={`${cmp.summary[sev]} ${sev}`} />
                      ),
                  )}
                </Stack>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Stack>

      <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6">Publishing queue</Typography>
        <Button component={RouterLink} to="/publishing" size="small">
          View all
        </Button>
      </Stack>
      {blocked.length === 0 ? (
        <Typography color="text.secondary">No blocked attempts waiting for review.</Typography>
      ) : (
        <Stack spacing={1}>
          {blocked.map((attempt) => (
            <Card key={attempt.id}>
              <CardActionArea component={RouterLink} to="/publishing">
                <CardContent>
                  <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
                    <SeverityChip value="blocked" />
                    <Typography sx={{ fontWeight: 600 }}>
                      {attempt.service_name} v{attempt.version}
                    </Typography>
                    <Box sx={{ flexGrow: 1 }} />
                    {attempt.affected_consumers.map((name) => (
                      <Chip key={name} size="small" color="error" variant="outlined" label={name} />
                    ))}
                  </Stack>
                </CardContent>
              </CardActionArea>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
