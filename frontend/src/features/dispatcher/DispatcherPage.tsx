import { useEffect, useState } from 'react'
import { getAllocations, saveAllocations, type CallCenterAllocation } from './dispatcher.service'

export function DispatcherPage() {
  const [allocations, setAllocations] = useState<CallCenterAllocation[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { getAllocations().then(setAllocations).catch(() => setError('Não foi possível carregar as configurações.')).finally(() => setLoading(false)) }, [])
  function update(id: string, percentage: number) { setAllocations((current) => current.map((item) => item.id === id ? { ...item, percentage } : item)); setMessage('') }
  async function save() {
    setSaving(true); setMessage(''); setError('')
    try { setAllocations(await saveAllocations(allocations)); setMessage('Configurações salvas para esta demonstração.') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Não foi possível salvar.') }
    finally { setSaving(false) }
  }
  const total = allocations.reduce((sum, item) => sum + item.percentage, 0)
  return <section className="mx-auto max-w-4xl px-4 py-8 sm:px-8">
    <div className="mb-7"><p className="text-sm text-indigo-500">ADMIN / CONFIGURAÇÃO</p><h1 className="mt-1 text-2xl font-semibold">Distribuição de leads</h1><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Defina a participação de cada call center no dispatcher.</p></div>
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
      {loading ? <p className="py-8 text-center text-slate-500">Carregando configurações…</p> : error && allocations.length === 0 ? <p role="alert" className="py-8 text-center text-rose-500">{error}</p> : <>
        <div className="space-y-5">{allocations.map((item) => <label key={item.id} className="grid grid-cols-[1fr_100px] items-center gap-4"><span className="font-medium">{item.name}<span className="mt-2 block h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-white/10"><span className="block h-full rounded-full bg-indigo-500" style={{ width: `${item.percentage}%` }} /></span></span><span className="relative"><input aria-label={`Percentual ${item.name}`} type="number" min="0" max="100" value={item.percentage} onChange={(e) => update(item.id, Number(e.target.value))} className="w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 pr-8 dark:border-white/10" /><span className="absolute right-3 top-2 text-slate-500">%</span></span></label>)}</div>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-5 dark:border-white/10"><p className={`text-sm font-medium ${total === 100 ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`}>Total: {total}% {total !== 100 && '· precisa somar 100%'}</p><button disabled={saving || total !== 100} onClick={() => void save()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50">{saving ? 'Salvando…' : 'Salvar configuração'}</button></div>
      </>}
    </div>
    {message && <p role="status" className="mt-4 text-sm text-emerald-600 dark:text-emerald-300">{message}</p>}{error && allocations.length > 0 && <p role="alert" className="mt-4 text-sm text-rose-500">{error}</p>}
  </section>
}
