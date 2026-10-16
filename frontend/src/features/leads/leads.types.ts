export type LeadStatus = 'new' | 'contacted' | 'no_answer' | 'callback' | 'qualified' | 'sale' | 'refund' | 'invalid'
export type Lead = { id: string; name: string; email: string; phone: string; product: string; funnel: string; source: string; campaign: string; callCenterId: string; callCenterName: string; status: LeadStatus; receivedAt: string }
export type LeadFilters = { search: string; product: string; funnel: string; source: string; callCenterId: string; status: string; from: string; to: string }
