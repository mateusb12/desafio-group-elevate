export type DashboardMetrics = { total: number; receivedToday: number; distributed: number; pending: number; sales: number; conversionRate: number }

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  await new Promise((resolve) => setTimeout(resolve, 250))
  return { total: 1284, receivedToday: 42, distributed: 1198, pending: 86, sales: 173, conversionRate: 14.4 }
}
