import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { checkCallCenterHealth, listDeliveries, type Delivery, type ServiceHealth } from './deliveries.service'

type Experiment = {
  id: string
  title: string
  status: 'Disponível' | 'Em preparação'
  objective: string
  problem: string
  prerequisites: string[]
  steps: string[]
  expected: string
  explanation: string
}

const experiments: Experiment[] = [
  {
    id: 'outbox', title: 'Persistência da Outbox', status: 'Disponível',
    objective: 'Mostrar que a intenção de entrega nasce na mesma transação do lead.',
    problem: 'Como preservar a intenção de entregar mesmo antes de existir um publisher?',
    prerequisites: ['Gere leads no LAB Leads.', 'Atualize os dados observados nesta tela.'],
    steps: ['Gerar leads usando o LAB Leads.', 'Localizar o evento correspondente.', 'Conferir distribuição, destino e estado pendente.'],
    expected: 'Cada lead tem distribuição e evento lead.distributed com os mesmos identificadores.',
    explanation: 'A Outbox registra a intenção no PostgreSQL; a publicação ainda não foi implementada.',
  },
  {
    id: 'rabbitmq', title: 'RabbitMQ indisponível', status: 'Em preparação',
    objective: 'Apresentar a separação entre a transação do banco e a publicação no broker.',
    problem: 'O que acontece quando o banco confirma, mas o broker não responde?',
    prerequisites: ['RabbitMQ e publisher ainda não estão implementados.', 'A indisponibilidade será simulada manualmente quando o fluxo existir.'],
    steps: ['Indisponibilizar o RabbitMQ.', 'Criar leads e observar a Outbox.', 'Restabelecer o broker e observar as publicações.'],
    expected: 'Leads continuam aceitos e eventos permanecem pendentes até a publicação.',
    explanation: 'A tela apresenta o roteiro, mas não inventa um resultado enquanto o publisher não existe.',
  },
  {
    id: 'call-center', title: 'Call center indisponível', status: 'Em preparação',
    objective: 'Demonstrar falhas parciais em integrações HTTP externas.',
    problem: 'Como uma falha na Logicall deve afetar Salesbound e AtendeMais?',
    prerequisites: ['Os simuladores têm health check real.', 'Delivery worker e retries ainda não estão conectados.'],
    steps: ['Parar a Logicall manualmente.', 'Gerar leads e observar as falhas.', 'Recuperar a Logicall e observar novas tentativas.'],
    expected: 'A falha de um destino não interrompe os demais e tentativas posteriores recuperam a entrega.',
    explanation: 'Hoje só o health check é observável; não há entrega ou retry para executar o roteiro.',
  },
  {
    id: 'duplicates', title: 'Entrega duplicada', status: 'Em preparação',
    objective: 'Explicar por que Outbox não significa exatamente uma entrega.',
    problem: 'Como evitar processamento duplicado depois de uma publicação ambígua?',
    prerequisites: ['RabbitMQ, worker e identificação de duplicatas ainda não existem.'],
    steps: ['Publicar um evento.', 'Simular falha após publicar.', 'Entregar novamente e verificar idempotência.'],
    expected: 'O consumidor reconhece a duplicata e não repete o efeito.',
    explanation: 'O padrão garante persistência da intenção, não a confirmação atômica entre sistemas.',
  },
  {
    id: 'concurrency', title: 'Concorrência', status: 'Disponível',
    objective: 'Observar distribuição e Outbox quando muitos leads chegam juntos.',
    problem: 'O que permanece consistente quando 100 leads são criados simultaneamente?',
    prerequisites: ['Use o gerador de 100 leads do LAB Leads.', 'Atualize os dados após o envio.'],
    steps: ['Abra o LAB Leads.', 'Gere 100 leads válidos.', 'Compare a quantidade e os identificadores na Outbox.'],
    expected: 'Os eventos persistidos correspondem às distribuições criadas para os leads.',
    explanation: 'A evidência vem das linhas reais consultadas no backend, não de um contador fixo na interface.',
  },
]

const stateLabel: Record<string, string> = { available: 'Disponível', unavailable: 'Indisponível', 'not-implemented': 'Não implementado', unknown: 'Não verificado' }

