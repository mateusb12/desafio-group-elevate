import { useEffect, useState } from 'react'
import type { AuthenticatedUser } from '../auth/auth.types'
import { getLeadDetails, listLeads, statusLabels, updateLeadStatus } from './leads.service'
import type { Lead, LeadDetails, LeadFacets, LeadFilters, LeadStatus } from './leads.types'

const initialFilters: LeadFilters = { search: '', product: '', funnel: '', source: '', callCenterId: '', status: '', from: '', to: '' }
const statuses = Object.entries(statusLabels) as [LeadStatus, string][]
const selectClass = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-[#111827]'
const callCenterBadgeClasses: Record<string, string> = {
  'call-center-a': 'border border-violet-500/20 bg-violet-500/10 text-violet-700 dark:text-violet-300',
  'call-center-b': 'border border-sky-500/20 bg-sky-500/10 text-sky-700 dark:text-sky-300',
  'call-center-c': 'border border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
}

export function LeadsPage({ user }: { user: AuthenticatedUser }) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [facets, setFacets] = useState<LeadFacets>({ products: [], funnels: [], sources: [], callCenters: [] })
  const [pagination, setPagination] = useState({ page: 1, pageSize: 5, total: 0, totalPages: 0 })
  const [filters, setFilters] = useState(initialFilters)
  const [page, setPage] = useState(1)
  const [selectedLead, setSelectedLead] = useState<LeadDetails | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [savingStatus, setSavingStatus] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    listLeads(filters, page, pagination.pageSize)
      .then((result) => { setLeads(result.leads); setFacets(result.filters); setPagination(result.pagination) })
      .catch(() => setError('Não foi possível carregar os leads.'))
      .finally(() => setLoading(false))
  }, [filters, page, pagination.pageSize, user.role, user.callCenterId])

  const options = (key: 'product' | 'funnel' | 'source') => facets[`${key}s`]
  const pageCount = pagination.totalPages

  function setFilter(key: keyof LeadFilters, value: string) {
    setLoading(true)
    setError('')
    setFilters((current) => ({ ...current, [key]: value }))
    setPage(1)
  }

  async function openLead(id: string) {
    setDetailLoading(true)
    setDetailError('')
    try {
      setSelectedLead(await getLeadDetails(id))
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : 'Não foi possível carregar os detalhes.')
    } finally {
      setDetailLoading(false)
    }
  }

  async function saveStatus(status: LeadStatus) {
    if (!selectedLead || status === selectedLead.status) return
    setSavingStatus(true)
    setDetailError('')
    try {
      await updateLeadStatus(selectedLead.id, status)
      const updated = await getLeadDetails(selectedLead.id)
      setSelectedLead(updated)
      setLeads((current) => current.map((lead) => lead.id === updated.id ? { ...lead, status: updated.status } : lead))
    } catch (reason) {
      setDetailError(reason instanceof Error ? reason.message : 'Não foi possível atualizar o status.')
    } finally {
      setSavingStatus(false)
    }
  }

  return <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
    <div className="mb-6"><p className="text-sm text-indigo-500">{user.role === 'ADMIN' ? 'ADMIN / OPERAÇÃO' : 'OPERATOR / ATENDIMENTO'}</p><h1 className="mt-1 text-2xl font-semibold">{user.role === 'ADMIN' ? 'Leads' : 'Meus leads'}</h1><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{user.role === 'ADMIN' ? 'Consulte, filtre e acompanhe a distribuição.' : `Leads encaminhados para ${user.callCenterName}.`}</p></div>
    <div className="mb-4 flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/[.03]">
      <input aria-label="Buscar lead" placeholder="Buscar nome, e-mail ou telefone" value={filters.search} onChange={(e) => setFilter('search', e.target.value)} className={`${selectClass} min-w-56 flex-1`} />
      {(['product', 'funnel', 'source'] as const).map((key) => <select key={key} aria-label={key} className={selectClass} value={filters[key]} onChange={(e) => setFilter(key, e.target.value)}><option value="">{key === 'product' ? 'Todos produtos' : key === 'funnel' ? 'Todos funis' : 'Todas origens'}</option>{options(key).map((value) => <option key={value}>{value}</option>)}</select>)}
      {user.role === 'ADMIN' && <select aria-label="Call center" className={selectClass} value={filters.callCenterId} onChange={(e) => setFilter('callCenterId', e.target.value)}><option value="">Todos call centers</option>{facets.callCenters.map((center) => <option key={center.id} value={center.id}>{center.name}</option>)}</select>}
      <select aria-label="Status" className={selectClass} value={filters.status} onChange={(e) => setFilter('status', e.target.value)}><option value="">Todos status</option>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <label className="flex items-center gap-2 text-xs text-slate-500">De<input aria-label="Data inicial" type="date" className={selectClass} value={filters.from} onChange={(e) => setFilter('from', e.target.value)} /></label><label className="flex items-center gap-2 text-xs text-slate-500">Até<input aria-label="Data final" type="date" className={selectClass} value={filters.to} onChange={(e) => setFilter('to', e.target.value)} /></label>
    </div>
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-white/10 dark:bg-white/[.03]">{loading ? <p className="p-8 text-center text-slate-500">Carregando leads…</p> : error ? <p role="alert" className="p-8 text-center text-rose-500">{error}</p> : leads.length === 0 ? <p className="p-8 text-center text-slate-500">Nenhum lead encontrado para esses filtros.</p> : <table className="w-full min-w-[980px] text-left text-sm"><thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-white/10"><tr>{['Lead', 'Produto / funil', 'Origem', ...(user.role === 'ADMIN' ? ['Call center'] : []), 'Status', 'Recebido em', ''].map((label) => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 dark:divide-white/5">{leads.map((lead) => <tr key={lead.id}><td className="px-4 py-4"><p className="font-medium">{lead.name}</p><p className="text-xs text-slate-500">{lead.id} · {lead.email} · {lead.phone}</p></td><td className="px-4 py-4">{lead.product}<p className="text-xs text-slate-500">{lead.funnel}</p></td><td className="px-4 py-4">{lead.source}<p className="text-xs text-slate-500">{lead.campaign}</p></td>{user.role === 'ADMIN' && <td className="px-4 py-4"><span className={`inline-flex rounded-full px-2.5 py-1 text-xs ${callCenterBadgeClasses[lead.callCenterId] ?? 'bg-slate-500/10 text-slate-600 dark:text-slate-300'}`}>{lead.callCenterName}</span></td>}<td className="px-4 py-4"><span className="rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs text-indigo-600 dark:text-indigo-300">{statusLabels[lead.status]}</span></td><td className="px-4 py-4 text-slate-500">{new Date(lead.receivedAt).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</td><td className="px-4 py-4"><button type="button" onClick={() => void openLead(lead.id)} className="rounded-lg border border-indigo-500/30 px-3 py-1.5 text-xs text-indigo-600 hover:bg-indigo-500/10 dark:text-indigo-300">Ver detalhes</button></td></tr>)}</tbody></table>}</div>
    {!loading && !error && pagination.total > 0 && <div className="flex items-center justify-between py-4 text-sm text-slate-500"><span>{pagination.total} lead(s) · página {page} de {pageCount}</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => { setLoading(true); setError(''); setPage((value) => value - 1) }} className="rounded-lg border border-slate-200 px-3 py-1.5 disabled:opacity-40 dark:border-white/10">Anterior</button><button disabled={page >= pageCount} onClick={() => { setLoading(true); setError(''); setPage((value) => value + 1) }} className="rounded-lg border border-slate-200 px-3 py-1.5 disabled:opacity-40 dark:border-white/10">Próxima</button></div></div>}
    {detailLoading && <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">Carregando detalhes…</div>}
    {selectedLead && !detailLoading && <div className="mt-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]"><div className="flex items-start justify-between gap-4"><div><p className="text-sm text-indigo-500">DETALHES DO LEAD</p><h2 className="mt-1 text-lg font-semibold">{selectedLead.name}</h2><p className="text-sm text-slate-500">{selectedLead.email} · {selectedLead.phone}</p></div><button type="button" onClick={() => setSelectedLead(null)} className="text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white">Fechar</button></div><div className="mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4"><p><span className="text-slate-500">Produto</span><br />{selectedLead.product}</p><p><span className="text-slate-500">Funil</span><br />{selectedLead.funnel}</p><p><span className="text-slate-500">Origem</span><br />{selectedLead.source}</p><p><span className="text-slate-500">Call center</span><br />{selectedLead.callCenterName}</p></div><div className="mt-5 flex flex-wrap items-center gap-3"><label htmlFor="lead-status" className="text-sm text-slate-500">Status do atendimento</label><select id="lead-status" className={selectClass} value={selectedLead.status} disabled={savingStatus} onChange={(e) => void saveStatus(e.target.value as LeadStatus)}>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{savingStatus && <span className="text-sm text-slate-500">Salvando…</span>}</div>{detailError && <p role="alert" className="mt-3 text-sm text-rose-500">{detailError}</p>}<div className="mt-6"><h3 className="text-sm font-medium">Histórico do atendimento</h3>{selectedLead.events.length === 0 ? <p className="mt-2 text-sm text-slate-500">Nenhum evento registrado.</p> : <ol className="mt-3 space-y-2">{selectedLead.events.map((event) => <li key={event.id} className="flex flex-wrap justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-white/[.04]"><span>{statusLabels[event.status]}</span><time className="text-slate-500">{new Date(event.eventAt).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</time></li>)}</ol>}</div></div>}
  </section>
}
