/** Extract a human-readable message from an axios/DRF error. */
export default function errorMessage(err, fallback = 'Something went wrong') {
  const data = err?.response?.data
  if (!data) return err?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (typeof data === 'object') {
    return Object.entries(data)
      .map(([key, value]) => {
        const text = Array.isArray(value) ? value.join(', ') : String(value)
        return key === 'detail' ? text : `${key}: ${text}`
      })
      .join(' | ')
  }
  return fallback
}
