import { NavLink, Outlet } from 'react-router-dom'
import { useSettingsStore } from '../store/settings'

const navItems = [
  { to: '/', label: 'Upload' },
  { to: '/graph', label: 'Graph Explorer' },
  { to: '/query', label: 'Query' },
  { to: '/evaluation', label: 'Evaluation' },
  { to: '/settings', label: 'Settings' },
]

export function Layout() {
  const jobId = useSettingsStore((s) => s.jobId)

  return (
    <div className="h-full">
      <div className="mx-auto flex h-full max-w-[1400px] gap-4 p-4">
        <aside className="panel w-[260px] shrink-0 rounded-xl p-3">
          <div className="mb-3">
            <div className="text-sm font-semibold">Graph-Augmented RAG</div>
            <div className="mono text-xs text-[rgba(255,255,255,0.62)]">Multi-Document Reasoning</div>
          </div>

          <div className="mb-3 rounded-lg border border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.03)] p-2">
            <div className="mono text-[10px] text-[rgba(255,255,255,0.6)]">ACTIVE JOB</div>
            <div className="mono truncate text-xs">{jobId || '—'}</div>
          </div>

          <nav className="flex flex-col gap-1">
            {navItems.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                className={({ isActive }) =>
                  [
                    'rounded-lg px-3 py-2 text-sm transition',
                    isActive
                      ? 'bg-[rgba(52,214,255,0.10)] text-white border border-[rgba(52,214,255,0.25)]'
                      : 'text-[rgba(255,255,255,0.75)] hover:bg-[rgba(255,255,255,0.04)]',
                  ].join(' ')
                }
              >
                {it.label}
              </NavLink>
            ))}
          </nav>

          <div className="mt-4 text-xs text-[rgba(255,255,255,0.55)]">
            Tip: set your OpenAI key in Settings. It’s sent only via the <span className="mono">X-OpenAI-Key</span>{' '}
            header.
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

