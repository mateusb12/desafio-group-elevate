import { csrfHeaders } from '../auth/auth.service'

export type LeadPayload = {
  name?: string | number
  email: string
  phone: string
  product: string
  funnel: string
  source: string
  campaign: string
  affiliate_id: string
  utm: { source: string; medium: string; campaign: string; content: string } | string
}

type ProductsResponse = {
  products?: { code: string }[]
  error?: string
}

export type LeadSubmission = {
  status: number
  id?: string
  error?: string
}

export async function listProducts(): Promise<string[]> {
  const response = await fetch('/api/api/products', { credentials: 'same-origin' })
  const body = await response.json() as ProductsResponse

  if (!response.ok) throw new Error(body.error ?? 'Falha ao consultar produtos.')
  if (!Array.isArray(body.products)) throw new Error('Resposta inválida do catálogo de produtos.')

  return body.products.map((product) => product.code)
}

export async function submitLead(payload: LeadPayload, idempotencyKey: string): Promise<LeadSubmission> {
  const response = await fetch('/api/api/leads', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(payload),
  })
  const text = await response.text()
  let body: Record<string, unknown> = {}

  try {
    const parsed: unknown = JSON.parse(text)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      body = parsed as Record<string, unknown>
    }
  } catch {
    // Respostas não JSON continuam disponíveis como status sem detalhes estruturados.
  }

  return {
    status: response.status,
    id: typeof body.id === 'string' ? body.id : undefined,
    error: typeof body.error === 'string' ? body.error : undefined,
  }
}

export async function clearLabLeads(): Promise<number> {
  const response = await fetch('/api/api/leads/lab', {
    method: 'DELETE',
    credentials: 'same-origin',
    headers: csrfHeaders(),
  })
  const body = await response.json() as { deleted?: number; error?: string }

  if (!response.ok) throw new Error(body.error ?? 'Não foi possível limpar os leads do LAB.')
  return body.deleted ?? 0
}
