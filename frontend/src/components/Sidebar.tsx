import { NavLink } from 'react-router-dom'
import { LayoutGrid, TrendingUp, Users, Briefcase, ChevronLeft, ChevronRight, BookOpen, ClipboardList, BarChart2 } from 'lucide-react'
import clsx from 'clsx'

const NAV = [
  { to: '/heatmap',        icon: LayoutGrid,   label: '博主热力图' },
  { to: '/signal',         icon: TrendingUp,   label: '今日信号'   },
  { to: '/bloggers',       icon: Users,        label: '博主管理'   },
  { to: '/portfolio',      icon: Briefcase,    label: '我的持仓'   },
  { to: '/learn',          icon: BookOpen,     label: '新手教学'   },
  { to: '/review',         icon: ClipboardList,label: '复盘整理'   },
  { to: '/signal-reviews', icon: BarChart2,    label: '信号复盘'   },
]

interface Props { collapsed: boolean; onToggle: () => void }

export default function Sidebar({ collapsed, onToggle }: Props) {
  return (
    <aside className={clsx(
      'hidden md:flex flex-col border-r border-bg-border bg-[#0a0a0a] transition-all duration-300 shrink-0',
      collapsed ? 'w-16' : 'w-56'
    )}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-bg-border">
        <div className="relative w-8 h-8 flex items-center justify-center shrink-0">
          <div className="absolute inset-0 rounded-lg" style={{background: 'radial-gradient(circle, rgba(0,212,170,0.15) 0%, transparent 70%)'}} />
          <div className="relative w-7 h-7 rounded-lg bg-white flex items-center justify-center">
            <span className="text-black font-bold text-sm">F</span>
          </div>
        </div>
        {!collapsed && (
          <span className="font-semibold text-white text-base tracking-tight">
            Fund<span className="serif-accent">Radar</span>
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 py-4 flex flex-col gap-1 px-2">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all',
            isActive
              ? 'bg-white/[0.04] text-white border border-white/[0.06]'
              : 'text-muted hover:text-white hover:bg-white/[0.02] border border-transparent'
          )}>
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="p-3 border-t border-bg-border">
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center p-2 rounded-lg text-muted hover:text-white hover:bg-white/[0.04] transition"
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
  )
}
