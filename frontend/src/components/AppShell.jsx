import { AnimatePresence, motion } from 'framer-motion'
import {
  Blocks, Bot, ChevronsLeft, FilePlus2, FileStack, FolderKanban, LayoutDashboard,
  Gauge, Library, Moon, PanelRightClose, PanelRightOpen, Search, Settings, ShieldCheck, Sun,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'
import { Badge, Tooltip } from './ui'
import Copilot from './Copilot'
import BrandLogo from './BrandLogo'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/new', label: 'New BRD', icon: FilePlus2, accent: true },
  { to: '/projects', label: 'My Projects', icon: FolderKanban },
  { to: '/knowledge', label: 'Knowledge Sources', icon: Library },
  { to: '/agents', label: 'AI Agents', icon: Bot },
  { to: '/review', label: 'Review Center', icon: ShieldCheck, badgeKey: 'pending' },
  { to: '/documents', label: 'Documents', icon: FileStack },
  { to: '/performance', label: 'Performance', icon: Gauge },
  { to: '/integrations', label: 'Integrations', icon: Blocks },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function AppShell({ children, pending = 0, project, health }) {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  const [collapsed, setCollapsed] = useState(false)
  const [copilot, setCopilot] = useState(true)
  const loc = useLocation()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <div className="min-h-screen bg-bg text-ink flex">
      <aside className={cn('sticky top-0 h-screen shrink-0 border-r border-line bg-surface flex flex-col transition-[width] duration-200',
        collapsed ? 'w-[68px]' : 'w-[248px]')}>
        <div className={cn('flex shrink-0 items-center border-b border-line',
          collapsed ? 'h-16 justify-center px-2' : 'h-[76px] px-3')}>
          <BrandLogo collapsed={collapsed} />
        </div>

        <nav className="flex-1 overflow-y-auto p-2.5 space-y-0.5">
          {NAV.map((item) => {
            const Icon = item.icon
            const link = (
              <NavLink key={item.to} to={item.to} end={item.end}
                className={({ isActive }) => cn(
                  'group relative flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors',
                  isActive ? 'bg-brand-soft text-brand' : 'text-muted hover:text-ink hover:bg-bg',
                  collapsed && 'justify-center px-0',
                )}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="nav-rail"
                      className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-brand" />}
                    <Icon className={cn('h-[18px] w-[18px] shrink-0', item.accent && !isActive && 'text-brand')} />
                    {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
                    {!collapsed && item.badgeKey === 'pending' && pending > 0 && <Badge tone="warning">{pending}</Badge>}
                  </>
                )}
              </NavLink>
            )
            return collapsed ? <Tooltip key={item.to} label={item.label} side="right">{link}</Tooltip> : link
          })}
        </nav>

        <div className="border-t border-line p-2.5 space-y-1">
          <button onClick={() => setDark((d) => !d)}
            className={cn('flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] font-medium text-muted hover:text-ink hover:bg-bg transition-colors',
              collapsed && 'justify-center px-0')}>
            {dark ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
            {!collapsed && <span>{dark ? 'Light mode' : 'Dark mode'}</span>}
          </button>

          <div className={cn('flex items-center gap-2.5 rounded-lg px-2.5 py-2', collapsed && 'justify-center px-0')}>
            <div className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-brand to-brand-deep grid place-items-center">
              <span className="text-[11px] font-bold text-brand-fg">PT</span>
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-medium truncate">Prashant Thakur</div>
                <div className="text-[10.5px] text-muted truncate">Lead Software Architect</div>
              </div>
            )}
          </div>

          <button onClick={() => setCollapsed((c) => !c)}
            className={cn('flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] text-muted hover:text-ink hover:bg-bg transition-colors',
              collapsed && 'justify-center px-0')}>
            <ChevronsLeft className={cn('h-[18px] w-[18px] transition-transform', collapsed && 'rotate-180')} />
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="sticky top-0 z-30 h-[76px] shrink-0 border-b border-line bg-surface/80 backdrop-blur-md flex items-center gap-4 px-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
            <input placeholder="Search projects, requirements, documents…"
              className="w-full rounded-lg bg-bg border border-line pl-9 pr-3 py-2 text-[13px] placeholder:text-muted/70 focus:border-brand focus:ring-4 focus:ring-brand/10 outline-none transition-shadow" />
          </div>
          <div className="flex items-center gap-2">
            {health?.integrations && (
              // Show the model that is ACTUALLY configured. This badge used to read
              // "GEMINI 2.5 PRO" no matter what was running — a label that lies about provenance
              // is worse than no label, and this one sits at the top of every screenshot.
              <Badge tone={health.integrations.llm === 'live' ? 'success' : 'warning'}>
                {health.integrations.llm === 'live'
                  ? `${(health.integrations.model || '').split(':').pop().toUpperCase()} · LIVE`
                  : 'MOCK MODE'}
              </Badge>
            )}
            <Tooltip label={copilot ? 'Hide AI Copilot' : 'Show AI Copilot'}>
              <button onClick={() => setCopilot((c) => !c)}
                className="h-9 w-9 grid place-items-center rounded-lg text-muted hover:text-ink hover:bg-bg transition-colors">
                {copilot ? <PanelRightClose className="h-[18px] w-[18px]" /> : <PanelRightOpen className="h-[18px] w-[18px]" />}
              </button>
            </Tooltip>
          </div>
        </header>

        <div className="flex-1 flex min-w-0">
          <main className="flex-1 min-w-0 overflow-x-hidden">
            <motion.div key={loc.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }} className="p-6 max-w-[1180px] mx-auto">
              {children}
            </motion.div>
          </main>

          <AnimatePresence initial={false}>
            {copilot && (
              <motion.aside initial={{ width: 0, opacity: 0 }} animate={{ width: 372, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }} transition={{ type: 'spring', stiffness: 260, damping: 30 }}
                className="sticky top-[76px] h-[calc(100vh-76px)] shrink-0 border-l border-line bg-surface overflow-hidden hidden xl:block">
                <div className="w-[372px] h-full"><Copilot project={project} /></div>
              </motion.aside>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
