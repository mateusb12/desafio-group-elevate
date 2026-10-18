import { useEffect, useState } from 'react'
import { csrfHeaders } from '../auth/auth.service'

export function LabWebhooksPage() {
  const [leadIds, setLeadIds] = useState<string[]>([])
  const [quantity, setQuantity] = useState(100)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function refreshLeads() {
    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/api/leads/lab', {
        credentials: 'same-origin',
      })

      const data = await response.json() as {
        leads?: string[]
        error?: string
      }

      if (!response.ok) {
        throw new Error(data.error ?? 'Falha ao carregar leads.')
      }

      setLeadIds(Array.isArray(data.leads) ? data.leads : [])
    } catch (err) {
      setLeadIds([])
      setError(err instanceof Error ? err.message : 'Falha ao carregar leads.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refreshLeads()
  }, [])

  const selectedIds = leadIds.slice(
    0,
    Math.min(quantity, leadIds.length),
  )

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
      <p className="text-sm text-indigo-500">ADMIN / LAB</p>

      <h1 className="mt-1 text-2xl font-semibold">
        Laboratório de webhooks
      </h1>

      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Simule atualizações do call center, duplicatas e eventos fora de ordem.
      </p>

      <div className="mt-6 flex flex-wrap items-end gap-4 rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
        <label className="flex flex-col gap-2 text-sm">
          Quantidade de leads

          <input
            type="number"
            min={1}
            max={Math.max(1, leadIds.length)}
            value={Math.min(quantity, Math.max(1, leadIds.length))}
            onChange={(event) =>
              setQuantity(Math.max(1, Number(event.target.value) || 1))
            }
            className="h-10 w-28 rounded-lg border border-slate-300 bg-transparent px-3 dark:border-white/10"
          />
        </label>

        <button
          type="button"
          onClick={() => void refreshLeads()}
          disabled={loading}
          className="h-10 rounded-lg border border-slate-300 px-4 text-sm dark:border-white/10"
        >
          {loading ? 'Carregando...' : 'Atualizar leads'}
        </button>

        <span className="text-sm text-slate-500">
          {leadIds.length} lead(s) disponíveis (até 100 recentes)
        </span>
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-red-600">
          {error}
        </p>
      )}

      {!loading && leadIds.length === 0 && !error && (
        <p className="mt-4 text-sm text-slate-500">
          Nenhum lead disponível. Crie leads no LAB → Leads primeiro.
        </p>
      )}

      <EventSimulator leadIds={selectedIds} />
    </section>
  )
}

type WebhookPayload = {
  lead_id: string
  external_id: string
  status: string
  event_at: string
}

type WebhookResult = {
  lead: string
  status: string
  external: string
  http: number | null
  duplicate: boolean
  applied: boolean
  stale: boolean
  current: string
  error: string
}

