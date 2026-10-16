import { useEffect, useState, type FormEvent } from 'react'
import { checkBackendHealth } from './auth.service'

type LoginPageProps = { onLogin: (email: string, password: string) => Promise<void> }

const demoAccounts = [
  { role: 'Administrador', email: 'admin@elevate.dev' },
  { role: 'Operador', email: 'operador@elevate.dev' },
]

type HealthStatus = 'checking' | 'online' | 'offline'

function BackendHealthIndicator() {
  const [status, setStatus] = useState<HealthStatus>('checking')

  useEffect(() => {
    let active = true
    const ping = async () => {
      const online = await checkBackendHealth()
      if (active) setStatus(online ? 'online' : 'offline')
    }

    void ping()
    const intervalId = window.setInterval(() => void ping(), 10_000)
    return () => {
      active = false
      window.clearInterval(intervalId)
    }
  }, [])

  const labels: Record<HealthStatus, string> = {
    checking: 'Verificando backend…',
    online: 'Backend online',
    offline: 'Backend offline',
  }

  const dotColor = status === 'online' ? 'bg-emerald-400' : status === 'offline' ? 'bg-rose-400' : 'bg-amber-400'

  return (
    <div className="flex min-h-11 items-center gap-2.5 rounded-lg border border-slate-700 bg-slate-950/60 px-3 text-sm text-slate-200" role="status" aria-live="polite">
      <span className={`size-2 rounded-full ${dotColor}`} />
      <span>{labels[status]}</span>
      <span className="ml-auto font-mono text-[11px] text-slate-500">/api/ping</span>
    </div>
  )
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await onLogin(email, password)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível entrar.')
    } finally {
      setSubmitting(false)
    }
  }

  function selectDemoAccount(accountEmail: string) {
    setEmail(accountEmail)
    setPassword('demo123')
    setError('')
  }

  return (
    <main className="flex min-h-screen flex-col bg-slate-950 px-5 py-5 text-slate-100 sm:px-10 sm:py-6">
      <header className="flex min-h-9 items-center justify-between">
        <a className="flex items-center gap-3 text-sm font-semibold tracking-widest text-slate-100" href="/" aria-label="Group Elevate, início">
          <span className="grid size-9 place-items-center rounded-lg border border-blue-500 text-base tracking-normal text-blue-400">G</span>
          <span>GROUP ELEVATE</span>
        </a>
        <span className="border-l border-slate-700 pl-4 text-xs tracking-wider text-slate-400">PAINEL DE LEADS</span>
      </header>

      <div className="grid flex-1 place-items-center py-9 sm:py-12">
        <section className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl shadow-black/30 sm:p-9" aria-labelledby="login-title">
          <BackendHealthIndicator />
          <div className="my-7">
            <p className="mb-2 text-[11px] font-bold tracking-[.14em] text-blue-400">BEM-VINDO DE VOLTA</p>
            <h1 id="login-title" className="text-2xl font-semibold tracking-tight text-white">Acesse sua conta</h1>
            <p className="mt-2 text-sm leading-relaxed text-slate-400">Entre no painel para acompanhar os leads da operação.</p>
          </div>
          <form className="flex flex-col gap-4" onSubmit={submit}>
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-200">
              E-mail
              <input className="h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20" type="email" autoComplete="username" placeholder="voce@empresa.com" required value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className="flex flex-col gap-2 text-sm font-medium text-slate-200">
              Senha
              <input className="h-11 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20" type="password" autoComplete="current-password" placeholder="••••••••" required value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {error && <p role="alert" className="rounded-lg border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-sm leading-relaxed text-rose-200">{error}</p>}
            <button className="mt-1 min-h-11 w-full rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-wait disabled:opacity-60" disabled={submitting} type="submit">{submitting ? 'Entrando…' : 'Entrar'}</button>
          </form>
        </section>
      </div>

      <section className="mx-auto w-full max-w-5xl" aria-labelledby="demo-title">
        <div className="mb-3 flex items-center justify-between gap-5">
          <div>
            <h2 id="demo-title" className="text-sm font-semibold text-slate-200">Perfis de demonstração</h2>
            <p className="mt-1 text-xs text-slate-400">Selecione um perfil para preencher as credenciais.</p>
          </div>
          <span className="rounded-full border border-amber-600/60 px-2.5 py-1 text-[10px] font-bold tracking-widest text-amber-400">DEMO</span>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {demoAccounts.map((account) => (
            <button className="flex min-h-[68px] flex-col justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-left text-slate-100 transition hover:border-blue-500 hover:bg-slate-800" key={account.email} type="button" onClick={() => selectDemoAccount(account.email)}>
              <span className="text-sm font-medium">{account.role}</span>
              <small className="text-xs text-slate-400">{account.email}</small>
            </button>
          ))}
        </div>
        <p className="mt-2 text-right text-[11px] text-slate-500">Senha de demonstração: <code className="font-mono text-slate-400">demo123</code></p>
      </section>
    </main>
  )
}
