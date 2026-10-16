import type { AuthenticatedUser } from './auth.types'

const demoAccounts = [
  { email: 'admin@elevate.dev', password: 'demo123', user: { id: 'admin-1', name: 'Mateus Admin', email: 'admin@elevate.dev', role: 'ADMIN' as const } },
  { email: 'operador@elevate.dev', password: 'demo123', user: { id: 'operator-1', name: 'Ana Operadora', email: 'operador@elevate.dev', role: 'OPERATOR' as const, callCenterId: 'call-center-a', callCenterName: 'Call Center A' } },
]

export async function login(email: string, password: string): Promise<AuthenticatedUser> {
  await new Promise((resolve) => setTimeout(resolve, 350))
  const account = demoAccounts.find((item) => item.email === email.trim().toLowerCase() && item.password === password)
  if (!account) throw new Error('E-mail ou senha inválidos. Use uma das contas demonstrativas.')
  return { ...account.user }
}

export async function logout(): Promise<void> {
  await Promise.resolve()
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
