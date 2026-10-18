export type DashboardMetrics = { total: number; receivedToday: number; distributed: number; pending: number; sales: number; conversionRate: number }

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  const response = await fetch('/api/dashboard/metrics', { credentials: 'same-origin' })
  if (!response.ok) throw new Error('Não foi possível carregar as métricas.')
  return response.json() as Promise<DashboardMetrics>
}
