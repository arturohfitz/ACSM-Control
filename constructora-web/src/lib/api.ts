export type ApiError = {
  detail?: string
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1'
const TOKEN_KEY = 'acsm_control_token'

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getStoredToken()
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')

  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 204) {
    return undefined as T
  }

  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    const message =
      typeof data.detail === 'string'
        ? data.detail
        : Array.isArray(data.detail) && data.detail[0]?.msg
          ? data.detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('. ')
        : 'No fue posible completar la solicitud'
    throw new Error(message)
  }

  return data as T
}

export function toPayload(values: Record<string, FormDataEntryValue>) {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => {
      if (value === '') return [key, null]
      if (value === 'true') return [key, true]
      if (value === 'false') return [key, false]
      return [key, value]
    }),
  )
}
