import { useEffect, useState } from 'react'
import { getDashboardMetrics, type DashboardMetrics } from './dashboard.service'

const cards: { key: keyof DashboardMetrics; label: string; suffix?: string }[] = [
  { key: 'total', label: 'Total de leads' }, { key: 'receivedToday', label: 'Recebidos hoje' },
  { key: 'distributed', label: 'Leads distribuídos' }, { key: 'pending', label: 'Leads aguardando distribuição' },
  { key: 'sales', label: 'Vendas' }, { key: 'conversionRate', label: 'Taxa de conversão', suffix: '%' },
]

export function DashboardPage({ onViewLeads }: { onViewLeads: () => void }) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { getDashboardMetrics().then(setMetrics).catch(() => setError('Não foi possível carregar o resumo.')) }, [])
  return <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm text-indigo-500">ADMIN / VISÃO GERAL</p><h1 className="mt-1 text-2xl font-semibold">Resumo de leads</h1><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Acompanhe a operação em um só lugar.</p></div><button onClick={onViewLeads} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">Ver leads</button></div>
    {error && <p role="alert" className="mb-4 rounded-lg bg-rose-500/10 p-4 text-rose-600">{error}</p>}
    {!metrics && !error ? <p className="py-10 text-center text-slate-500">Carregando métricas…</p> : metrics && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{cards.map((card) => <article key={card.key} className="rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]"><p className="text-sm text-slate-500 dark:text-slate-400">{card.label}</p><p className="mt-3 text-3xl font-semibold">{metrics[card.key].toLocaleString('pt-BR')}{card.suffix ?? ''}</p></article>)}</div>}
  </section>
}
