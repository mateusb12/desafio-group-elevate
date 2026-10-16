import { useEffect, useState } from 'react'
import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router'
import { getCurrentUser, login, logout } from './features/auth/auth.service'
import type { AuthenticatedUser } from './features/auth/auth.types'
import { LoginPage } from './features/auth/LoginPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { LeadsPage } from './features/leads/LeadsPage'
import { DispatcherPage } from './features/dispatcher/DispatcherPage'

type Section = 'dashboard' | 'leads' | 'dispatcher'

function App() {
  const [user, setUser] = useState<AuthenticatedUser | null>(null)
  const [sessionChecked, setSessionChecked] = useState(false)
  const [darkMode, setDarkMode] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    void getCurrentUser()
      .catch(() => null)
      .then(setUser)
      .finally(() => setSessionChecked(true))
  }, [])

  async function handleLogin(email: string, password: string) {
    const authenticatedUser = await login(email, password)
    setUser(authenticatedUser)
    navigate(authenticatedUser.role === 'ADMIN' ? '/dashboard' : '/leads', { replace: true })
  }

  async function handleLogout() {
    await logout()
    setUser(null)
    navigate('/login', { replace: true })
  }

  function toggleTheme() {
    const nextDarkMode = !darkMode
    setDarkMode(nextDarkMode)
    document.documentElement.classList.toggle('dark', nextDarkMode)
  }

  const defaultPath = user?.role === 'ADMIN' ? '/dashboard' : '/leads'

  if (!sessionChecked) return null

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={defaultPath} replace /> : <LoginPage onLogin={handleLogin} />} />
      <Route path="/" element={user ? <AuthenticatedLayout user={user} darkMode={darkMode} onToggleTheme={toggleTheme} onLogout={handleLogout} /> : <Navigate to="/login" replace />}>
        <Route index element={<Navigate to={defaultPath} replace />} />
        <Route path="dashboard" element={user?.role === 'ADMIN' ? <DashboardPage onViewLeads={() => navigate('/leads')} /> : <Navigate to="/leads" replace />} />
        <Route path="leads" element={user ? <LeadsPage user={user} /> : <Navigate to="/login" replace />} />
        <Route path="dispatcher" element={user?.role === 'ADMIN' ? <DispatcherPage /> : <Navigate to="/leads" replace />} />
      </Route>
      <Route path="*" element={<Navigate to={user ? defaultPath : '/login'} replace />} />
    </Routes>
  )
}

function AuthenticatedLayout({
  user,
  darkMode,
  onToggleTheme,
  onLogout,
}: {
  user: AuthenticatedUser
  darkMode: boolean
  onToggleTheme: () => void
  onLogout: () => void
}) {
  return (
    <main className="flex min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-[#090d16] dark:text-slate-100">
      <Sidebar user={user} darkMode={darkMode} onToggleTheme={onToggleTheme} onLogout={onLogout} />
      <div className="min-w-0 flex-1 overflow-x-hidden"><Outlet /></div>
    </main>
  )
}

function Sidebar({
  user,
  darkMode,
  onToggleTheme,
  onLogout,
}: {
  user: AuthenticatedUser
  darkMode: boolean
  onToggleTheme: () => void
  onLogout: () => void
}) {
  const navigation: { id: Section; label: string; to: string }[] = user.role === 'ADMIN'
    ? [
        { id: 'dashboard', label: 'Visão geral', to: '/dashboard' },
        { id: 'leads', label: 'Leads', to: '/leads' },
        { id: 'dispatcher', label: 'Distribuição', to: '/dispatcher' },
      ]
    : [{ id: 'leads', label: 'Meus leads', to: '/leads' }]

  return (
      <aside className="flex w-16 shrink-0 flex-col border-r border-slate-200 bg-white px-2 py-4 dark:border-white/10 dark:bg-[#0d1320] sm:w-60 sm:px-4">
        <NavLink to="/" className="mb-8 flex items-center justify-center gap-3 font-semibold tracking-tight sm:justify-start">
          <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-indigo-500 text-white">G</span>
          <span className="hidden sm:inline">Group Elevate</span>
        </NavLink>
        <p className="mb-2 hidden px-3 text-[10px] font-semibold uppercase tracking-widest text-slate-400 sm:block">Workspace</p>
        <nav className="flex flex-col gap-1" aria-label="Navegação principal">
          {navigation.map((item) => {
            const icon = item.id === 'dashboard' ? '▦' : item.id === 'leads' ? '≡' : '⇄'
            return (
              <NavLink key={item.id} to={item.to} aria-label={item.label} title={item.label} className={({ isActive }) => `flex items-center justify-center gap-3 rounded-lg px-2 py-2.5 text-sm transition sm:justify-start sm:px-3 ${isActive ? 'bg-indigo-500/10 font-medium text-indigo-700 dark:text-indigo-300' : 'text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5'}`}>
                <span aria-hidden="true" className="grid size-5 shrink-0 place-items-center text-base">{icon}</span>
                <span className="hidden sm:inline">{item.label}</span>
              </NavLink>
            )
          })}
        </nav>
        <div className="mt-auto border-t border-slate-200 pt-4 dark:border-white/10">
          <div className="mb-3 flex items-center justify-center gap-3 px-2 sm:justify-start">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-200 text-xs font-semibold text-slate-700 dark:bg-white/10 dark:text-slate-200">{user.name.split(' ').map((part) => part[0]).slice(0, 2).join('')}</span>
            <div className="hidden min-w-0 sm:block">
              <p className="truncate text-sm font-medium">{user.name}</p>
              <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user.role === 'ADMIN' ? 'Administrador' : user.callCenterName}</p>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <button type="button" onClick={onToggleTheme} className="flex items-center justify-center gap-3 rounded-lg px-2 py-2 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5 sm:justify-start sm:px-3" aria-label={`Ativar modo ${darkMode ? 'claro' : 'escuro'}`} title={`Modo ${darkMode ? 'claro' : 'escuro'}`}>
              <span aria-hidden="true" className="grid size-5 place-items-center">{darkMode ? '☼' : '☾'}</span>
              <span className="hidden sm:inline">Aparência</span>
            </button>
            <button type="button" onClick={() => void onLogout()} className="flex items-center justify-center gap-3 rounded-lg px-2 py-2 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/5 sm:justify-start sm:px-3" title="Sair">
              <span aria-hidden="true" className="grid size-5 place-items-center">↪</span>
              <span className="hidden sm:inline">Sair</span>
            </button>
          </div>
        </div>
      </aside>
  )
}

export default App
