import { useEffect, useState } from 'react'

type BackendStatus = 'checking' | 'online' | 'offline'

function App() {
  const [darkMode, setDarkMode] = useState(true)
  const [backendStatus, setBackendStatus] = useState<BackendStatus>('checking')
  const [backendMessage, setBackendMessage] = useState('Verificando conexão...')

  useEffect(() => {
    let active = true

    async function checkBackend() {
      try {
        const response = await fetch('/api/ping')
        if (!response.ok) throw new Error('Backend indisponível')
        const payload: { status: string; message: string } = await response.json()
        if (active) {
          setBackendStatus(payload.status === 'ok' ? 'online' : 'offline')
          setBackendMessage(payload.message)
        }
      } catch {
        if (active) {
          setBackendStatus('offline')
          setBackendMessage('Não foi possível conectar ao backend')
        }
      }
    }

    void checkBackend()
    const interval = window.setInterval(checkBackend, 5000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  function toggleTheme() {
    const nextDarkMode = !darkMode
    setDarkMode(nextDarkMode)
    document.documentElement.classList.toggle('dark', nextDarkMode)
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-6 text-slate-900 transition-colors dark:bg-[#090d16] dark:text-slate-100 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-center justify-between border-b border-slate-200 pb-5 dark:border-white/10">
          <a href="/" className="flex items-center gap-3 font-semibold tracking-tight">
            <span className="grid size-9 place-items-center rounded-xl bg-indigo-500 text-white shadow-lg shadow-indigo-500/20">G</span>
            <span>Group Elevate <span className="font-normal text-slate-500 dark:text-slate-400">/ starter</span></span>
          </a>
          <button
            type="button"
            onClick={toggleTheme}
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5"
            aria-label={`Ativar modo ${darkMode ? 'claro' : 'escuro'}`}
          >
            {darkMode ? '☼  Modo claro' : '☾  Modo escuro'}
          </button>
        </header>

        <section className="grid gap-12 py-16 sm:py-24 md:grid-cols-[1.2fr_0.8fr] md:items-center">
          <div>
            <div className={`mb-6 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${backendStatus === 'online' ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-700 dark:text-emerald-300' : backendStatus === 'offline' ? 'border-rose-400/20 bg-rose-400/10 text-rose-700 dark:text-rose-300' : 'border-amber-400/20 bg-amber-400/10 text-amber-700 dark:text-amber-300'}`}>
              <span className={`size-1.5 rounded-full ${backendStatus === 'online' ? 'bg-emerald-500' : backendStatus === 'offline' ? 'bg-rose-500' : 'bg-amber-500'}`} />
              {backendStatus === 'checking' ? 'Verificando backend' : backendStatus === 'online' ? 'Backend conectado' : 'Backend indisponível'}
            </div>
            <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
              Uma base simples para o seu próximo projeto.
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-slate-600 dark:text-slate-400 sm:text-lg">
              Frontend configurado com React, TypeScript, Vite e Tailwind CSS. Edite esta tela e comece a construir.
            </p>
            <a href="#stack" className="mt-8 inline-flex items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/20 transition hover:bg-indigo-400">
              Explorar a stack <span aria-hidden="true">→</span>
            </a>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-200/40 dark:border-white/10 dark:bg-white/[0.03] dark:shadow-black/20 sm:p-8">
            <div className="flex items-center justify-between border-b border-slate-200 pb-5 dark:border-white/10">
              <div>
                <p className="text-sm font-medium">Healthcheck do backend</p>
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">GET /ping · atualiza a cada 5s</p>
              </div>
              <span className={`rounded-md px-2.5 py-1 text-xs font-medium ${backendStatus === 'online' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' : backendStatus === 'offline' ? 'bg-rose-500/10 text-rose-700 dark:text-rose-300' : 'bg-amber-500/10 text-amber-700 dark:text-amber-300'}`}>
                {backendStatus === 'checking' ? 'Verificando' : backendStatus === 'online' ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className="space-y-4 pt-5">
              {[
                ['Frontend', 'React + TypeScript'],
                ['Bundler', 'Vite'],
                ['Estilos', 'Tailwind CSS v4'],
                ['Resposta da API', backendMessage],
              ].map(([label, value]) => (
                <div key={label} className="flex items-center justify-between gap-4 text-sm">
                  <span className="text-slate-500 dark:text-slate-400">{label}</span>
                  <span className="text-right font-medium">{value}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="stack" className="border-t border-slate-200 pt-8 dark:border-white/10">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Ferramentas do projeto</p>
          <div className="mt-5 flex flex-wrap gap-2">
            {['React 19', 'TypeScript', 'Vite', 'Tailwind CSS v4'].map((item) => (
              <span key={item} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 dark:border-white/10 dark:bg-white/[0.03] dark:text-slate-300">{item}</span>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}

export default App
