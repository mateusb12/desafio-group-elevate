import { useEffect, useMemo, useState } from 'react'
import type { AuthenticatedUser } from '../auth/auth.types'
import { listLeads, statusLabels, updateLeadStatus } from './leads.service'
import type { Lead, LeadFilters, LeadStatus } from './leads.types'

const initialFilters: LeadFilters = { search: '', product: '', funnel: '', source: '', callCenterId: '', status: '', from: '', to: '' }
const statuses = Object.entries(statusLabels) as [LeadStatus, string][]
const selectClass = 'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-white/10 dark:bg-[#111827]'

export function LeadsPage({ user }: { user: AuthenticatedUser }) {
  const [leads, setLeads] = useState<Lead[]>([])
  const [filters, setFilters] = useState(initialFilters)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [updating, setUpdating] = useState('')
  useEffect(() => { listLeads(user.role, user.callCenterId).then(setLeads).catch(() => setError('Não foi possível carregar os leads.')).finally(() => setLoading(false)) }, [user.role, user.callCenterId])
  const options = (key: 'product' | 'funnel' | 'source' | 'callCenterName') => [...new Set(leads.map((lead) => lead[key]))]
  const filtered = useMemo(() => leads.filter((lead) => {
    const query = filters.search.trim().toLowerCase()
    const day = lead.receivedAt.slice(0, 10)
    return (!query || `${lead.id} ${lead.name} ${lead.email} ${lead.phone}`.toLowerCase().includes(query)) && (!filters.product || lead.product === filters.product) && (!filters.funnel || lead.funnel === filters.funnel) && (!filters.source || lead.source === filters.source) && (!filters.callCenterId || lead.callCenterId === filters.callCenterId) && (!filters.status || lead.status === filters.status) && (!filters.from || day >= filters.from) && (!filters.to || day <= filters.to)
  }), [leads, filters])
  const pageSize = 5
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const visible = filtered.slice((page - 1) * pageSize, page * pageSize)
  function setFilter(key: keyof LeadFilters, value: string) { setFilters((current) => ({ ...current, [key]: value })); setPage(1) }
  async function changeStatus(id: string, status: LeadStatus) {
    setUpdating(id); setNotice('')
    try { const updated = await updateLeadStatus(id, status); setLeads((current) => current.map((lead) => lead.id === id ? updated : lead)); setNotice('Status atualizado.') }
    catch { setNotice('Não foi possível atualizar o status.') }
    finally { setUpdating('') }
  }
  return <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
    <div className="mb-6"><p className="text-sm text-indigo-500">{user.role === 'ADMIN' ? 'ADMIN / OPERAÇÃO' : 'OPERATOR / ATENDIMENTO'}</p><h1 className="mt-1 text-2xl font-semibold">{user.role === 'ADMIN' ? 'Leads' : 'Meus leads'}</h1><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{user.role === 'ADMIN' ? 'Consulte, filtre e acompanhe a distribuição.' : `Leads encaminhados para ${user.callCenterName}.`}</p></div>
    <div className="mb-4 flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-4 dark:border-white/10 dark:bg-white/[.03]">
      <input aria-label="Buscar lead" placeholder="Buscar nome, e-mail ou telefone" value={filters.search} onChange={(e) => setFilter('search', e.target.value)} className={`${selectClass} min-w-56 flex-1`} />
      {(['product', 'funnel', 'source'] as const).map((key) => <select key={key} aria-label={key} className={selectClass} value={filters[key]} onChange={(e) => setFilter(key, e.target.value)}><option value="">{key === 'product' ? 'Todos produtos' : key === 'funnel' ? 'Todos funis' : 'Todas origens'}</option>{options(key).map((value) => <option key={value}>{value}</option>)}</select>)}
      {user.role === 'ADMIN' && <select aria-label="Call center" className={selectClass} value={filters.callCenterId} onChange={(e) => setFilter('callCenterId', e.target.value)}><option value="">Todos call centers</option>{options('callCenterName').map((name) => <option key={name} value={leads.find((lead) => lead.callCenterName === name)?.callCenterId}>{name}</option>)}</select>}
      <select aria-label="Status" className={selectClass} value={filters.status} onChange={(e) => setFilter('status', e.target.value)}><option value="">Todos status</option>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
      <label className="flex items-center gap-2 text-xs text-slate-500">De<input aria-label="Data inicial" type="date" className={selectClass} value={filters.from} onChange={(e) => setFilter('from', e.target.value)} /></label><label className="flex items-center gap-2 text-xs text-slate-500">Até<input aria-label="Data final" type="date" className={selectClass} value={filters.to} onChange={(e) => setFilter('to', e.target.value)} /></label>
    </div>
    {notice && <p role="status" className="mb-3 text-sm text-emerald-600 dark:text-emerald-300">{notice}</p>}
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-white/10 dark:bg-white/[.03]">{loading ? <p className="p-8 text-center text-slate-500">Carregando leads…</p> : error ? <p role="alert" className="p-8 text-center text-rose-500">{error}</p> : filtered.length === 0 ? <p className="p-8 text-center text-slate-500">Nenhum lead encontrado para esses filtros.</p> : <table className="w-full min-w-[920px] text-left text-sm"><thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-white/10"><tr>{['Lead', 'Produto / funil', 'Origem', ...(user.role === 'ADMIN' ? ['Call center'] : []), 'Status', 'Recebido em'].map((label) => <th key={label} className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 dark:divide-white/5">{visible.map((lead) => <tr key={lead.id}><td className="px-4 py-4"><p className="font-medium">{lead.name}</p><p className="text-xs text-slate-500">{lead.id} · {lead.email} · {lead.phone}</p></td><td className="px-4 py-4">{lead.product}<p className="text-xs text-slate-500">{lead.funnel}</p></td><td className="px-4 py-4">{lead.source}<p className="text-xs text-slate-500">{lead.campaign}</p></td>{user.role === 'ADMIN' && <td className="px-4 py-4">{lead.callCenterName}</td>}<td className="px-4 py-4">{user.role === 'OPERATOR' ? <select disabled={updating === lead.id} aria-label={`Status de ${lead.name}`} className={selectClass} value={lead.status} onChange={(e) => void changeStatus(lead.id, e.target.value as LeadStatus)}>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select> : <span className="rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs text-indigo-600 dark:text-indigo-300">{statusLabels[lead.status]}</span>}</td><td className="px-4 py-4 text-slate-500">{new Date(lead.receivedAt).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })}</td></tr>)}</tbody></table>}</div>
    {!loading && !error && filtered.length > 0 && <div className="flex items-center justify-between py-4 text-sm text-slate-500"><span>{filtered.length} lead(s) · página {page} de {pageCount}</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="rounded-lg border border-slate-200 px-3 py-1.5 disabled:opacity-40 dark:border-white/10">Anterior</button><button disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)} className="rounded-lg border border-slate-200 px-3 py-1.5 disabled:opacity-40 dark:border-white/10">Próxima</button></div></div>}
  </section>
}
