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
      'hidden md:flex flex-col border-r border-[#1f2937] bg-[#0d1220] transition-all duration-300 shrink-0',
      collapsed ? 'w-16' : 'w-56'
    )}>
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 py-5 border-b border-[#1f2937]">
        <div className="w-8 h-8 rounded-lg bg-[#00d4aa] flex items-center justify-center shrink-0">
          <span className="text-[#0a0e1a] font-bold text-sm">F</span>
        </div>
        {!collapsed && (
          <span className="font-semibold text-white text-base tracking-tight">FundRadar</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} className={({ isActive }) => clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all',
            isActive
              ? 'bg-[#00d4aa15] text-[#00d4aa] font-medium'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          )}>
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Toggle */}
      <button
        onClick={onToggle}
        className="flex items-center justify-center py-4 border-t border-[#1f2937] text-gray-500 hover:text-white transition"
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  )
}
