import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:5000/api',
  timeout: 60000,
})

api.interceptors.response.use(
  r => r,
  err => {
    const msg = err.response?.data?.error || err.message || 'Request failed'
    return Promise.reject(new Error(msg))
  }
)

export const health       = ()   => api.get('/health')
export const uploadCSV    = (fd) => api.post('/upload/csv', fd)
export const listTables   = ()   => api.get('/upload/tables')
export const getSchema    = (t)  => api.get(`/upload/schema/${t}`)

// Single or multi-table text query
// Pass tables: ['t1','t2'] for JOIN, or table_name: 't1' for single
export const queryText    = (d)  => api.post('/query/text', d)
export const queryVoice   = (fd) => api.post('/query/voice', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
export const queryImage   = (fd) => api.post('/query/image', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
export const queryDirect  = (d)  => api.post('/query/direct', d)
export const getTables    = ()   => api.get('/query/tables')
export const getJoinHint  = (d)  => api.post('/query/join-hint', d)

export const getHistory   = (p)  => api.get('/history/', { params: p })
export const getHistStats = ()   => api.get('/history/stats')
export const deleteHist   = (id) => api.delete(`/history/${id}`)
export const clearHistory = ()   => api.delete('/history/clear')

export const exportCSV    = (d)  => api.post('/export/csv', d, { responseType: 'blob' })
export const exportPDF    = (d)  => api.post('/export/pdf', d, { responseType: 'blob' })
export const exportChart  = (d)  => api.post('/export/chart', d, { responseType: 'blob' })

export function downloadBlob(blob, name) {
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href = url; a.download = name; a.click()
  URL.revokeObjectURL(url)
}
