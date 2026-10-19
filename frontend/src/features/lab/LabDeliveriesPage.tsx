import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import { checkCallCenterHealth, checkDeliveryWorkerHealth, checkOutboxServiceHealth, checkRabbitMqHealth, listDeliveries, type Delivery, type ServiceHealth } from './deliveries.service'

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
    problem: 'Como garantir que a mensagem não seja perdida antes de ser enviada?',
    prerequisites: ['Gere leads no LAB Leads antes de iniciar o roteiro.', 'Atualize os dados observados nesta tela.'],
    steps: ['Localizar o evento correspondente ao lead.', 'Conferir distribuição, destino e estado pendente.', 'Verificar se o lead, a distribuição e o evento possuem os mesmos identificadores.'],
    expected: 'Para cada lead, há uma linha de distribuição e uma linha do evento lead.distributed com os mesmos IDs.',
    explanation: 'A Outbox registra a intenção no PostgreSQL; o publisher a encaminha ao RabbitMQ separadamente.',
  },
  {
    id: 'rabbitmq', title: 'RabbitMQ indisponível', status: 'Disponível',
    objective: 'Apresentar a separação entre a transação do banco e a publicação no broker.',
    problem: 'O que acontece quando o banco salva o lead, mas a mensagem não pode ser enviada?',
    prerequisites: ['Use o LAB Leads para gerar novos leads.'],
    steps: ['Execute `docker compose stop rabbitmq`.', 'Gere leads e observe os eventos pendentes na Outbox aumentando.', 'Execute `docker compose start rabbitmq` e atualize os dados.'],
    expected: 'O lead é salvo mesmo quando a mensagem não pode ser enviada. Ela fica pendente e é enviada depois.',
    explanation: 'A API salva o lead no PostgreSQL. O publisher faz retry até conseguir enviar a mensagem.',
  },
  {
    id: 'call-center', title: 'Call center indisponível', status: 'Disponível',
    objective: 'Demonstrar falhas parciais em integrações HTTP externas.',
    problem: 'Como uma falha na Logicall deve afetar Salesbound e AtendeMais?',
    prerequisites: ['O serviço delivery-worker está em execução.'],
    steps: ['Execute `docker compose stop logicall`.', 'Gere leads e observe Salesbound/AtendeMais entregues e Logicall em retry.', 'Execute `docker compose start logicall` e atualize os dados.'],
    expected: 'A falha de um destino não interrompe os demais e tentativas posteriores recuperam a entrega.',
    explanation: 'Cada mensagem é processada em uma tarefa independente; o retry de Logicall não bloqueia os demais destinos.',
  },
  {
    id: 'duplicates', title: 'Entrega duplicada', status: 'Disponível',
    objective: 'Explicar por que Outbox não significa exatamente uma entrega.',
    problem: 'Como evitar que a mesma mensagem seja processada mais de uma vez?',
    prerequisites: ['Consulte os logs do delivery-worker.'],
    steps: ['Gere um lead e anote o event_id.', 'Republique a mesma mensagem pelo RabbitMQ Management ou reinicie o worker durante a entrega.', 'Verifique `duplicate=true` no simulador e um único efeito persistido.'],
    expected: 'O consumidor reconhece a duplicata e não repete o efeito.',
    explanation: 'O fluxo é at-least-once; a tabela local e a chave event_id do simulador tornam a repetição segura.',
  },
  {
    id: 'concurrency', title: 'Concorrência', status: 'Disponível',
    objective: 'Observar distribuição e Outbox quando muitos leads chegam juntos.',
    problem: 'O sistema consegue criar 100 leads ao mesmo tempo sem perder dados?',
    prerequisites: ['Nenhum.'],
    steps: ['Abra o LAB Leads.', 'Gere 100 leads válidos.', 'Atualize os dados.', 'Compare a quantidade e os IDs na Outbox.'],
    expected: 'Para cada lead criado, há uma linha em distributions e uma linha em outbox_pending_deliveries para o evento lead.distributed.',
    explanation: 'A Outbox mostra os registros salvos no banco e seus IDs.',
  },
]

const stateLabel: Record<string, string> = { available: 'Online', unavailable: 'Offline', unknown: 'Não verificado', pending: 'Pendente', retry_scheduled: 'Retry agendado', published: 'Publicado', delivered: 'Entregue', failed: 'Falha final' }

