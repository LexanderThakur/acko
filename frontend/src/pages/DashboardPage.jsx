import { useEffect, useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import {
  Card,
  CardActionArea,
  CardContent,
  Chip,
  Grid,
  Stack,
  Typography,
} from '@mui/material'
import api from '../api/client'

function StatCard({ title, value, to, color = 'primary' }) {
  return (
    <Card>
      <CardActionArea component={RouterLink} to={to}>
        <CardContent>
          <Typography color="text.secondary" variant="body2">
            {title}
          </Typography>
          <Typography variant="h4" color={`${color}.main`}>
            {value}
          </Typography>
        </CardContent>
      </CardActionArea>
    </Card>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get('/comparisons/')
      .then((res) => setData(res.data))
      .catch((err) => setError(err.message))
  }, [])

  const comparisons = data?.results ?? []
  const breaking = comparisons.reduce((sum, c) => sum + (c.breaking || 0), 0)

  return (
    <Stack spacing={3}>
      <Typography variant="h4">Dashboard</Typography>

      {error && <Typography color="error">Failed to load: {error}</Typography>}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Services" value="→" to="/services" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Consumers" value="→" to="/consumers" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Comparisons" value={data?.count ?? '…'} to="/publishing" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <StatCard title="Breaking changes" value={breaking} to="/publishing" color="error" />
        </Grid>
      </Grid>

      <Typography variant="h6">Recent comparisons</Typography>
      {comparisons.length === 0 && !error && (
        <Typography color="text.secondary">
          No comparisons yet — register a service, upload two spec versions, then compare them.
        </Typography>
      )}
      <Stack spacing={1}>
        {comparisons.slice(0, 5).map((c) => (
          <Card key={c.id}>
            <CardContent>
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                <Typography sx={{ fontWeight: 600 }}>
                  {c.service_name} {c.base_version} → {c.target_version}
                </Typography>
                {c.summary.blocker > 0 && (
                  <Chip label={`${c.summary.blocker} blocker`} color="error" size="small" />
                )}
                {c.summary.major > 0 && (
                  <Chip label={`${c.summary.major} major`} color="warning" size="small" />
                )}
                {c.summary.minor > 0 && (
                  <Chip label={`${c.summary.minor} minor`} color="info" size="small" />
                )}
                {c.summary.info > 0 && <Chip label={`${c.summary.info} info`} size="small" />}
              </Stack>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Stack>
  )
}
