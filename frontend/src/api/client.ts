import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
  paramsSerializer: (params) => {
    const sp = new URLSearchParams()
    for (const [key, val] of Object.entries(params)) {
      if (Array.isArray(val)) {
        val.forEach((v) => sp.append(key, String(v)))
      } else if (val != null) {
        sp.append(key, String(val))
      }
    }
    return sp.toString()
  },
})

let _token: string | null = sessionStorage.getItem('pf_token')

export function setToken(token: string | null) {
  _token = token
}

api.interceptors.request.use((config) => {
  if (_token) {
    config.headers.Authorization = `Bearer ${_token}`
  }
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      setToken(null)
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
