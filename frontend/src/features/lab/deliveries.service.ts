export type Delivery = {
  eventId: string
  eventType: string
  leadId: string | null
  distributionId: string
  callCenter: string
  callCenterId: string
  createdAt: string
  publishedAt: string | null
  state: 'pending' | 'published' | 'retry_scheduled' | 'delivered' | 'failed'
  deliveryStatus: 'pending' | 'retry_scheduled' | 'delivered' | 'failed' | null
}

export type DeliveryResponse = {
  deliveries: Delivery[]
  counters: { total: number; pending: number; published: number; deliveryTotal: number; initialPending: number; delivered: number; retrying: number; failed: number }
  pagination: { page: number; pageSize: number; total: number; totalPages: number }
}

export type ServiceHealth = {
  name: string
  id: string
  state: 'available' | 'unavailable' | 'unknown'
  httpStatus?: number
  error?: string
  processedCount?: number
  publishedCount?: number
  markedPublishedCount?: number
  acceptedCount?: number
}

export type RabbitMqHealth = {
  state: 'available' | 'unavailable'
  error?: string
  messageCount?: number
  deadLetterCount?: number
}

const LAB_REQUEST_TIMEOUT_MS = 1200

async function fetchLab(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), LAB_REQUEST_TIMEOUT_MS)
  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } finally {
    window.clearTimeout(timeout)
  }
}

async function readJson<T extends object>(response: Response): Promise<T> {
  if (response.status === 401) window.dispatchEvent(new Event('auth-expired'))
  const body = await response.json() as T
  const error = 'error' in body && typeof body.error === 'string' ? body.error : 'Falha ao consultar o LAB.'
  if (!response.ok) throw new Error(error)
  return body
}

export async function listDeliveries(page = 1, pageSize = 8): Promise<DeliveryResponse> {
  const response = await fetchLab(`/api/api/lab/deliveries?page=${page}&pageSize=${pageSize}`, { credentials: 'same-origin' })
  return readJson<DeliveryResponse>(response)
}

export async function checkCallCenterHealth(): Promise<ServiceHealth[]> {
  const response = await fetchLab('/api/api/lab/health', { credentials: 'same-origin' })
  const body = await readJson<{ services?: ServiceHealth[] }>(response)
  if (!Array.isArray(body.services)) throw new Error('Resposta inválida da saúde dos simuladores.')
  return body.services
}

export async function checkRabbitMqHealth(): Promise<RabbitMqHealth> {
  const response = await fetchLab('/api/api/lab/rabbitmq', { credentials: 'same-origin' })
  return readJson<RabbitMqHealth>(response)
}

async function checkProcessHealth(path: string, expectedId: string, expectedName: string): Promise<ServiceHealth> {
  const response = await fetchLab(path, { credentials: 'same-origin' })
  const body = await readJson<ServiceHealth>(response)
  if (body.id !== expectedId || body.name !== expectedName || !['available', 'unavailable'].includes(body.state)) {
    throw new Error('Resposta inválida da saúde do processo.')
  }
  return body
}

export function checkOutboxServiceHealth(): Promise<ServiceHealth> {
  return checkProcessHealth('/api/api/lab/outbox-service/health', 'outbox-service', 'Outbox Service')
}

export function checkDeliveryWorkerHealth(): Promise<ServiceHealth> {
  return checkProcessHealth('/api/api/lab/delivery-worker/health', 'delivery-worker', 'Worker')
}
