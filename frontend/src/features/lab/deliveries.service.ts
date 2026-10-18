export type Delivery = {
  eventId: string
  eventType: string
  leadId: string | null
  distributionId: string
  callCenter: string
  callCenterId: string
  createdAt: string
  publishedAt: string | null
  state: 'pending' | 'published'
}

export type DeliveryResponse = {
  deliveries: Delivery[]
  counters: { total: number; pending: number; published: number }
  pagination: { page: number; pageSize: number; total: number; totalPages: number }
}

export type ServiceHealth = {
  name: string
  id: string
  state: 'available' | 'unavailable'
  httpStatus?: number
  error?: string
}

export type RabbitMqHealth = {
  state: 'available' | 'unavailable'
  error?: string
}

async function readJson<T extends object>(response: Response): Promise<T> {
  const body = await response.json() as T
  const error = 'error' in body && typeof body.error === 'string' ? body.error : 'Falha ao consultar o LAB.'
  if (!response.ok) throw new Error(error)
  return body
}

export async function listDeliveries(page = 1, pageSize = 8): Promise<DeliveryResponse> {
  const response = await fetch(`/api/api/lab/deliveries?page=${page}&pageSize=${pageSize}`, { credentials: 'same-origin' })
  return readJson<DeliveryResponse>(response)
}

export async function checkCallCenterHealth(): Promise<ServiceHealth[]> {
  const response = await fetch('/api/api/lab/health', { credentials: 'same-origin' })
  const body = await readJson<{ services?: ServiceHealth[] }>(response)
  if (!Array.isArray(body.services)) throw new Error('Resposta inválida da saúde dos simuladores.')
  return body.services
}

export async function checkRabbitMqHealth(): Promise<RabbitMqHealth> {
  const response = await fetch('/api/api/lab/rabbitmq', { credentials: 'same-origin' })
  return readJson<RabbitMqHealth>(response)
}