const stateTone: Record<string, string> = {
  available: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  unavailable: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
  unknown: 'bg-slate-100 text-slate-500 dark:bg-white/5 dark:text-slate-400',
  retry_scheduled: 'bg-amber-500/10 text-amber-700 dark:text-amber-300',
  published: 'bg-sky-500/10 text-sky-700 dark:text-sky-300',
  delivered: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  failed: 'bg-rose-500/10 text-rose-700 dark:text-rose-300',
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
  'Outbox Service': '⇢',
  Worker: '⚙',
  'Call center HTTP': '⌁',
}

const callCenterBarTone: Record<string, string> = {
  'call-center-a': 'bg-indigo-400',
  'call-center-b': 'bg-amber-400',
  'call-center-c': 'bg-cyan-400',
}

export function LabDeliveriesPage() {
  const [selectedId, setSelectedId] = useState('outbox')
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [counters, setCounters] = useState({ total: 0, pending: 0, published: 0, deliveryTotal: 0, initialPending: 0, delivered: 0, retrying: 0, failed: 0 })
  const [health, setHealth] = useState<ServiceHealth[]>([])
  const [processHealth, setProcessHealth] = useState<ServiceHealth[]>([])
  const [rabbitMqState, setRabbitMqState] = useState<'available' | 'unavailable' | 'unknown'>('unknown')
  const [rabbitMqMessageCount, setRabbitMqMessageCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [healthError, setHealthError] = useState('')
  const [copiedId, setCopiedId] = useState('')
  const refreshInFlight = useRef(false)
  const selected = experiments.find((experiment) => experiment.id === selectedId) ?? experiments[0]

  const refresh = useCallback(async (initial = false) => {
    if (refreshInFlight.current) return
    refreshInFlight.current = true
    if (initial) setLoading(true)
    else setRefreshing(true)
    setError('')
    setHealthError('')
    const [deliveryResult, healthResult, rabbitMqResult, outboxResult, workerResult] = await Promise.allSettled([listDeliveries(), checkCallCenterHealth(), checkRabbitMqHealth(), checkOutboxServiceHealth(), checkDeliveryWorkerHealth()])
    if (deliveryResult.status === 'fulfilled') {
      setDeliveries(deliveryResult.value.deliveries)
      setCounters(deliveryResult.value.counters)
    } else setError(deliveryResult.reason instanceof Error ? deliveryResult.reason.message : 'Falha ao consultar a Outbox.')
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value)
    else setHealthError(healthResult.reason instanceof Error ? healthResult.reason.message : 'Falha ao consultar simuladores.')
    if (rabbitMqResult.status === 'fulfilled') {
      setRabbitMqState(rabbitMqResult.value.state)
      setRabbitMqMessageCount(rabbitMqResult.value.messageCount ?? null)
    } else {
      setRabbitMqMessageCount(null)
    }
    if (outboxResult.status === 'fulfilled') {
      setProcessHealth((current) => [...current.filter((item) => item.id !== 'outbox-service'), outboxResult.value])
    } else {
      setProcessHealth((current) => [...current.filter((item) => item.id !== 'outbox-service'), { name: 'Outbox Service', id: 'outbox-service', state: 'unknown' }])
    }
    if (workerResult.status === 'fulfilled') {
      setProcessHealth((current) => [...current.filter((item) => item.id !== 'delivery-worker'), workerResult.value])
    } else {
    setProcessHealth((current) => [...current.filter((item) => item.id !== 'delivery-worker'), { name: 'Worker', id: 'delivery-worker', state: 'unknown' }])
    }
    setLoading(false)
    setRefreshing(false)
    refreshInFlight.current = false
  }, [])

  useEffect(() => {
    void refresh(true)
    const timer = window.setInterval(() => void refresh(), 1000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const flow = useMemo(() => [
    { label: 'Lead', state: deliveries.length || counters.total ? 'available' : 'unknown', processedCount: undefined, publishedCount: undefined, markedPublishedCount: undefined, messageCount: undefined },
    { label: 'PostgreSQL / Outbox', state: error ? 'unknown' : loading ? 'unknown' : 'available', processedCount: undefined, publishedCount: undefined, markedPublishedCount: undefined, messageCount: undefined },
    { label: 'Outbox Service', state: processHealth.find((item) => item.id === 'outbox-service')?.state ?? 'unknown', processedCount: undefined, publishedCount: processHealth.find((item) => item.id === 'outbox-service')?.publishedCount, markedPublishedCount: processHealth.find((item) => item.id === 'outbox-service')?.markedPublishedCount, messageCount: undefined },
    { label: 'RabbitMQ', state: rabbitMqState, processedCount: undefined, publishedCount: undefined, markedPublishedCount: undefined, messageCount: rabbitMqMessageCount ?? undefined },
    { label: 'Worker', state: processHealth.find((item) => item.id === 'delivery-worker')?.state ?? 'unknown', processedCount: processHealth.find((item) => item.id === 'delivery-worker')?.processedCount, publishedCount: undefined, markedPublishedCount: undefined, messageCount: undefined },
  ], [counters.total, deliveries.length, error, loading, processHealth, rabbitMqMessageCount, rabbitMqState])

  const callCenters = health.length ? health : [
    { name: 'Logicall', id: 'call-center-a', state: 'unknown' as const },
    { name: 'Salesbound', id: 'call-center-b', state: 'unknown' as const },
    { name: 'AtendeMais', id: 'call-center-c', state: 'unknown' as const },
  ]
  const acceptedCounts = callCenters
    .map((item) => item.acceptedCount)
    .filter((count): count is number => count !== undefined)
  const maxAcceptedCount = Math.max(0, ...acceptedCounts)

  async function copyIdentifier(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedId(value)
      window.setTimeout(() => setCopiedId((current) => current === value ? '' : current), 1400)
    } catch {
      // O UUID resumido continua visível mesmo quando a área de transferência não está disponível.
    }
  }

  function renderStep(step: string) {
    const command = step.match(/^(.*?)`([^`]+)`(.*)$/)
    if (!command) return step

    const [, before, value, after] = command
    return (
      <>
        {before}
        <span className="my-1 inline-flex max-w-full items-center overflow-hidden rounded-md border border-slate-700/70 bg-slate-950/60 align-middle dark:border-white/[.10] dark:bg-black/20">
          <code className="min-w-0 truncate px-2 py-1 font-mono text-[12px] text-slate-300">{value}</code>
          <button
            type="button"
            onClick={() => void copyIdentifier(value)}
            title="Copiar comando"
            aria-label={`Copiar comando ${value}`}
            className="grid size-7 shrink-0 place-items-center border-l border-slate-700/70 text-slate-400 transition hover:bg-indigo-500/15 hover:text-indigo-300 dark:border-white/[.10]"
          >
            {copiedId === value ? '✓' : '⧉'}
          </button>
        </span>
        {after.startsWith(' e ') ? <span className="block">{after}</span> : after}
      </>
    )
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

      <div className="mt-6 flex flex-col gap-4">
        <div className={`${panelClass} p-4 sm:p-5`}>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-1">
            {flow.slice(0, 3).map((item, index) => (
              <div key={item.label} className="flex min-w-0 flex-1 items-center gap-2 sm:gap-1">
                <div className="min-w-0 flex-1 rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2.5 dark:border-white/[.07] dark:bg-white/[.025]">
                  <div className="flex items-center gap-2"><span className="grid size-5 shrink-0 place-items-center text-sm text-slate-400" aria-hidden="true">{flowIcons[item.label]}</span><p className="truncate text-[13px] font-medium">{item.label}</p></div>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${stateTone[item.state]}`}>{stateLabel[item.state]}</span>
                    {item.label === 'Outbox Service' && item.publishedCount !== undefined && <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">{item.publishedCount} publicados no Rabbit</span>}
                    {item.label === 'Outbox Service' && item.markedPublishedCount !== undefined && <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">{item.markedPublishedCount} marcados na Outbox</span>}
                    {item.label === 'PostgreSQL / Outbox' && <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">{counters.pending} eventos pendentes na Outbox</span>}
                  </div>
                </div>
                {index < 2 && <span className="hidden shrink-0 px-1 text-slate-500 sm:inline" aria-hidden="true">→</span>}
              </div>
            ))}
          </div>
        </div>

        <div className={`${panelClass} p-4 sm:p-5`}>
          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_minmax(0,1.2fr)] sm:items-center">
            {flow.slice(3, 4).map((item) => (
              <div key={item.label} className="min-w-0 rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2.5 dark:border-white/[.07] dark:bg-white/[.025]">
                <div className="flex items-center gap-2"><span className="grid size-5 shrink-0 place-items-center text-sm text-slate-400" aria-hidden="true">{flowIcons[item.label]}</span><p className="truncate text-[13px] font-medium">{item.label}</p></div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${stateTone[item.state]}`}>{stateLabel[item.state]}</span>
                  {item.messageCount !== undefined && <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">{item.messageCount} na fila</span>}
                </div>
              </div>
            ))}
            <span className="hidden self-center px-1 text-slate-500 sm:inline" aria-hidden="true">→</span>
            {flow.slice(4, 5).map((item) => (
              <div key={item.label} className="min-w-0 rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2.5 dark:border-white/[.07] dark:bg-white/[.025]">
                <div className="flex items-center gap-2"><span className="grid size-5 shrink-0 place-items-center text-sm text-slate-400" aria-hidden="true">{flowIcons[item.label]}</span><p className="truncate text-[13px] font-medium">{item.label}</p></div>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${stateTone[item.state]}`}>{stateLabel[item.state]}</span>
                  {item.processedCount !== undefined && <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">{item.processedCount} processados até agora</span>}
                </div>
              </div>
            ))}
            <div className="flex flex-col gap-2">
              {callCenters.map((item) => (
                <div key={item.id} className="flex min-w-0 items-center gap-1">
                  <span className="hidden shrink-0 px-1 text-slate-500 sm:inline" aria-hidden="true">→</span>
                  <div className="min-w-0 flex-1 rounded-lg border border-slate-200/70 bg-slate-50/70 px-3 py-2.5 dark:border-white/[.07] dark:bg-white/[.025]">
                    <div className="flex items-center gap-2"><span className="grid size-5 shrink-0 place-items-center text-sm text-slate-400" aria-hidden="true">⌁</span><p className="truncate text-[13px] font-medium">{item.name}</p></div>
                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${stateTone[item.state]}`}>{stateLabel[item.state]}</span>
                      {item.acceptedCount !== undefined && <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-white/5 dark:text-slate-300">{item.acceptedCount} atendidos</span>}
                    </div>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200/80 dark:bg-white/[.07]" aria-label={item.acceptedCount !== undefined ? `${item.acceptedCount} atendidos em relação ao maior contador` : 'Contador indisponível'}>
                      <div
                        className={`h-full rounded-full transition-[width] duration-500 ${callCenterBarTone[item.id] ?? 'bg-slate-400'}`}
                        style={{ width: `${maxAcceptedCount > 0 && item.acceptedCount !== undefined ? (item.acceptedCount / maxAcceptedCount) * 100 : 0}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(0,.9fr)_minmax(500px,1.1fr)]">
        <section aria-labelledby="experiments-title">
          <div className="mb-3 flex items-baseline justify-between"><h2 id="experiments-title" className="text-base font-semibold text-slate-700 dark:text-slate-200">Experimentos</h2><span className="text-xs text-slate-500 dark:text-slate-400">Selecione um roteiro</span></div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {experiments.map((experiment) => (
              <button key={experiment.id} type="button" onClick={() => setSelectedId(experiment.id)} aria-pressed={selected.id === experiment.id} className={`min-h-[138px] rounded-xl border p-4 text-left transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 ${selected.id === experiment.id ? 'border-indigo-400/70 bg-indigo-500/[.08]' : 'border-slate-200/80 bg-white hover:border-indigo-300/70 hover:bg-slate-50 dark:border-white/[.08] dark:bg-[#101827] dark:hover:bg-white/[.04]'}`}>
                <div className="flex items-start gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-lg leading-none text-slate-500 dark:bg-white/[.07] dark:text-slate-300" aria-hidden="true">{experimentIcons[experiment.id]}</span></div>
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
            <div><h3 className="text-xs font-semibold text-slate-400">Passos</h3><ol className="mt-2 space-y-1.5 text-[13px] leading-5 text-slate-600 dark:text-slate-300">{selected.steps.map((item, index) => <li key={item}>{index + 1}. {renderStep(item)}</li>)}</ol></div>
          </div>
          <div className="mt-5 rounded-lg bg-slate-50/80 p-3.5 text-[13px] leading-5 dark:bg-white/[.045]"><p><span className="font-semibold">Resultado esperado:</span> {selected.expected}</p><p className="mt-2 text-slate-600 dark:text-slate-300"><span className="font-semibold text-slate-900 dark:text-slate-100">O que demonstra:</span> {selected.explanation}</p></div>
          {selected.id === 'outbox' || selected.id === 'concurrency' ? <Link to="/lab" className="mt-4 inline-flex text-[13px] font-medium text-indigo-600 hover:text-indigo-500 hover:underline dark:text-indigo-300 dark:hover:text-indigo-200">Abrir LAB Leads para gerar dados →</Link> : null}
        </article>
      </div>

      <section className={`${panelClass} mt-5`}>
        <div className="flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-[17px] font-semibold">Resultado observado</h2><p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">Dados reais retornados pelo backend.</p></div>{loading && <span className="text-xs text-slate-500">Consultando...</span>}</div>
        {error ? <p role="alert" className="mt-4 text-[13px] text-rose-600 dark:text-rose-300">{error}</p> : <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4"><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none">{counters.total}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Persistidos na Outbox</p></div><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none text-emerald-700 dark:text-emerald-300">{counters.published}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Publicados no RabbitMQ</p></div><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none text-emerald-700 dark:text-emerald-300">{counters.delivered}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Entregues por HTTP</p></div><div className="rounded-lg border border-slate-200/70 bg-slate-50/70 px-3.5 py-3 dark:border-white/[.06] dark:bg-white/[.025]"><p className="text-xl font-semibold leading-none text-amber-700 dark:text-amber-300">{counters.retrying + counters.failed}</p><p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">Retry / falha final</p></div></div>}
      </section>

<section className={`${panelClass} mt-5`}><div className="flex items-baseline justify-between gap-3"><div><h2 className="text-[17px] font-semibold">Últimos eventos da Outbox</h2><p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">IDs abreviados; estado separa publicação de entrega HTTP.</p></div><span className="text-xs text-slate-500 dark:text-slate-400">{deliveries.length} exibidos</span></div>{error ? <p className="mt-4 text-[13px] text-rose-600 dark:text-rose-300">A lista não pôde ser consultada.</p> : deliveries.length === 0 && !loading ? <p className="mt-4 text-[13px] text-slate-500 dark:text-slate-400">Nenhum evento encontrado. Gere leads no LAB Leads.</p> : <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[13px]"><thead className="border-b border-slate-200/70 text-xs text-slate-500 dark:border-white/[.07] dark:text-slate-400"><tr><th className="px-2 pb-3 pr-4 font-medium">Evento</th><th className="px-2 pb-3 pr-4 font-medium">Lead</th><th className="px-2 pb-3 pr-4 font-medium">Distribuição</th><th className="px-2 pb-3 pr-4 font-medium">Destino</th><th className="px-2 pb-3 pr-4 font-medium">Criado em</th><th className="px-2 pb-3 font-medium">Estado</th></tr></thead><tbody>{deliveries.map((delivery) => <tr key={delivery.eventId} className="border-b border-slate-200/60 last:border-0 hover:bg-slate-50/70 dark:border-white/[.045] dark:hover:bg-white/[.025]"><td className="px-2 py-3 pr-4 font-medium">{delivery.eventType}</td><td className="px-2 py-3 pr-4 font-mono"><button type="button" title={delivery.leadId ?? undefined} onClick={() => delivery.leadId && void copyIdentifier(delivery.leadId)} className="rounded px-1 py-0.5 text-slate-400 transition hover:bg-indigo-500/10 hover:text-indigo-300">{copiedId === delivery.leadId ? 'copiado' : shortId(delivery.leadId)}</button></td><td className="px-2 py-3 pr-4 font-mono"><button type="button" title={delivery.distributionId} onClick={() => void copyIdentifier(delivery.distributionId)} className="rounded px-1 py-0.5 text-slate-400 transition hover:bg-indigo-500/10 hover:text-indigo-300">{copiedId === delivery.distributionId ? 'copiado' : shortId(delivery.distributionId)}</button></td><td className="px-2 py-3 pr-4 font-medium">{delivery.callCenter}</td><td className="whitespace-nowrap px-2 py-3 pr-4 text-slate-500">{formatDate(delivery.createdAt)}</td><td className="px-2 py-3"><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${stateTone[delivery.state]}`}>{delivery.state === 'pending' ? 'Aguardando retry' : delivery.state === 'retry_scheduled' ? 'Retry agendado' : delivery.state === 'failed' ? 'Falha final' : delivery.state === 'delivered' ? 'Entregue por HTTP' : 'Publicado'}</span></td></tr>)}</tbody></table></div>}</section>

      <section className={`${panelClass} mt-5`}><div><h2 className="text-[17px] font-semibold">Saúde dos simuladores HTTP</h2><p className="mt-1 text-[13px] text-slate-500 dark:text-slate-400">Consulta real feita pelo backend, com timeout curto.</p></div>{healthError ? <p role="alert" className="mt-4 text-[13px] text-rose-300">{healthError}</p> : health.length === 0 && !loading ? <p className="mt-4 text-[13px] text-slate-500 dark:text-slate-400">Estado não verificado.</p> : <div className="mt-4 grid gap-3 sm:grid-cols-3">{health.map((service) => <div key={service.id} className="rounded-lg border border-slate-200/70 bg-slate-50/60 px-3.5 py-3 dark:border-white/[.07] dark:bg-white/[.025]"><div className="flex items-center justify-between gap-3"><span className="text-[13px] font-semibold">{service.name}</span><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${stateTone[service.state]}`}>{stateLabel[service.state]}</span></div><p className="mt-2 text-xs text-slate-500 dark:text-slate-400">{service.httpStatus ? `HTTP ${service.httpStatus}` : service.error ?? 'Sem resposta'}</p></div>)}</div>}</section>
    </section>
  )
}
