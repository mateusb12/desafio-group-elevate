import { useState } from 'react'
import { login, logout } from './features/auth/auth.service'
import type { AuthenticatedUser } from './features/auth/auth.types'
import { LoginPage } from './features/auth/LoginPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { LeadsPage } from './features/leads/LeadsPage'
import { DispatcherPage } from './features/dispatcher/DispatcherPage'

type Section = 'dashboard' | 'leads' | 'dispatcher'

function App() {
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [section, setSection] = useState<Section>('dashboard')
  const [darkMode, setDarkMode] = useState(true)

  async function handleLogin(email: string, password: string) {
    const session = await login(email, password)
    setUser(session)
    setSection(session.role === 'ADMIN' ? 'dashboard' : 'leads')
  }

  async function handleLogout() {
    await logout()
    setUser(null)
    setSection('dashboard')
  }

  function toggleTheme() {
    const nextDarkMode = !darkMode
    setDarkMode(nextDarkMode)
    document.documentElement.classList.toggle('dark', nextDarkMode)
  }

  if (!user) return <LoginPage onLogin={handleLogin} />

  const navigation: { id: Section; label: string }[] = user.role === 'ADMIN'
    ? [
        { id: 'dashboard', label: 'Visão geral' },
        { id: 'leads', label: 'Leads' },
        { id: 'dispatcher', label: 'Distribuição' },
      ]
    : [{ id: 'leads', label: 'Meus leads' }]

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-[#090d16] dark:text-slate-100">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-white/10 dark:bg-[#090d16]/90">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-8">
          <a href="/" className="flex shrink-0 items-center gap-3 font-semibold tracking-tight">
            <span className="grid size-9 place-items-center rounded-xl bg-indigo-500 text-white">G</span>
            <span className="hidden sm:inline">Group Elevate <span className="font-normal text-slate-500 dark:text-slate-400">/ dispatcher</span></span>
          </a>
          <nav className="flex items-center gap-1" aria-label="Navegação principal">
            {navigation.map((item) => (
              <button key={item.id} type="button" onClick={() => setSection(item.id)} className={`rounded-lg px-3 py-2 text-sm transition ${section === item.id ? 'bg-indigo-500/10 font-medium text-indigo-700 dark:text-indigo-300' : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5'}`}>
                {item.label}
              </button>
            ))}
          </nav>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            <div className="hidden text-right sm:block">
              <p className="text-sm font-medium">{user.name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">{user.role === 'ADMIN' ? 'Administrador' : user.callCenterName}</p>
            </div>
            <button type="button" onClick={toggleTheme} className="rounded-lg border border-slate-200 px-2.5 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5" aria-label={`Ativar modo ${darkMode ? 'claro' : 'escuro'}`}>
              {darkMode ? '☼' : '☾'}
            </button>
            <button type="button" onClick={() => void handleLogout()} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5">Sair</button>
          </div>
        </div>
      </header>
      {section === 'dashboard' && user.role === 'ADMIN' && <DashboardPage onViewLeads={() => setSection('leads')} />}
      {section === 'leads' && <LeadsPage user={user} />}
      {section === 'dispatcher' && user.role === 'ADMIN' && <DispatcherPage />}
    </main>
  )
}

export default App
