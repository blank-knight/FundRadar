import { useState, useEffect } from 'react'
import { Plus, Trash2, TrendingUp, TrendingDown, Wallet, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import PortfolioAdvice from '../components/PortfolioAdvice'
import ScreenshotUpload from '../components/ScreenshotUpload'

interface Holding {
  id?: number
  fund_code: string
  fund_name: string
  fund_type?: string
  shares?: number
  cost_price?: number
  cost_total?: number
  current_price?: number
  current_value?: number
  profit_loss?: number
  profit_loss_pct?: number
}

type SortKey = 'profit' | 'amount' | 'name'

function AddModal({ onAdd, onClose }: { onAdd: (p: { fund_name: string; fund_code: string }) => void; onClose: () => void }) {
  const [form, setForm] = useState({ name: '', code: '' })
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = () => {
    if (!form.name || !form.code) return
    onAdd({ fund_name: form.name, fund_code: form.code })
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-[#111827] border border-[#1f2937] rounded-2xl p-5 w-full max-w-sm" onClick={e => e.stopPropagation()}>
        <h2 className="text-white font-bold text-lg mb-4">添加持仓</h2>
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-gray-400 text-xs mb-1 block">基金名称</label>
            <input value={form.name} onChange={e => set('name', e.target.value)}
              placeholder="如：易方达蓝筹精选"
              className="w-full bg-[#0d1220] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#00d4aa]" />
          </div>
          <div>
            <label className="text-gray-400 text-xs mb-1 block">基金代码</label>
            <input value={form.code} onChange={e => set('code', e.target.value)}
              placeholder="如：005827"
              className="w-full bg-[#0d1220] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#00d4aa]" />
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
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [sort, setSort] = useState<SortKey>('amount')
  const [showAdd, setShowAdd] = useState(false)

  // 从 portfolio.json 加载持仓
  const loadHoldings = () => {
    fetch('/data/portfolio.json')
      .then(r => r.json())
      .then(d => { setHoldings(d.holdings || []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { loadHoldings() }, [])

  // 删除持仓
  const remove = async (fundCode: string) => {
    setDeleting(fundCode)
    try {
      const resp = await fetch('/api/delete-position', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fund_code: fundCode }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error || '删除失败')
      // 本地移除
      setHoldings(prev => prev.filter(h => h.fund_code !== fundCode))
    } catch (err) {
      alert('删除失败: ' + (err as Error).message)
    } finally {
      setDeleting(null)
    }
  }

  const sorted = [...holdings].sort((a, b) => {
    if (sort === 'profit') return (b.profit_loss_pct ?? -999) - (a.profit_loss_pct ?? -999)
    if (sort === 'amount') return (b.current_value ?? 0) - (a.current_value ?? 0)
    return (a.fund_name || '').localeCompare(b.fund_name || '')
  })

  const totalCost = holdings.reduce((s, h) => s + (h.cost_total ?? 0), 0)
  const totalCurrent = holdings.reduce((s, h) => s + (h.current_value ?? 0), 0)
  const totalProfit = holdings.reduce((s, h) => s + (h.profit_loss ?? 0), 0)
  const totalPct = totalCost > 0 ? (totalProfit / totalCost * 100) : 0

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="animate-spin text-[#00d4aa]" size={24} />
      </div>
    )
  }

  return (
    <div className="p-3 md:p-6 h-full flex flex-col overflow-auto">
      <div className="flex items-start justify-between mb-4 flex-wrap gap-2">
        <div>
          <h1 className="text-lg md:text-2xl font-bold text-white mb-1">我的持仓</h1>
          <p className="text-gray-400 text-xs md:text-sm">AI 分析新闻和分析师评级，帮你的持仓做决策</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <ScreenshotUpload onImported={() => setTimeout(() => loadHoldings(), 3000)} />
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-3 md:px-4 py-2 bg-[#00d4aa] text-[#0a0e1a] rounded-lg text-sm font-semibold hover:bg-[#00b894] transition">
            <Plus size={16} /><span className="hidden md:inline">手动添加</span>
          </button>
        </div>
      </div>

      {/* AI 操作建议 */}
      <div className="mb-5">
        <PortfolioAdvice />
      </div>

      {/* 总览卡片 */}
      {holdings.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-4">
          <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4">
            <p className="text-gray-400 text-xs mb-1 flex items-center gap-1"><Wallet size={12} />总市值</p>
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
      {holdings.length > 0 && (
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
        {holdings.length === 0 ? (
          <div className="text-center text-gray-500 py-6 text-sm">
            暂无持仓。点击「截图导入」上传持仓截图，或「手动添加」。
          </div>
        ) : sorted.map(h => {
          const pnl = h.profit_loss ?? 0
          const pnlPct = h.profit_loss_pct ?? 0
          const val = h.current_value ?? 0
          return (
            <div key={h.fund_code} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4 hover:border-[#374151] transition">
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-white font-semibold text-sm">{h.fund_name}</span>
                    <span className="text-gray-500 text-xs">({h.fund_code})</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    {h.shares && <span>{h.shares.toLocaleString()} 份</span>}
                    {h.cost_price && <span>成本 {h.cost_price.toFixed(3)}</span>}
                    {h.current_price && <span>现价 {h.current_price.toFixed(3)}</span>}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-white font-semibold text-sm">¥{val.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</p>
                  <p className={clsx('text-xs', pnl >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
                    {pnl >= 0 ? '+' : ''}¥{pnl.toFixed(0)} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)
                  </p>
                </div>
                <button
                  onClick={() => remove(h.fund_code)}
                  disabled={deleting === h.fund_code}
                  className="p-2 text-gray-600 hover:text-[#f87171] transition flex-shrink-0 disabled:opacity-50">
                  {deleting === h.fund_code
                    ? <Loader2 size={16} className="animate-spin" />
                    : <Trash2 size={16} />}
                </button>
              </div>
              {/* 占比进度条 */}
              {totalCurrent > 0 && (
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>占总持仓</span>
                    <span>{(val / totalCurrent * 100).toFixed(1)}%</span>
                  </div>
                  <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                    <div className={clsx('h-full rounded-full transition-all',
                      pnl >= 0 ? 'bg-[#4ade80]' : 'bg-[#f87171]'
                    )} style={{ width: `${(val / totalCurrent * 100).toFixed(1)}%` }} />
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {showAdd && <AddModal onAdd={() => setTimeout(() => loadHoldings(), 3000)} onClose={() => setShowAdd(false)} />}
    </div>
  )
}
