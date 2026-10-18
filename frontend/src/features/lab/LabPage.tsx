import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { fakerPT_BR as faker } from '@faker-js/faker'
import { clearLabLeads as clearLabLeadsRequest, listLeadCatalog, submitLead, type LeadCatalog, type LeadPayload } from './lab.service'

type Scenario =
  | 'valid'
  | 'invalid-email'
  | 'invalid-phone'
  | 'missing-name'
  | 'unknown-product'
  | 'unknown-funnel'
  | 'invalid-utm'
  | 'invalid-types'
  | 'duplicate'
  | 'mixed'

type PreviewLead = {
  payload: LeadPayload
  scenario: Scenario
  idempotencyKey: string
}
type Result = { http: number | null; ok: boolean; ms: number; detail: string }
type Expected = { http: number; detail: string }


const scenarios: { id: Scenario; label: string; description: string }[] = [
  { id: 'valid', label: 'Leads válidos', description: 'Cadastros completos para testar o recebimento.' },
  { id: 'invalid-email', label: 'E-mail inválido', description: 'E-mails sem formato válido.' },
  { id: 'invalid-phone', label: 'Telefone inválido', description: 'Telefones incompletos.' },
  { id: 'missing-name', label: 'Nome ausente', description: 'Payloads sem o campo obrigatório name.' },
  { id: 'unknown-product', label: 'Produto inexistente', description: 'Produtos que não devem existir no cadastro.' },
  { id: 'unknown-funnel', label: 'Funil inexistente', description: 'Funis que não devem existir no cadastro.' },
  { id: 'invalid-utm', label: 'UTM malformada', description: 'UTM como texto, em vez de objeto.' },
  { id: 'invalid-types', label: 'Tipos incorretos', description: 'Nome numérico em vez de texto.' },
  { id: 'duplicate', label: 'Leads duplicados', description: 'Repete exatamente o mesmo payload para testar idempotência.' },
  { id: 'mixed', label: 'Operação completa', description: 'Mantém a quantidade final de leads e executa testes inválidos e de duplicidade em paralelo.' },
]
const selectableScenarios: Scenario[] = ['valid', 'mixed']

const sources = ['facebook', 'instagram', 'google', 'youtube']
function randomLead(catalog: LeadCatalog): LeadPayload {
  const name = faker.person.fullName()
  const [firstName, ...lastName] = name.split(' ')
  const source = faker.helpers.arrayElement(sources)
  const campaign = `campaign-${faker.string.numeric(3)}`
  const ddd = faker.helpers.arrayElement(['11', '21', '31', '41', '85'])
  const association = faker.helpers.arrayElement(catalog.associations)

  return {
    name,
    email: faker.internet.email({ firstName, lastName: lastName.join(' ') }).toLowerCase(),
    phone: `+55${ddd}9${faker.string.numeric(8)}`,
    product: association.productCode,
    funnel: association.funnelCode,
    source,
    campaign,
    affiliate_id: faker.string.numeric(3),
    utm: {
      source,
      medium: source === 'google' ? 'cpc' : 'social',
      campaign,
      content: `ad-${faker.string.numeric(2)}`,
    },
  }
}

function leadForScenario(scenario: Scenario, catalog: LeadCatalog): PreviewLead {
  const lead = randomLead(catalog)
  switch (scenario) {
    case 'invalid-email': lead.email = 'email-sem-arroba'; break
    case 'invalid-phone': lead.phone = '123'; break
    case 'missing-name': delete lead.name; break
    case 'unknown-product': lead.product = 'produto-inexistente'; break
    case 'unknown-funnel': lead.funnel = 'funil-inexistente'; break
    case 'invalid-utm': lead.utm = 'utm-invalida'; break
    case 'invalid-types': lead.name = 12345; break
  }
  return { payload: lead, scenario, idempotencyKey: crypto.randomUUID() }
}

