import type { AuthenticatedUser } from './auth.types'

type AuthResponse = { user: AuthenticatedUser }

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json() as T & { error?: string }
  if (!response.ok) throw new Error(body.error ?? 'Não foi possível concluir a operação.')
  return body
}

export async function login(email: string, password: string): Promise<AuthenticatedUser> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const body = await parseResponse<AuthResponse>(response)
  return body.user
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' })
}

export async function getCurrentUser(): Promise<AuthenticatedUser | null> {
  const response = await fetch('/api/auth/me')
  if (response.status === 401) return null
  const body = await parseResponse<AuthResponse>(response)
  return body.user
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch('/api/ping')
    if (!response.ok) return false
    const body = await response.json() as { status: string }
    return body.status === 'ok'
  } catch {
    return false
  }
}