function EventSimulator({ leadIds }: { leadIds: string[] }) {
  const [sending, setSending] = useState(false)
  const [notice, setNotice] = useState('')
  const [events, setEvents] = useState<WebhookResult[]>([])

  async function sendWebhooks() {
    if (sending || !leadIds.length) return

    setSending(true)
    setEvents([])
    setNotice(`Enviando webhooks para ${leadIds.length} lead(s)...`)

    const base = Date.now() + 60_000
    const batch: WebhookPayload[] = []

    const make = (
      lead: string,
      status: string,
      timestamp: number,
      external = crypto.randomUUID(),
    ): WebhookPayload => ({
      lead_id: lead,
      status,
      external_id: external,
      event_at: new Date(timestamp).toISOString(),
    })

    for (const [index, lead] of leadIds.entries()) {
      const t = base + index * 1000

      // Uma única operação cobre os fluxos válidos, inválidos, duplicados e
      // fora de ordem, deixando estados finais diferentes no dashboard.
      switch (index % 8) {
        case 0: {
          const sale = make(lead, 'sale', t + 20_000)
          batch.push(make(lead, 'contacted', t + 10_000), sale, sale)
          break
        }
        case 1:
          batch.push(
            make(lead, 'no_answer', t + 10_000),
            make(lead, 'callback', t + 20_000),
          )
          break
        case 2:
          batch.push(
            make(lead, 'contacted', t + 10_000),
            make(lead, 'qualified', t + 20_000),
          )
          break
        case 3:
          batch.push(
            make(lead, 'contacted', t + 10_000),
            make(lead, 'sale', t + 20_000),
            make(lead, 'refund', t + 30_000),
          )
          break
        case 4:
          // A venda chega antes de um evento mais antigo: o segundo evento
          // deve ser registrado, mas não pode rebaixar o status atual.
          batch.push(
            make(lead, 'sale', t + 30_000),
            make(lead, 'contacted', t + 10_000),
          )
          break
        case 5:
          batch.push(
            make(lead, 'invalid', t + 10_000),
            // O segundo payload é rejeitado pela API e aparece no relatório.
            make(lead, 'status-inexistente', t + 20_000),
          )
          break
        case 6: {
          const contacted = make(lead, 'contacted', t + 10_000)
          batch.push(contacted, contacted, make(lead, 'no_answer', t + 20_000))
          break
        }
        default:
          batch.push(
            make(lead, 'callback', t + 10_000),
            make(lead, 'qualified', t + 30_000),
            make(lead, 'contacted', t + 20_000),
          )
      }
    }

    try {
      for (const payload of batch) {
        try {
          const headers = new Headers(csrfHeaders())
          headers.set('Content-Type', 'application/json')

          const response = await fetch('/api/api/webhooks/callcenter', {
            method: 'POST',
            credentials: 'same-origin',
            headers,
            body: JSON.stringify(payload),
          })

          const body = await response.json() as {
            duplicate?: boolean
            applied?: boolean
            out_of_order?: boolean
            current_status?: string
            error?: string
          }

          setEvents((old) => [...old, {
            lead: payload.lead_id,
            status: payload.status,
            external: payload.external_id,
            http: response.status,
            duplicate: !!body.duplicate,
            applied: !!body.applied,
            stale: !!body.out_of_order,
            current: body.current_status ?? '—',
            error: body.error ?? '',
          }])
        } catch (error) {
          setEvents((old) => [...old, {
            lead: payload.lead_id,
            status: payload.status,
            external: payload.external_id,
            http: null,
            duplicate: false,
            applied: false,
            stale: false,
            current: '—',
            error: error instanceof Error ? error.message : 'Erro de rede',
          }])
        }
      }

      setNotice(
        `${batch.length} requisição(ões) enviadas. Confira HTTP, duplicata e fora de ordem.`,
      )
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="mt-7 rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
      <h2 className="font-semibold">Simular eventos do call center</h2>

      <p className="mt-1 text-sm text-slate-500">
        Envia uma operação completa para POST /api/webhooks/callcenter, com
        eventos válidos, inválidos, duplicados e fora de ordem.
      </p>

      <p className="mt-2 text-sm text-slate-500">
        Leads disponíveis: {leadIds.length}. Gere e envie leads válidos acima para começar.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <select
          aria-label="Cenário de webhooks"
          className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm dark:border-white/10 dark:bg-[#111827]"
        >
          <option>Operação completa (todos os cenários)</option>
        </select>

        <button
          type="button"
          onClick={() => void sendWebhooks()}
          disabled={sending || !leadIds.length}
          className="min-h-11 rounded-lg bg-indigo-600 px-4 text-sm font-semibold text-white disabled:opacity-40"
        >
          {sending ? 'Gerando operação...' : 'Gerar operação demonstrativa'}
        </button>
      </div>

      {notice && (
        <p role="status" className="mt-3 text-sm text-indigo-500">
          {notice}
        </p>
      )}

      {events.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200 dark:border-white/10">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs text-slate-500 dark:border-white/10">
                {[
                  'Lead', 'Evento', 'External ID', 'HTTP',
                  'Duplicado?', 'Aplicado?', 'Fora de ordem?', 'Status atual / Erro',
                ].map((column) => (
                  <th key={column} className="px-3 py-2">{column}</th>
                ))}
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-100 dark:divide-white/5">
              {events.map((item, index) => (
                <tr key={index}>
                  <td className="px-3 py-2 font-mono text-xs">{item.lead.slice(0, 8)}</td>
                  <td className="px-3 py-2">{item.status}</td>
                  <td className="px-3 py-2 font-mono text-xs">{item.external.slice(0, 8)}</td>
                  <td className="px-3 py-2">{item.http ?? '—'}</td>
                  <td className="px-3 py-2">{item.duplicate ? 'SIM' : 'não'}</td>
                  <td className="px-3 py-2">{item.applied ? 'SIM' : 'não'}</td>
                  <td className="px-3 py-2">{item.stale ? 'SIM' : 'não'}</td>
                  <td className="px-3 py-2">{item.error || item.current}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