function expectedForScenario(scenario: Scenario, index: number): Expected {
  switch (scenario) {
    case 'valid': return { http: 201, detail: 'ID criado' }
    case 'invalid-email': return { http: 400, detail: 'E-mail inválido.' }
    case 'invalid-phone': return { http: 400, detail: 'Telefone inválido.' }
    case 'missing-name': return { http: 400, detail: 'Campo inválido ou ausente: name.' }
    case 'unknown-product': return { http: 400, detail: 'Produto desconhecido.' }
    case 'unknown-funnel': return { http: 400, detail: 'Funil desconhecido.' }
    case 'invalid-utm': return { http: 400, detail: 'UTM deve ser um objeto.' }
    case 'invalid-types': return { http: 400, detail: 'Campo inválido ou ausente: name.' }
    case 'duplicate': return index === 0
      ? { http: 201, detail: 'ID criado' }
      : { http: 200, detail: 'Mesmo ID da primeira linha' }
    case 'mixed': return { http: 201, detail: 'Lead criado após testes auxiliares' }
  }
}

function resultPresentation(scenario: Scenario, index: number, ok: boolean) {
  if (!ok) return { label: '✕ FALHOU', className: 'text-red-600' }
  if (scenario === 'valid' || scenario === 'mixed') return { label: '✓ ACEITO', className: 'text-emerald-600' }
  if (scenario === 'duplicate' && index > 0) return { label: '↺ DUPLICATA', className: 'text-sky-600' }
  if (scenario === 'duplicate') return { label: '✓ ACEITO', className: 'text-emerald-600' }
  return { label: '✓ REJEITADO COMO ESPERADO', className: 'text-amber-600' }
}

function invalidProbeFor(payload: LeadPayload, index: number): LeadPayload {
  const probe = { ...payload }
  switch (index % 7) {
    case 0: probe.email = 'email-sem-arroba'; break
    case 1: probe.phone = '123'; break
    case 2: probe.product = 'produto-inexistente'; break
    case 3: probe.funnel = 'funil-inexistente'; break
    case 4: probe.utm = 'utm-invalida'; break
    case 5: probe.name = 12345; break
    default: delete probe.name
  }
  return probe
}

