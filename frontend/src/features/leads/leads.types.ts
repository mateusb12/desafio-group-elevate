export type LeadStatus = 'new' | 'contacted' | 'no_answer' | 'callback' | 'qualified' | 'sale' | 'refund' | 'invalid'
export type Lead = { id: string; name: string; email: string; phone: string; product: string; funnel: string; source: string; campaign: string; callCenterId: string; callCenterName: string; status: LeadStatus; receivedAt: string }
export type LeadEvent = { id: string; status: LeadStatus; eventAt: string; receivedAt: string }
export type LeadDetails = Lead & { affiliateId: string; utm: Record<string, string>; events: LeadEvent[] }
export type LeadFilters = { search: string; product: string; funnel: string; source: string; callCenterId: string; status: string; from: string; to: string }
export type LeadsPage = { leads: Lead[]; pagination: { page: number; pageSize: number; total: number; totalPages: number } }
export type LeadFacets = { products: string[]; funnels: string[]; sources: string[]; callCenters: { id: string; name: string }[] }
