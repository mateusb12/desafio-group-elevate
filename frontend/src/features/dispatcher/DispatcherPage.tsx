import { useEffect, useState } from 'react'
import { Slider } from '../../shared/Slider'
import { getAllocations, saveAllocations, type CallCenterAllocation } from './dispatcher.service'

export function DispatcherPage() {
  const [allocations, setAllocations] = useState<CallCenterAllocation[]>([])
  const [savedAllocations, setSavedAllocations] = useState<CallCenterAllocation[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { getAllocations().then((saved) => { setAllocations(saved); setSavedAllocations(saved) }).catch(() => setError('Não foi possível carregar as configurações.')).finally(() => setLoading(false)) }, [])
  function update(id: string, percentage: number) { setAllocations((current) => current.map((item) => item.id === id ? { ...item, percentage } : item)); setMessage('') }
  async function save() {
    setSaving(true); setMessage(''); setError('')
    try { const saved = await saveAllocations(allocations); setAllocations(saved); setSavedAllocations(saved); setMessage('Configurações salvas para esta demonstração.') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Não foi possível salvar.') }
    finally { setSaving(false) }
  }
  const total = allocations.reduce((sum, item) => sum + item.percentage, 0)
  const deficit = Math.max(0, 100 - total)
  const reducedIds = new Set(allocations.filter((item) => item.percentage < (savedAllocations.find((saved) => saved.id === item.id)?.percentage ?? item.percentage)).map((item) => item.id))
  const balancingItems = allocations.filter((item) => !reducedIds.has(item.id))
  const previewItems = balancingItems.length > 0 ? balancingItems : allocations
  const previewPerItem = previewItems.length > 0 ? deficit / previewItems.length : 0
  return <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
    <div className="mb-7"><p className="text-sm text-indigo-500">ADMIN / CONFIGURAÇÃO</p><h1 className="mt-1 text-2xl font-semibold">Distribuição de leads</h1><p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Defina a participação de cada call center no dispatcher.</p></div>
    <div className="rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
      {loading ? <p className="py-8 text-center text-slate-500">Carregando configurações…</p> : error && allocations.length === 0 ? <p role="alert" className="py-8 text-center text-rose-500">{error}</p> : <>
        <div className="space-y-5">{allocations.map((item) => <Slider key={item.id} label={item.name} value={item.percentage} baselineValue={savedAllocations.find((saved) => saved.id === item.id)?.percentage ?? item.percentage} balancePreview={previewItems.some((preview) => preview.id === item.id) ? previewPerItem : 0} onChange={(percentage) => update(item.id, percentage)} />)}</div>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-5 dark:border-white/10"><p className={`text-sm font-medium ${total === 100 ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}`}>Total: {total}% {total !== 100 && '· precisa somar 100%'}</p><button disabled={saving || total !== 100} onClick={() => void save()} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50">{saving ? 'Salvando…' : 'Salvar configuração'}</button></div>
      </>}
    </div>
    {message && <p role="status" className="mt-4 text-sm text-emerald-600 dark:text-emerald-300">{message}</p>}{error && allocations.length > 0 && <p role="alert" className="mt-4 text-sm text-rose-500">{error}</p>}
  </section>
}
