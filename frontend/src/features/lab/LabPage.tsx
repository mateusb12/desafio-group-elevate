import { useMemo, useState, type FormEvent } from 'react'
import { fakerPT_BR as faker } from '@faker-js/faker'

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

type Utm = { source: string; medium: string; campaign: string; content: string }
type LeadPayload = {
  name?: string | number
  email: string
  phone: string
  product: string
  funnel: string
  source: string
  campaign: string
  affiliate_id: string
  utm: Utm | string
}
type PreviewLead = { payload: LeadPayload; scenario: Scenario }

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
  { id: 'mixed', label: 'Cenários mistos', description: 'Mistura leads válidos e diferentes erros na mesma amostra.' },
]

const products = ['nutralean', 'curso-vendas', 'marketing-digital']
const funnels = ['vsl-01', 'webinar-02', 'checkout-03']
const sources = ['facebook', 'instagram', 'google', 'youtube']
const issueScenarios: Scenario[] = [
  'valid', 'invalid-email', 'invalid-phone', 'missing-name',
  'unknown-product', 'unknown-funnel', 'invalid-utm', 'invalid-types',
]

function randomLead(): LeadPayload {
  const name = faker.person.fullName()
  const [firstName, ...lastName] = name.split(' ')
  const source = faker.helpers.arrayElement(sources)
  const campaign = `campaign-${faker.string.numeric(3)}`
  const ddd = faker.helpers.arrayElement(['11', '21', '31', '41', '85'])

  return {
    name,
    email: faker.internet.email({ firstName, lastName: lastName.join(' ') }).toLowerCase(),
    phone: `+55${ddd}9${faker.string.numeric(8)}`,
    product: faker.helpers.arrayElement(products),
    funnel: faker.helpers.arrayElement(funnels),
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

function leadForScenario(scenario: Scenario): PreviewLead {
  const lead = randomLead()
  switch (scenario) {
    case 'invalid-email': lead.email = 'email-sem-arroba'; break
    case 'invalid-phone': lead.phone = '123'; break
    case 'missing-name': delete lead.name; break
    case 'unknown-product': lead.product = 'produto-inexistente'; break
    case 'unknown-funnel': lead.funnel = 'funil-inexistente'; break
    case 'invalid-utm': lead.utm = 'utm-invalida'; break
    case 'invalid-types': lead.name = 12345; break
  }
  return { payload: lead, scenario }
}

export function LabPage() {
  const [quantity, setQuantity] = useState(5)
  const [scenario, setScenario] = useState<Scenario>('valid')
  const [leads, setLeads] = useState<PreviewLead[]>([])
  const [notice, setNotice] = useState('')

  const payload = useMemo(() => JSON.stringify(leads.map(({ payload: lead }) => lead), null, 2), [leads])
  const selected = scenarios.find((item) => item.id === scenario)!

  function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const amount = Math.min(100, Math.max(1, quantity))
    const repeated = scenario === 'duplicate' ? randomLead() : null
    const generated = Array.from({ length: amount }, (_, index) => repeated
      ? { payload: repeated, scenario: 'duplicate' as const }
      : leadForScenario(scenario === 'mixed' ? issueScenarios[index % issueScenarios.length] : scenario))
    setLeads(generated)
    setNotice(`${amount} lead(s) fictício(s) gerado(s).`)
  }

  async function copyPayload() {
    try {
      await navigator.clipboard.writeText(payload)
      setNotice('JSON copiado para a área de transferência.')
    } catch {
      setNotice('Não foi possível copiar o JSON.')
    }
  }

  return (
    <section className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
      <div className="mb-7">
        <p className="text-sm text-indigo-500">ADMIN / LAB</p>
        <h1 className="mt-1 text-2xl font-semibold">Laboratório de leads</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Gere entradas válidas, inválidas ou repetidas para experimentar a API conforme ela evolui.
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
              {scenarios.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
            </select>
          </label>
          <p className="mt-2 min-h-10 text-xs leading-relaxed text-slate-500">{selected.description}</p>

          <button className="mt-5 min-h-11 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500" type="submit">
            Gerar leads fictícios
          </button>
          <p className="mt-3 text-xs leading-relaxed text-slate-500">
            Produto, funil, origem, campanha e afiliado são aleatórios. Os dados ficam apenas no navegador.
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
          {leads.length === 0 ? (
            <div className="grid min-h-64 place-items-center rounded-lg border border-dashed border-slate-300 px-6 text-center text-sm text-slate-500 dark:border-white/10">
              Configure a quantidade e um cenário para gerar os primeiros leads.
            </div>
          ) : (
            <>
              <div className="mb-4 overflow-x-auto rounded-lg border border-slate-200 dark:border-white/10">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-white/10">
                    <tr>{['Nome', 'E-mail', 'Produto', 'Origem', 'Cenário'].map((label) => <th key={label} className="px-3 py-2 font-medium">{label}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-white/5">
                    {leads.map(({ payload: lead, scenario: itemScenario }, index) => (
                      <tr key={index}>
                        <td className="px-3 py-3 font-medium">{lead.name ?? '—'}</td>
                        <td className="px-3 py-3 text-slate-500">{lead.email}</td>
                        <td className="px-3 py-3">{lead.product}</td>
                        <td className="px-3 py-3">{lead.source}</td>
                        <td className="px-3 py-3 text-xs text-slate-500">{scenarios.find((s) => s.id === itemScenario)?.label}</td>
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
