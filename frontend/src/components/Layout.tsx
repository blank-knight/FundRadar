import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import Sidebar from './Sidebar'
import { LayoutGrid, TrendingUp, Users, Briefcase, BookOpen, ClipboardList, BarChart2 } from 'lucide-react'
import clsx from 'clsx'

const MOBILE_NAV = [
  { to: '/heatmap',        icon: LayoutGrid,   label: '热力图' },
  { to: '/signal',         icon: TrendingUp,   label: '信号'   },
  { to: '/bloggers',       icon: Users,        label: '博主'   },
  { to: '/portfolio',      icon: Briefcase,    label: '持仓'   },
  { to: '/learn',          icon: BookOpen,     label: '教学'   },
  { to: '/review',         icon: ClipboardList,label: '复盘'   },
  { to: '/signal-reviews', icon: BarChart2,    label: '回顾'   },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)
  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0e1a]">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(c => !c)} />
      <main className="flex-1 overflow-y-auto pb-14 md:pb-0">
        <Outlet />
      </main>
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#0d1220] border-t border-[#1f2937] flex items-center justify-around px-1">
        {MOBILE_NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => clsx(
            'flex flex-col items-center gap-0.5 py-2 px-1 min-w-0 flex-1',
            isActive ? 'text-[#00d4aa]' : 'text-gray-500'
          )}>
            <Icon size={20} className="shrink-0" />
            <span className="text-[10px] truncate">{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
