import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  AppBar,
  Box,
  Button,
  Container,
  Drawer,
  IconButton,
  Link,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import MenuIcon from '@mui/icons-material/Menu'
import { useState } from 'react'
import { useAuth } from '../auth/AuthContext'

const NAV = [
  { to: '/', label: 'Dashboard' },
  { to: '/services', label: 'Services' },
  { to: '/consumers', label: 'Consumers' },
  { to: '/publishing', label: 'Publishing' },
  { to: '/notifications', label: 'Notifications' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const theme = useTheme()
  const isSmall = useMediaQuery(theme.breakpoints.down('sm'))
  const [drawerOpen, setDrawerOpen] = useState(false)

  const isActive = (to) => (to === '/' ? location.pathname === '/' : location.pathname.startsWith(to))

  const navItems = (
    <>
      {NAV.map((item) => (
        <Button
          key={item.to}
          component={RouterLink}
          to={item.to}
          color={isActive(item.to) ? 'secondary' : 'inherit'}
          sx={{ minWidth: 90 }}
        >
          {item.label}
        </Button>
      ))}
    </>
  )

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="static" color="primary" elevation={0}>
        <Toolbar>
          {isSmall && (
            <IconButton edge="start" color="inherit" onClick={() => setDrawerOpen(true)} sx={{ mr: 1 }}>
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="h6" sx={{ mr: 4, fontWeight: 700 }}>
            Contract Guard
          </Typography>
          {!isSmall && <Stack direction="row" spacing={1}>{navItems}</Stack>}
          <Box sx={{ flexGrow: 1 }} />
          {user && (
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography variant="body2">Hi, {user.username}</Typography>
              <Button
                color="inherit"
                onClick={() => {
                  logout()
                  navigate('/login')
                }}
              >
                Log out
              </Button>
            </Stack>
          )}
        </Toolbar>
      </AppBar>

      {isSmall && (
        <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          <List sx={{ width: 220 }}>
            {NAV.map((item) => (
              <ListItemButton
                key={item.to}
                component={RouterLink}
                to={item.to}
                selected={isActive(item.to)}
                onClick={() => setDrawerOpen(false)}
              >
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        </Drawer>
      )}

      <Container sx={{ py: 4, flexGrow: 1 }}>
        <Outlet />
      </Container>

      <Box component="footer" sx={{ py: 2, textAlign: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          Contract Guard — static API contract analysis ·{' '}
          <Link href="http://localhost:8765/docs/" target="_blank" rel="noreferrer">
            Swagger UI
          </Link>
        </Typography>
      </Box>
    </Box>
  )
}
