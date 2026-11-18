import axios from 'axios'

/**
 * Single axios instance for the whole app.
 * The Vite dev server proxies /api to Django (see vite.config.js), so the
 * baseURL is just /api — no CORS or host juggling in code.
 */
const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// --- JWT request interceptor: attach the access token when present -------
const TOKEN_KEY = 'cg_access_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// --- Response interceptor: on 401, drop the stale token and go to login --
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setToken(null)
      // avoid redirect loops for the login page itself
      if (!window.location.hash.includes('/login')) {
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  },
)

export default api