export function LabPage() {
  const [quantity, setQuantity] = useState(5)
  const [catalog, setCatalog] = useState<LeadCatalog>({ products: [], funnels: [], associations: [] })
  const [catalogError, setCatalogError] = useState('')
  const [scenario, setScenario] = useState<Scenario>('mixed')
  const [leads, setLeads] = useState<PreviewLead[]>([])
  const [notice, setNotice] = useState('')
  const [sending, setSending] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [results, setResults] = useState<Record<number, Result>>({})

  const payload = useMemo(() => JSON.stringify(leads.map(({ payload: lead }) => lead), null, 2), [leads])
  const report = useMemo(() => JSON.stringify(leads.map(({ payload: lead, scenario: itemScenario }, index) => ({
    payload: lead,
    scenario: itemScenario,
    esperado: expectedForScenario(itemScenario, index),
    resultado: results[index] ?? null,
  })), null, 2), [leads, results])
  const selected = scenarios.find((item) => item.id === scenario)!

  useEffect(() => {
    let cancelled = false
    void listLeadCatalog()
      .then((nextCatalog) => {
        if (!nextCatalog.products.length || !nextCatalog.funnels.length || !nextCatalog.associations.length) {
          throw new Error('Não há produtos, funis ou associações ativas cadastrados.')
        }
        if (!cancelled) setCatalog(nextCatalog)
      })
      .catch((error: unknown) => {
        if (!cancelled) setCatalogError(error instanceof Error ? error.message : 'Erro no catálogo.')
      })
    return () => { cancelled = true }
  }, [])

  function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!catalog.associations.length) {
      setNotice(catalogError || 'Aguardando catálogo de produtos e funis.')
      return
    }
    const amount = Math.min(100, Math.max(1, quantity))
    const repeated = scenario === 'duplicate' ? randomLead(catalog) : null
    const repeatedKey = repeated ? crypto.randomUUID() : null
    const generated = Array.from({ length: amount }, () => {
      if (repeated) {
        return {
          payload: repeated,
          scenario: 'duplicate' as const,
          idempotencyKey: repeatedKey!,
        }
      }
      if (scenario === 'mixed') {
        return { ...leadForScenario('valid', catalog), scenario: 'mixed' as const }
      }
      return leadForScenario(scenario, catalog)
    })
    setLeads(generated)
    setResults({})
    setNotice(`${amount} lead(s) fictício(s) gerado(s).`)
  }

  async function copyPayload() {
    try {
      await navigator.clipboard.writeText(report)
      setNotice('Relatório JSON copiado para a área de transferência.')
    } catch {
      setNotice('Não foi possível copiar o JSON.')
    }
  }

  async function sendLeads() {
    if (!leads.length || sending) return
    setSending(true)
    setResults({})
    setNotice(`Enviando ${leads.length} lead(s)...`)
    let approved = 0
    let firstDuplicateId: string | undefined

    try {
      for (const [index, item] of leads.entries()) {
        const started = performance.now()
        let result: Result
        try {
          const response = await submitLead(item.payload, item.idempotencyKey)
          const id = response.id
          let ok = (response.status === 201 || response.status === 200) && !!id

          if (item.scenario === 'mixed') {
            const probe = await submitLead(
              invalidProbeFor(item.payload, index),
              crypto.randomUUID(),
            )
            ok = ok && probe.status === 400
          }

          if (item.scenario === 'duplicate') {
            if (firstDuplicateId === undefined) firstDuplicateId = id
            else ok = ok && response.status === 200 && id === firstDuplicateId
          }

          if (item.scenario === 'mixed' && index % 7 === 6) {
            const duplicate = await submitLead(item.payload, item.idempotencyKey)
            ok = ok && duplicate.status === 200 && duplicate.id === id
          }

          const description = response.error ?? id ?? 'Resposta sem detalhes'
          result = { http: response.status, ok, ms: Math.round(performance.now() - started), detail: description }
        } catch (error) {
          result = {
            http: null,
            ok: false,
            ms: Math.round(performance.now() - started),
            detail: error instanceof Error ? error.message : 'Erro de rede',
          }
        }
        if (result.ok) approved++
        setResults((previous) => ({ ...previous, [index]: result }))
      }
      setNotice(`${approved}/${leads.length} cenários conformes.`)
    } finally {
      setSending(false)
    }
  }

  async function clearLabLeads() {
    if (clearing) return
    const confirmed = window.confirm(
      'Isso excluirá todos os leads gerados pelo LAB. Usuários e outras tabelas não serão alterados. Continuar?',
    )
    if (!confirmed) return

    setClearing(true)
    try {
      const deleted = await clearLabLeadsRequest()
      setNotice(`${deleted} lead(s) removido(s) do banco.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Não foi possível limpar os leads do LAB.')
    } finally {
      setClearing(false)
    }
  }

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
      <div className="mb-7">
        <p className="text-sm text-indigo-500">ADMIN / LAB</p>
        <h1 className="mt-1 text-2xl font-semibold">Laboratório de leads</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Gere a quantidade final de leads desejada enquanto o LAB testa entradas válidas, inválidas e repetidas em segundo plano.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,440px)_1fr]">
        <form onSubmit={generate} className="rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
          <div className="mb-5 flex items-center justify-between">
            <h2 className="font-medium">Configuração</h2>
            <span className="rounded-full bg-indigo-500/10 px-2.5 py-1 text-xs text-indigo-600 dark:text-indigo-300">MODO TESTE</span>
          </div>

          <label className="flex flex-col gap-3 text-sm font-medium">
            Quantidade
            <span className="flex items-center justify-between">
              <span className="text-xs font-normal text-slate-500">De 1 a 100 leads</span>
              <output className="rounded-md bg-indigo-500/10 px-2 py-1 text-sm font-semibold text-indigo-600 dark:text-indigo-300">{quantity}</output>
            </span>
            <input aria-label="Quantidade de leads" type="range" min="1" max="100" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} className="accent-indigo-600" />
          </label>

          <label className="mt-6 flex flex-col gap-2 text-sm font-medium">
            Cenário
            <select value={scenario} onChange={(event) => setScenario(event.target.value as Scenario)} className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm outline-none focus:border-indigo-500 dark:border-white/10 dark:bg-[#111827]">
              {selectableScenarios.map((id) => {
                const item = scenarios.find((scenarioItem) => scenarioItem.id === id)!
                return <option key={item.id} value={item.id}>{item.id === 'mixed' ? 'Operação completa (todos os cenários)' : item.label}</option>
              })}
            </select>
          </label>
          <p className="mt-2 min-h-10 text-xs leading-relaxed text-slate-500">{selected.description}</p>

          <button disabled={sending || catalog.associations.length === 0} className="mt-5 min-h-11 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500 disabled:opacity-50" type="submit">
            Gerar leads fictícios
          </button>
          <button type="button" disabled={!leads.length || sending} onClick={() => void sendLeads()}
            className="mt-3 min-h-11 w-full rounded-lg border border-emerald-600 px-4 py-2 text-sm font-semibold text-emerald-600 hover:bg-emerald-600/10 disabled:opacity-40">
            {sending ? 'Enviando...' : `Enviar ${leads.length} lead(s) ao backend`}
          </button>
          <button type="button" disabled={sending || clearing} onClick={() => void clearLabLeads()}
            className="mt-3 min-h-11 w-full rounded-lg border border-rose-600 px-4 py-2 text-sm font-semibold text-rose-600 hover:bg-rose-600/10 disabled:opacity-40">
            {clearing ? 'Limpando banco...' : 'Limpar leads do banco'}
          </button>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            Produtos e funis reais do banco ({catalog.products.length} produtos, {catalog.funnels.length} funis, {catalog.associations.length} combinações ativas). Origem, campanha e afiliado são aleatórios.
            {catalogError && <span className="block text-rose-600">{catalogError}</span>}
          </p>
        </form>

        <div className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 dark:border-white/10 dark:bg-white/[.03]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-medium">Prévia dos payloads</h2>
              <p className="mt-1 text-xs text-slate-500">Cada objeto do JSON representa um POST /api/leads independente.</p>
            </div>
            <button type="button" disabled={!leads.length} onClick={() => void copyPayload()} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium disabled:opacity-40 dark:border-white/10">Copiar JSON</button>
          </div>

          {notice && <p role="status" className="mb-3 text-sm text-indigo-500">{notice}</p>}
          {Object.keys(results).length > 0 && (
            <div className="mb-4 flex flex-wrap gap-4 rounded-lg bg-slate-100 px-4 py-3 text-sm dark:bg-white/5">
              <span className="text-emerald-600">✓ Conformes: {Object.values(results).filter((result) => result.ok).length}</span>
              <span className="text-red-600">✕ Falhas: {Object.values(results).filter((result) => !result.ok).length}</span>
              <span className="text-slate-500">Processados: {Object.keys(results).length}/{leads.length}</span>
            </div>
          )}
          {leads.length === 0 ? (
            <div className="grid min-h-64 place-items-center rounded-lg border border-dashed border-slate-300 px-6 text-center text-sm text-slate-500 dark:border-white/10">
              Configure a quantidade e um cenário para gerar os primeiros leads.
            </div>
          ) : (
            <>
              <div className="mb-4 overflow-x-auto rounded-lg border border-slate-200 dark:border-white/10">
                <table className="w-full min-w-[900px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-white/10">
                    <tr>{['Nome', 'E-mail', 'Produto', 'Origem', 'Cenário', 'HTTP', 'Esperado', 'Resultado'].map((label) => <th key={label} className="px-3 py-2 font-medium">{label}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                    {leads.map(({ payload: lead, scenario: itemScenario }, index) => (
                      <tr key={index}>
                        <td className="align-middle px-3 py-3 font-medium">{lead.name ?? '—'}</td>
                        <td className="align-middle px-3 py-3 text-slate-500">{lead.email}</td>
                        <td className="align-middle px-3 py-3">{lead.product}</td>
                        <td className="align-middle px-3 py-3">{lead.source}</td>
                        <td className="align-middle px-3 py-3 text-xs text-slate-500">{scenarios.find((s) => s.id === itemScenario)?.label}</td>
                        <td className="align-middle px-3 py-3 font-mono text-xs">{results[index]?.http ?? '—'}</td>
                        <td className="align-middle px-3 py-3 text-xs text-slate-500">
                          <span className="font-mono">{expectedForScenario(itemScenario, index).http}</span>
                          <p className="mt-1 max-w-48 break-words">{expectedForScenario(itemScenario, index).detail}</p>
                        </td>
                        <td className="align-middle px-3 py-3 text-xs">
                          {results[index] ? (
                            <div className={resultPresentation(itemScenario, index, results[index].ok).className}>
                              <span className="font-semibold">{resultPresentation(itemScenario, index, results[index].ok).label}</span>
                              <span className="ml-2 opacity-70">{results[index].ms} ms</span>
                              <p className="mt-1 max-w-64 break-words opacity-80">{results[index].detail}</p>
                            </div>
                          ) : <span className="text-slate-400">{sending ? 'Aguardando...' : 'Não enviado'}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <pre className="max-h-80 overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-relaxed text-slate-300">{payload}</pre>
            </>
          )}
        </div>
      </div>
    </section>
  )
}
