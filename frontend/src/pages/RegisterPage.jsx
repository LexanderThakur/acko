import { Field, Formik } from 'formik'
import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import * as Yup from 'yup'
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Link,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import { useAuth } from '../auth/AuthContext'

const schema = Yup.object({
  username: Yup.string().min(3, 'At least 3 characters').required('Required'),
  password: Yup.string().min(8, 'At least 8 characters').required('Required'),
  email: Yup.string().email('Invalid email'),
})

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState(null)

  return (
    <Card sx={{ maxWidth: 420, mx: 'auto', mt: 10 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Create your account
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Register to manage API contracts.
        </Typography>

        <Formik
          initialValues={{ username: '', password: '', email: '' }}
          validationSchema={schema}
          onSubmit={async (values, { setSubmitting }) => {
            setServerError(null)
            try {
              await register(values.username, values.password, values.email)
              navigate('/')
            } catch (err) {
              const data = err.response?.data
              const msg =
                typeof data === 'object' && data
                  ? Object.entries(data)
                      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
                      .join(' | ')
                  : 'Registration failed'
              setServerError(msg)
            } finally {
              setSubmitting(false)
            }
          }}
        >
          {({ handleSubmit, isSubmitting }) => (
            <Stack component="form" onSubmit={handleSubmit} spacing={2} noValidate>
              {serverError && <Alert severity="error">{serverError}</Alert>}

              <FastField name="username">
                {({ field, meta }) => (
                  <TextField
                    {...field}
                    label="Username"
                    fullWidth
                    error={Boolean(meta.touched && meta.error)}
                    helperText={meta.touched && meta.error ? meta.error : ' '}
                  />
                )}
              </FastField>

              <FastField name="email">
                {({ field }) => (
                  <TextField {...field} label="Email (optional)" fullWidth type="email" />
                )}
              </FastField>

              <FastField name="password">
                {({ field, meta }) => (
                  <TextField
                    {...field}
                    label="Password"
                    type="password"
                    fullWidth
                    error={Boolean(meta.touched && meta.error)}
                    helperText={meta.touched && meta.error ? meta.error : ' '}
                  />
                )}
              </FastField>

              <Button type="submit" variant="contained" disabled={isSubmitting}>
                {isSubmitting ? 'Registering…' : 'Register'}
              </Button>

              <Divider />
              <Typography variant="body2" align="center">
                Already have an account?{' '}
                <Link component={RouterLink} to="/login">
                  Log in
                </Link>
              </Typography>
            </Stack>
          )}
        </Formik>
      </CardContent>
    </Card>
  )
}
