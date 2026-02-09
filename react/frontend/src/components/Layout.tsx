import { ReactNode, useState, memo } from 'react'
import { Menu, X } from 'lucide-react'

interface NavItem {
  id: string
  label: string
  icon: React.ComponentType<{ size?: number | string }>
  description: string
}

interface LayoutProps {
  children: ReactNode
  currentPage: string
  onNavigate: (page: string) => void
  navItems: NavItem[]
  appName: string
}

const NavButton = memo(function NavButton({
  item,
  isActive,
  onClick,
  showLabel,
}: {
  item: NavItem
  isActive: boolean
  onClick: () => void
  showLabel: boolean
}) {
  const Icon = item.icon
  return (
    <button
      onClick={onClick}
      aria-label={item.description}
      aria-current={isActive ? 'page' : undefined}
      className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl transition-all
        focus-visible:ring-2 focus-visible:ring-accent-blue focus-visible:outline-none
        ${isActive ? 'bg-accent-blue/10 text-accent-blue' : 'text-slate-400 hover:bg-navy-700/50'}`}
    >
      <Icon size={18} />
      {showLabel && <span className="text-sm">{item.label}</span>}
    </button>
  )
})

export function Layout({ children, currentPage, onNavigate, navItems, appName }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="min-h-screen bg-navy-900 flex">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:p-4 focus:bg-accent-blue focus:text-white focus:z-50"
      >
        Skip to main content
      </a>

      <aside
        className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-navy-800/50 border-r border-navy-700/50 flex flex-col transition-all`}
      >
        <div className="p-4 border-b border-navy-700/50 flex items-center justify-between">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-accent-blue rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">SC</span>
              </div>
              <h1 className="font-bold text-slate-200">{appName}</h1>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg hover:bg-navy-700 focus-visible:ring-2 focus-visible:ring-accent-blue"
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            aria-expanded={sidebarOpen}
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1" role="navigation" aria-label="Main">
          {navItems.map((item) => (
            <NavButton
              key={item.id}
              item={item}
              isActive={currentPage === item.id}
              onClick={() => onNavigate(item.id)}
              showLabel={sidebarOpen}
            />
          ))}
        </nav>

        <div className="p-4 border-t border-navy-700/50">
          {sidebarOpen && (
            <p className="text-xs text-slate-500">Powered by Snowflake Cortex</p>
          )}
        </div>
      </aside>

      <main id="main-content" className="flex-1 overflow-auto" role="main">
        {children}
      </main>
    </div>
  )
}