const stateTone: Record<string, string> = {
  available: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  unavailable: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
  'not-implemented': 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  unknown: 'bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-slate-400',
}

const panelClass = 'rounded-xl border border-slate-200/80 bg-white p-5 dark:border-white/[.08] dark:bg-[#101827]'

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString('pt-BR') : '—'
}

function shortId(value: string | null) {
  return value ? value.slice(0, 8) : '—'
}

const experimentIcons: Record<string, string> = {
  outbox: '◈',
  rabbitmq: '⇢',
  'call-center': '⌁',
  duplicates: '⧉',
  concurrency: '⋮⋮',
}

const flowIcons: Record<string, string> = {
  Lead: '●',
  'PostgreSQL / Outbox': '▣',
  RabbitMQ: '≋',
  Worker: '⚙',
  'Call center HTTP': '⌁',
}

export function LabDeliveriesPage() {
  const [selectedId, setSelectedId] = useState('outbox')
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [counters, setCounters] = useState({ total: 0, pending: 0, published: 0 })
  const [health, setHealth] = useState<ServiceHealth[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [healthError, setHealthError] = useState('')
  const [copiedId, setCopiedId] = useState('')
  const selected = experiments.find((experiment) => experiment.id === selectedId) ?? experiments[0]

  const refresh = useCallback(async (initial = false) => {
    if (initial) setLoading(true)
    else setRefreshing(true)
    setError('')
    setHealthError('')
    const [deliveryResult, healthResult] = await Promise.allSettled([listDeliveries(), checkCallCenterHealth()])
    if (deliveryResult.status === 'fulfilled') {
      setDeliveries(deliveryResult.value.deliveries)
      setCounters(deliveryResult.value.counters)
    } else setError(deliveryResult.reason instanceof Error ? deliveryResult.reason.message : 'Falha ao consultar a Outbox.')
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
    else setHealthError(healthResult.reason instanceof Error ? healthResult.reason.message : 'Falha ao consultar simuladores.')
    setLoading(false)
    setRefreshing(false)
  }, [])

  useEffect(() => {
    void refresh(true)
    const timer = window.setInterval(() => void refresh(), 15000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const flow = useMemo(() => [
    { label: 'Lead', state: deliveries.length || counters.total ? 'available' : 'unknown' },
    { label: 'PostgreSQL / Outbox', state: error ? 'unknown' : loading ? 'unknown' : 'available' },
    { label: 'RabbitMQ', state: 'not-implemented' },
    { label: 'Worker', state: 'not-implemented' },
    { label: 'Call center HTTP', state: health.length ? (health.some((item) => item.state === 'available') ? 'available' : 'unavailable') : 'unknown' },
  ], [counters.total, deliveries.length, error, health, loading])

  async function copyIdentifier(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedId(value)
      window.setTimeout(() => setCopiedId((current) => current === value ? '' : current), 1400)
    } catch {
      // O UUID resumido continua visível mesmo quando a área de transferência não está disponível.
    }
  }

  return (
    <section className="mx-auto max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-[0.16em] text-indigo-400">LAB / Entregas</p>
          <h1 className="mt-1 text-[23px] font-semibold tracking-tight">Laboratório de entregas</h1>
          <p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">Experimentos guiados para explicar persistência, falhas e consistência.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={refreshing} className="rounded-lg border border-slate-300/80 px-3.5 py-2 text-[13px] font-medium transition hover:border-indigo-400 dark:border-white/[.10] dark:hover:bg-white/[.04]">
          {refreshing ? 'Atualizando...' : '↻ Atualizar dados'}
        </button>
      </header>

      <div className={`${panelClass} mt-6 p-4 sm:p-5`}>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-1">
          {flow.map((item, index) => (
            <div key={item.label} className="flex min-w-0 flex-1 items-center gap-2 sm:gap-1">
              <div className="min-w-0 flex-1 rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2.5 dark:border-white/[.07] dark:bg-white/[.025]">
                <div className="flex items-center gap-2"><span className="grid size-5 shrink-0 place-items-center text-sm text-slate-400" aria-hidden="true">{flowIcons[item.label]}</span><p className="truncate text-[13px] font-medium">{item.label}</p></div>
                <span className={`mt-2 inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${stateTone[item.state]}`}>{stateLabel[item.state]}</span>
              </div>
              {index < flow.length - 1 && <span className="hidden shrink-0 px-1 text-slate-500 sm:inline" aria-hidden="true">→</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,.85fr)]">
        <section aria-labelledby="experiments-title">
          <div className="mb-3 flex items-baseline justify-between"><h2 id="experiments-title" className="text-base font-semibold text-slate-700 dark:text-slate-200">Experimentos</h2><span className="text-xs text-slate-500 dark:text-slate-400">Selecione um roteiro</span></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {experiments.map((experiment) => (
              <button key={experiment.id} type="button" onClick={() => setSelectedId(experiment.id)} aria-pressed={selected.id === experiment.id} className={`min-h-[138px] rounded-xl border p-4 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 ${selected.id === experiment.id ? 'border-indigo-400/70 bg-indigo-500/[.08]' : 'border-slate-200/80 bg-white hover:border-indigo-300/70 hover:bg-slate-50 dark:border-white/[.08] dark:bg-[#101827] dark:hover:bg-white/[.04]'}`}>
                <div className="flex items-start justify-between gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-lg leading-none text-slate-500 dark:bg-white/[.07] dark:text-slate-300" aria-hidden="true">{experimentIcons[experiment.id]}</span><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${experiment.status === 'Disponível' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'}`}>{experiment.status}</span></div>
                <h3 className="mt-4 text-[15px] font-semibold leading-tight">{experiment.title}</h3>
                <p className="mt-1.5 line-clamp-2 text-[13px] leading-5 text-slate-500 dark:text-slate-400">{experiment.objective}</p>
              </button>
            ))}
          </div>
        </section>

        <article className={panelClass} aria-live="polite">
          <div className="flex items-start justify-between gap-4"><div><p className="text-xs font-semibold tracking-[0.12em] text-indigo-400">Experimento selecionado</p><h2 className="mt-1 text-[18px] font-semibold">{selected.title}</h2></div><span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${selected.status === 'Disponível' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'}`}>{selected.status}</span></div>
          <p className="mt-4 text-[13px] leading-5 text-slate-700 dark:text-slate-300"><span className="font-semibold text-slate-900 dark:text-slate-100">Problema:</span> {selected.problem}</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <div><h3 className="text-xs font-semibold text-slate-400">Pré-requisitos</h3><ul className="mt-2 space-y-1.5 text-[13px] leading-5 text-slate-600 dark:text-slate-300">{selected.prerequisites.map((item) => <li key={item}>• {item}</li>)}</ul></div>
            <div><h3 className="text-xs font-semibold text-slate-400">Passos</h3><ol className="mt-2 space-y-1.5 text-[13px] leading-5 text-slate-600 dark:text-slate-300">{selected.steps.map((item, index) => <li key={item}>{index + 1}. {item}</li>)}</ol></div>
          </div>
          <div className="mt-5 rounded-lg bg-slate-50/80 p-3.5 text-[13px] leading-5 dark:bg-white/[.045]"><p><span className="font-semibold">Resultado esperado:</span> {selected.expected}</p><p className="mt-2 text-slate-600 dark:text-slate-300"><span className="font-semibold text-slate-900 dark:text-slate-100">O que demonstra:</span> {selected.explanation}</p></div>
          {selected.id === 'outbox' || selected.id === 'concurrency' ? <Link to="/lab" className="mt-4 inline-flex text-[13px] font-medium text-indigo-600 hover:text-indigo-500 hover:underline dark:text-indigo-300 dark:hover:text-indigo-200">Abrir LAB Leads para gerar dados →</Link> : null}
        </article>
      </div>

      <section className={`${panelClass} mt-5`}>
        <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-[17px] font-semibold">Resultado observado</h2><p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">Dados reais retornados pelo backend.</p></div>{loading && <span className="text-xs text-slate-500">Consultando...</span>}</div>
        {error ? <p role="alert" className="mt-4 text-[13px] text-rose-600 dark:text-rose-300">{error}</p> : <div className="mt-4 grid grid-cols-3 gap-2.5"><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none">{counters.total}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Eventos</p></div><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none text-amber-700 dark:text-amber-300">{counters.pending}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Pendentes</p></div><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none text-emerald-700 dark:text-emerald-300">{counters.published}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Publicados</p></div></div>}
      </section>

      <section className={`${panelClass} mt-5`}><div className="flex items-baseline justify-between gap-3"><div><h2 className="text-[17px] font-semibold">Últimos eventos da Outbox</h2><p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">IDs abreviados; passe o cursor ou copie para ver o valor completo.</p></div><span className="text-xs text-slate-500 dark:text-slate-400">{deliveries.length} exibidos</span></div>{error ? <p className="mt-4 text-[13px] text-rose-600 dark:text-rose-300">A lista não pôde ser consultada.</p> : deliveries.length === 0 && !loading ? <p className="mt-4 text-[13px] text-slate-500 dark:text-slate-400">Nenhum evento encontrado. Gere leads no LAB Leads.</p> : <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[13px]"><thead className="border-b border-slate-200/70 text-xs text-slate-500 dark:border-white/[.07] dark:text-slate-400"><tr><th className="px-2 pb-3 pr-4 font-medium">Evento</th><th className="px-2 pb-3 pr-4 font-medium">Lead</th><th className="px-2 pb-3 pr-4 font-medium">Distribuição</th><th className="px-2 pb-3 pr-4 font-medium">Destino</th><th className="px-2 pb-3 pr-4 font-medium">Criado em</th><th className="px-2 pb-3 font-medium">Estado</th></tr></thead><tbody>{deliveries.map((delivery) => <tr key={delivery.eventId} className="border-b border-slate-200/60 last:border-0 hover:bg-slate-50/70 dark:border-white/[.045] dark:hover:bg-white/[.025]"><td className="px-2 py-3 pr-4 font-medium">{delivery.eventType}</td><td className="px-2 py-3 pr-4 font-mono"><button type="button" title={delivery.leadId ?? undefined} onClick={() => delivery.leadId && void copyIdentifier(delivery.leadId)} className="rounded px-1 py-0.5 text-slate-400 transition hover:bg-indigo-500/10 hover:text-indigo-300">{copiedId === delivery.leadId ? 'copiado' : shortId(delivery.leadId)}</button></td><td className="px-2 py-3 pr-4 font-mono"><button type="button" title={delivery.distributionId} onClick={() => void copyIdentifier(delivery.distributionId)} className="rounded px-1 py-0.5 text-slate-400 transition hover:bg-indigo-500/10 hover:text-indigo-300">{copiedId === delivery.distributionId ? 'copiado' : shortId(delivery.distributionId)}</button></td><td className="px-2 py-3 pr-4 font-medium">{delivery.callCenter}</td><td className="whitespace-nowrap px-2 py-3 pr-4 text-slate-500">{formatDate(delivery.createdAt)}</td><td className="px-2 py-3"><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${delivery.state === 'pending' ? 'bg-amber-500/10 text-amber-700 dark:text-amber-300' : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'}`}>{delivery.state === 'pending' ? 'Pendente' : 'Publicado'}</span></td></tr>)}</tbody></table></div>}</section>

      <section className={`${panelClass} mt-5`}><div><h2 className="text-[17px] font-semibold">Saúde dos simuladores HTTP</h2><p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">Consulta real feita pelo backend, com timeout curto.</p></div>{healthError ? <p role="alert" className="mt-4 text-[13px] text-rose-300">{healthError}</p> : health.length === 0 && !loading ? <p className="mt-4 text-[13px] text-slate-500 dark:text-slate-400">Estado não verificado.</p> : <div className="mt-4 grid gap-3 sm:grid-cols-3">{health.map((service) => <div key={service.id} className="rounded-lg border border-slate-200/70 bg-slate-50/60 px-3.5 py-3 dark:border-white/[.07] dark:bg-white/[.025]"><div className="flex items-center justify-between gap-3"><span className="text-[13px] font-semibold">{service.name}</span><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${stateTone[service.state]}`}>{stateLabel[service.state]}</span></div><p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{service.httpStatus ? `HTTP ${service.httpStatus}` : service.error ?? 'Sem resposta'}</p></div>)}</div>}</section>
    </section>
  )
}
