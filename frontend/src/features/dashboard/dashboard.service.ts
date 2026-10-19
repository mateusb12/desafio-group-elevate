export type DashboardMetrics = { total: number; receivedToday: number; distributed: number; pending: number; sales: number; conversionRate: number }

export type DashboardFunnel = {
  total: number
  nodes: { id: string; label: string }[]
  links: { source: string; target: string; value: number }[]
}

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await fetch('/api/dashboard/metrics', { credentials: 'same-origin' })
  if (!response.ok) throw new Error('Não foi possível carregar as métricas.')
  return response.json() as Promise<DashboardMetrics>
}

export async function getDashboardFunnel(): Promise<DashboardFunnel> {
  const response = await fetch('/api/dashboard/funnel', { credentials: 'same-origin' })
  if (!response.ok) throw new Error('Não foi possível carregar o fluxo de leads.')
  return response.json() as Promise<DashboardFunnel>
}
