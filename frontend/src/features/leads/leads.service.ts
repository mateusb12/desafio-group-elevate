import type { Lead, LeadStatus } from './leads.types'

export const statusLabels: Record<LeadStatus, string> = {
  new: 'Novo',
  contacted: 'Contatado',
  no_answer: 'Não atendeu',
  callback: 'Retornar',
  qualified: 'Qualificado',
  sale: 'Venda',
  refund: 'Reembolso',
  invalid: 'Inválido',
}

export async function listLeads(): Promise<Lead[]> {
  // O proxy Vite remove o primeiro /api.
  const response = await fetch('/api/api/leads', {
    credentials: 'same-origin',
  })

  const body = await response.json() as {
    leads?: Lead[]
    error?: string
  }

  if (!response.ok) {
    throw new Error(body.error ?? 'Não foi possível carregar os leads.')
  }

  if (!Array.isArray(body.leads)) {
    throw new Error('Resposta inválida da API de leads.')
  }

  return body.leads
}
