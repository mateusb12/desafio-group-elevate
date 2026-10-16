import type { Lead, LeadStatus } from './leads.types'

const leads: Lead[] = [
  { id: 'LD-1042', name: 'Mariana Costa', email: 'mariana@email.com', phone: '(11) 99912-3456', product: 'Curso de Vendas', funnel: 'Lançamento Q3', source: 'Instagram', campaign: 'campanha-vendas', callCenterId: 'call-center-a', callCenterName: 'Logicall', status: 'new', receivedAt: '2026-10-16T09:20:00' },
  { id: 'LD-1041', name: 'Rafael Oliveira', email: 'rafael@email.com', phone: '(21) 98822-1000', product: 'Marketing Digital', funnel: 'Sempre ativo', source: 'Google', campaign: 'google-search', callCenterId: 'call-center-b', callCenterName: 'Salesbound', status: 'contacted', receivedAt: '2026-10-16T08:45:00' },
  { id: 'LD-1040', name: 'Camila Santos', email: 'camila@email.com', phone: '(31) 97744-7788', product: 'Curso de Vendas', funnel: 'Lançamento Q3', source: 'Indicação', campaign: 'parceiros', callCenterId: 'call-center-a', callCenterName: 'Logicall', status: 'qualified', receivedAt: '2026-10-15T17:10:00' },
  { id: 'LD-1039', name: 'João Pedro Lima', email: 'joao@email.com', phone: '(41) 99111-2200', product: 'Gestão Financeira', funnel: 'Webinar', source: 'Facebook', campaign: 'webinar-outubro', callCenterId: 'call-center-c', callCenterName: 'AtendeMais', status: 'no_answer', receivedAt: '2026-10-15T15:30:00' },
  { id: 'LD-1038', name: 'Beatriz Almeida', email: 'bia@email.com', phone: '(85) 99900-5522', product: 'Marketing Digital', funnel: 'Sempre ativo', source: 'Instagram', campaign: 'remarketing', callCenterId: 'call-center-a', callCenterName: 'Logicall', status: 'sale', receivedAt: '2026-10-15T14:05:00' },
  { id: 'LD-1037', name: 'Lucas Ferreira', email: 'lucas@email.com', phone: '(11) 98800-1200', product: 'Curso de Vendas', funnel: 'Webinar', source: 'YouTube', campaign: 'aula-aberta', callCenterId: 'call-center-b', callCenterName: 'Salesbound', status: 'callback', receivedAt: '2026-10-14T12:25:00' },
  { id: 'LD-1036', name: 'Isabela Rocha', email: 'isa@email.com', phone: '(27) 99777-6633', product: 'Gestão Financeira', funnel: 'Lançamento Q3', source: 'Google', campaign: 'pesquisa-q3', callCenterId: 'call-center-c', callCenterName: 'AtendeMais', status: 'new', receivedAt: '2026-10-14T10:15:00' },
  { id: 'LD-1035', name: 'Pedro Henrique', email: 'pedro@email.com', phone: '(61) 98123-9087', product: 'Marketing Digital', funnel: 'Webinar', source: 'Facebook', campaign: 'webinar-outubro', callCenterId: 'call-center-a', callCenterName: 'Logicall', status: 'invalid', receivedAt: '2026-10-13T16:50:00' },
  { id: 'LD-1034', name: 'Fernanda Souza', email: 'fer@email.com', phone: '(48) 99982-7722', product: 'Curso de Vendas', funnel: 'Sempre ativo', source: 'Indicação', campaign: 'parceiros', callCenterId: 'call-center-b', callCenterName: 'Salesbound', status: 'refund', receivedAt: '2026-10-13T11:40:00' },
]

export const statusLabels: Record<LeadStatus, string> = { new: 'Novo', contacted: 'Contatado', no_answer: 'Não atendeu', callback: 'Retornar', qualified: 'Qualificado', sale: 'Venda', refund: 'Reembolso', invalid: 'Inválido' }

export async function listLeads(role: 'ADMIN' | 'OPERATOR', callCenterId?: string): Promise<Lead[]> {
  await new Promise((resolve) => setTimeout(resolve, 250))
  return leads.filter((lead) => role === 'ADMIN' || lead.callCenterId === callCenterId).map((lead) => ({ ...lead }))
}

export async function updateLeadStatus(id: string, status: LeadStatus): Promise<Lead> {
  await new Promise((resolve) => setTimeout(resolve, 200))
  const lead = leads.find((item) => item.id === id)
  if (!lead) throw new Error('Lead não encontrado.')
  lead.status = status
  return { ...lead }
}
