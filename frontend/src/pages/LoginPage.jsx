import { Field, Formik } from 'formik'
import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import * as Yup from 'yup'
import {
  Alert,
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
  username: Yup.string().required('Required'),
  password: Yup.string().required('Required'),
})

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState(null)

  return (
    <Card sx={{ maxWidth: 420, mx: 'auto', mt: 10 }}>
      <CardContent>
        <Typography variant="h5" gutterBottom>
          Log in
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Access Contract Guard.
        </Typography>

        <Formik
          initialValues={{ username: '', password: '' }}
          validationSchema={schema}
          onSubmit={async (values, { setSubmitting }) => {
            setServerError(null)
            try {
              await login(values.username, values.password)
              navigate('/')
            } catch (err) {
              if (err.response?.status === 401) {
                setServerError('Invalid username or password')
              } else {
                setServerError('Login failed. Is the backend running?')
              }
            } finally {
              setSubmitting(false)
            }
          }}
        >
          {({ handleSubmit, isSubmitting }) => (
            <Stack component="form" onSubmit={handleSubmit} spacing={2} noValidate>
              {serverError && <Alert severity="error">{serverError}</Alert>}

              <Field name="username">
                {({ field, meta }) => (
                  <TextField
                    {...field}
                    label="Username"
                    fullWidth
                    error={Boolean(meta.touched && meta.error)}
                    helperText={meta.touched && meta.error ? meta.error : ' '}
                  />
                )}
              </Field>

              <Field name="password">
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
              </Field>

              <Button type="submit" variant="contained" disabled={isSubmitting}>
                {isSubmitting ? 'Logging in…' : 'Log in'}
              </Button>

              <Divider />
              <Typography variant="body2" align="center">
                New here?{' '}
                <Link component={RouterLink} to="/register">
                  Create an account
                </Link>
              </Typography>
            </Stack>
          )}
        </Formik>
      </CardContent>
    </Card>
  )
}
