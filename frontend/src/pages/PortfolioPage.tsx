import { useState } from 'react'
import { Plus, Trash2, TrendingUp, TrendingDown, Wallet } from 'lucide-react'
import clsx from 'clsx'
import PortfolioAdvice from '../components/PortfolioAdvice'

type Position = {
  id: number
  name: string
  code: string
  type: '股票型' | '混合型' | '债券型' | '指数型'
  shares: number
  costNav: number
  currentNav: number
  amount: number
}

type SortKey = 'profit' | 'amount' | 'name'

const TYPE_COLORS: Record<Position['type'], string> = {
  '股票型': 'text-[#f87171] bg-[#7f1d1d]/40',
  '混合型': 'text-[#fbbf24] bg-[#78350f]/40',
  '债券型': 'text-[#60a5fa] bg-[#1e3a5f]/40',
  '指数型': 'text-[#4ade80] bg-[#14532d]/40',
}

function pct(cost: number, cur: number) {
  return ((cur - cost) / cost * 100)
}

function AddModal({ onAdd, onClose }: { onAdd: (p: Position) => void; onClose: () => void }) {
  const [form, setForm] = useState({ name: '', code: '', type: '指数型' as Position['type'], shares: '', costNav: '' })
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = () => {
    if (!form.name || !form.code || !form.shares || !form.costNav) return
    const shares = parseFloat(form.shares)
    const costNav = parseFloat(form.costNav)
    onAdd({ id: Date.now(), name: form.name, code: form.code, type: form.type,
      shares, costNav, currentNav: costNav, amount: shares * costNav })
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#111827] border border-[#1f2937] rounded-2xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <h2 className="text-white font-bold text-lg mb-4">添加持仓</h2>
        <div className="flex flex-col gap-3">
          {[
            { label: '基金名称', key: 'name', placeholder: '如：易方达蓝筹精选' },
            { label: '基金代码', key: 'code', placeholder: '如：005827' },
            { label: '持有份额', key: 'shares', placeholder: '如：5000' },
            { label: '买入净值', key: 'costNav', placeholder: '如：1.820' },
          ].map(f => (
            <div key={f.key}>
              <label className="text-gray-400 text-xs mb-1 block">{f.label}</label>
              <input value={(form as Record<string, string>)[f.key]}
                onChange={e => set(f.key, e.target.value)}
                placeholder={f.placeholder}
                className="w-full bg-[#0d1220] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#00d4aa]" />
            </div>
          ))}
          <div>
            <label className="text-gray-400 text-xs mb-1 block">基金类型</label>
            <div className="flex gap-2 flex-wrap">
              {(['指数型', '股票型', '混合型', '债券型'] as Position['type'][]).map(t => (
                <button key={t} onClick={() => set('type', t)} className={clsx(
                  'px-3 py-1 rounded-full text-xs border transition',
                  form.type === t ? 'bg-[#00d4aa] text-[#0a0e1a] border-[#00d4aa]' : 'text-gray-400 border-[#1f2937]'
                )}>{t}</button>
              ))}
            </div>
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg border border-[#1f2937] text-gray-400 text-sm hover:text-white transition">取消</button>
          <button onClick={submit} className="flex-1 py-2 rounded-lg bg-[#00d4aa] text-[#0a0e1a] text-sm font-semibold hover:bg-[#00b894] transition">确认添加</button>
        </div>
      </div>
    </div>
  )
}

export default function PortfolioPage() {
  const [positions, setPositions] = useState<Position[]>([])
  const [sort, setSort] = useState<SortKey>('amount')
  const [showAdd, setShowAdd] = useState(false)

  const remove = (id: number) => setPositions(p => p.filter(x => x.id !== id))
  const addPosition = (p: Position) => setPositions(prev => [...prev, p])

  const sorted = [...positions].sort((a, b) => {
    if (sort === 'profit') return pct(b.costNav, b.currentNav) - pct(a.costNav, a.currentNav)
    if (sort === 'amount') return b.amount - a.amount
    return a.name.localeCompare(b.name)
  })

  const totalCost = positions.reduce((s, p) => s + p.shares * p.costNav, 0)
  const totalCurrent = positions.reduce((s, p) => s + p.amount, 0)
  const totalProfit = totalCurrent - totalCost
  const totalPct = totalCost > 0 ? (totalProfit / totalCost * 100) : 0

  return (
    <div className="p-3 md:p-6 h-full flex flex-col overflow-auto">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="text-lg md:text-2xl font-bold text-white mb-1">我的持仓</h1>
          <p className="text-gray-400 text-xs md:text-sm">AI 分析新闻和分析师评级，帮你的持仓做决策</p>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 px-3 md:px-4 py-2 bg-[#00d4aa] text-[#0a0e1a] rounded-lg text-sm font-semibold hover:bg-[#00b894] transition shrink-0">
          <Plus size={16} /><span className="hidden md:inline">添加持仓</span>
        </button>
      </div>

      {/* ── AI 操作建议 + 赛道提醒 ── */}
      <div className="mb-5">
        <PortfolioAdvice />
      </div>

      {/* 总览卡片 */}
      {positions.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-4">
          <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4">
            <p className="text-gray-400 text-xs mb-1 flex items-center gap-1"><Wallet size={12} />总持仓</p>
            <p className="text-white text-lg md:text-xl font-bold">¥{totalCurrent.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</p>
          </div>
          <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4">
            <p className="text-gray-400 text-xs mb-1">总成本</p>
            <p className="text-white text-lg md:text-xl font-bold">¥{totalCost.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</p>
          </div>
          <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4">
            <p className="text-gray-400 text-xs mb-1">总盈亏</p>
            <p className={clsx('text-lg md:text-xl font-bold', totalProfit >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
              {totalProfit >= 0 ? '+' : ''}¥{totalProfit.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}
            </p>
          </div>
          <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4">
            <p className="text-gray-400 text-xs mb-1">总收益率</p>
            <p className={clsx('text-lg md:text-xl font-bold', totalPct >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
              {totalPct >= 0 ? '+' : ''}{totalPct.toFixed(2)}%
            </p>
          </div>
        </div>
      )}

      {/* 排序 */}
      {positions.length > 0 && (
        <div className="flex items-center gap-2 mb-3 text-sm text-gray-400">
          <span>排序：</span>
          {([['amount', '持仓金额'], ['profit', '收益率'], ['name', '名称']] as [SortKey, string][]).map(([k, l]) => (
            <button key={k} onClick={() => setSort(k)} className={clsx(
              'px-2 py-1 rounded transition',
              sort === k ? 'text-[#00d4aa]' : 'hover:text-white'
            )}>{l}</button>
          ))}
        </div>
      )}

      {/* 持仓列表 */}
      <div className="flex flex-col gap-3">
        {positions.length === 0 ? (
          <div className="text-center text-gray-500 py-6 text-sm">
            暂无持仓。在上方添加基金后可查看详细盈亏。
          </div>
        ) : sorted.map(p => {
          const gain = pct(p.costNav, p.currentNav)
          const profit = p.amount - p.shares * p.costNav
          return (
            <div key={p.id} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4 hover:border-[#374151] transition">
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-white font-semibold text-sm">{p.name}</span>
                    <span className="text-gray-500 text-xs">({p.code})</span>
                    <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', TYPE_COLORS[p.type])}>{p.type}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{p.shares.toLocaleString()} 份</span>
                    <span>成本 {p.costNav.toFixed(3)}</span>
                    <span>现价 {p.currentNav.toFixed(3)}</span>
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-white font-semibold text-sm">¥{p.amount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</p>
                  <p className={clsx('text-xs', gain >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
                    {profit >= 0 ? '+' : ''}¥{profit.toFixed(0)} ({gain >= 0 ? '+' : ''}{gain.toFixed(2)}%)
                  </p>
                </div>
                <button onClick={() => remove(p.id)}
                  className="p-2 text-gray-600 hover:text-[#f87171] transition flex-shrink-0">
                  <Trash2 size={16} />
                </button>
              </div>
              <div className="mt-2">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>占总持仓</span>
                  <span>{totalCurrent > 0 ? (p.amount / totalCurrent * 100).toFixed(1) : 0}%</span>
                </div>
                <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                  <div className={clsx('h-full rounded-full transition-all',
                    gain >= 0 ? 'bg-[#4ade80]' : 'bg-[#f87171]'
                  )} style={{ width: `${totalCurrent > 0 ? (p.amount / totalCurrent * 100).toFixed(1) : 0}%` }} />
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {showAdd && <AddModal onAdd={addPosition} onClose={() => setShowAdd(false)} />}
    </div>
  )
}
