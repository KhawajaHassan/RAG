import axios from 'axios'
import toast from 'react-hot-toast'

const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({
  baseURL,
})

api.interceptors.request.use((config) => {
  const key = localStorage.getItem('openai_api_key') ?? ''
  if (key) config.headers.set('X-OpenAI-Key', key)
  return config
})

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err?.response?.data?.detail ??
      err?.message ??
      'Request failed'
    toast.error(String(msg))
    return Promise.reject(err)
  },
)

