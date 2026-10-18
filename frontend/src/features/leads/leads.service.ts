import type { Lead, LeadFacets, LeadFilters, LeadStatus, LeadsPage } from './leads.types'

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

export async function listLeads(filters: LeadFilters, page: number, pageSize: number): Promise<LeadsPage & { filters: LeadFacets }> {
  // O proxy Vite remove o primeiro /api.
  const query = new URLSearchParams({ page: String(page), pageSize: String(pageSize) })
  Object.entries(filters).forEach(([key, value]) => {
    if (value) query.set(key, value)
  })
  const response = await fetch(`/api/api/leads?${query.toString()}`, {
    credentials: 'same-origin',
  })

  const body = await response.json() as {
    leads?: Lead[]
    filters?: LeadFacets
    pagination?: LeadsPage['pagination']
    error?: string
  }

  if (!response.ok) {
    throw new Error(body.error ?? 'Não foi possível carregar os leads.')
  }

  if (!Array.isArray(body.leads) || !body.filters || !body.pagination) {
    throw new Error('Resposta inválida da API de leads.')
  }

  return { leads: body.leads, filters: body.filters, pagination: body.pagination }
}
