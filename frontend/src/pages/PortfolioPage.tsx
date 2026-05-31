import { useState } from 'react'
import { Plus, Trash2, TrendingUp, TrendingDown, Wallet, Sparkles, Loader2 } from 'lucide-react'
import clsx from 'clsx'

const API = 'http://localhost:8001/api'

type AnalysisResult = {
  fund_code: string
  recommendation: string   // 买入 | 持有 | 减仓 | 观望
  reasoning: string
  confidence: number
  error?: string
}

const REC_STYLE: Record<string, string> = {
  '买入': 'text-[#4ade80] bg-[#14532d]/40 border-[#4ade80]/30',
  '持有': 'text-[#60a5fa] bg-[#1e3a5f]/40 border-[#60a5fa]/30',
  '减仓': 'text-[#f87171] bg-[#7f1d1d]/40 border-[#f87171]/30',
  '观望': 'text-[#fbbf24] bg-[#78350f]/40 border-[#fbbf24]/30',
}

type Position = {
  id: number
  name: string
  code: string
  type: '股票型' | '混合型' | '债券型' | '指数型'
  shares: number       // 持有份额
  costNav: number      // 买入净值
  currentNav: number   // 当前净值
  amount: number       // 持仓金额（元）
  signal: 'bull' | 'bear' | 'neutral'  // 今日博主信号
}

const INIT_POSITIONS: Position[] = [
  { id:1, name:'易方达蓝筹精选', code:'005827', type:'股票型',
    shares:5000, costNav:1.820, currentNav:2.156, amount:10780, signal:'bull' },
  { id:2, name:'华夏沪深300ETF', code:'510330', type:'指数型',
    shares:8000, costNav:4.120, currentNav:4.380, amount:35040, signal:'bull' },
  { id:3, name:'招商中证白酒',   code:'161725', type:'指数型',
    shares:3000, costNav:1.650, currentNav:1.510, amount:4530,  signal:'bear' },
  { id:4, name:'兴全合润混合',   code:'163406', type:'混合型',
    shares:2000, costNav:3.200, currentNav:3.450, amount:6900,  signal:'bull' },
]

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

// 添加持仓弹窗
function AddModal({ onAdd, onClose }: { onAdd: (p: Position) => void; onClose: () => void }) {
  const [form, setForm] = useState({ name:'', code:'', type:'指数型' as Position['type'], shares:'', costNav:'' })
  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = () => {
    if (!form.name || !form.code || !form.shares || !form.costNav) return
    const shares = parseFloat(form.shares)
    const costNav = parseFloat(form.costNav)
    onAdd({ id: Date.now(), name: form.name, code: form.code, type: form.type,
      shares, costNav, currentNav: costNav, amount: shares * costNav, signal: 'neutral' })
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-[#111827] border border-[#1f2937] rounded-2xl p-6 w-96" onClick={e => e.stopPropagation()}>
        <h2 className="text-white font-bold text-lg mb-4">添加持仓</h2>
        <div className="flex flex-col gap-3">
          {[
            { label:'基金名称', key:'name', placeholder:'如：易方达蓝筹精选' },
            { label:'基金代码', key:'code', placeholder:'如：005827' },
            { label:'持有份额', key:'shares', placeholder:'如：5000' },
            { label:'买入净值', key:'costNav', placeholder:'如：1.820' },
          ].map(f => (
            <div key={f.key}>
              <label className="text-gray-400 text-xs mb-1 block">{f.label}</label>
              <input value={(form as Record<string,string>)[f.key]}
                onChange={e => set(f.key, e.target.value)}
                placeholder={f.placeholder}
                className="w-full bg-[#0d1220] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#00d4aa]" />
            </div>
          ))}
          <div>
            <label className="text-gray-400 text-xs mb-1 block">基金类型</label>
            <div className="flex gap-2 flex-wrap">
              {(['指数型','股票型','混合型','债券型'] as Position['type'][]).map(t => (
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
  const [positions, setPositions] = useState(INIT_POSITIONS)
  const [sort, setSort] = useState<SortKey>('amount')
  const [showAdd, setShowAdd] = useState(false)
  const [analysisMap, setAnalysisMap] = useState<Record<string, AnalysisResult>>({})
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisError, setAnalysisError] = useState('')

  const remove = (id: number) => setPositions(p => p.filter(x => x.id !== id))
  const addPosition = (p: Position) => setPositions(prev => [...prev, p])

  const runAnalysis = async () => {
    setAnalyzing(true)
    setAnalysisError('')
    try {
      // 用 mock token，实际对接后端 auth 时替换
      const token = 'mock-token'
      const res = await fetch(`${API}/portfolio/analyze/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ fund_codes: positions.map(p => p.code) }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const map: Record<string, AnalysisResult> = {}
      for (const item of data.results ?? []) {
        map[item.fund_code] = item
      }
      setAnalysisMap(map)
    } catch (e: unknown) {
      setAnalysisError(e instanceof Error ? e.message : '分析失败，请稍后重试')
    } finally {
      setAnalyzing(false)
    }
  }

  const sorted = [...positions].sort((a, b) => {
    if (sort === 'profit') return pct(b.costNav, b.currentNav) - pct(a.costNav, a.currentNav)
    if (sort === 'amount') return b.amount - a.amount
    return a.name.localeCompare(b.name)
  })

  const totalCost    = positions.reduce((s, p) => s + p.shares * p.costNav, 0)
  const totalCurrent = positions.reduce((s, p) => s + p.amount, 0)
  const totalProfit  = totalCurrent - totalCost
  const totalPct     = totalCost > 0 ? (totalProfit / totalCost * 100) : 0

  return (
    <div className="p-6 h-full flex flex-col overflow-auto">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">我的持仓</h1>
          <p className="text-gray-400 text-sm">管理持有的基金，结合博主信号辅助决策</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={runAnalysis} disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2 border border-[#00d4aa] text-[#00d4aa] rounded-lg text-sm font-semibold hover:bg-[#00d4aa15] transition disabled:opacity-50 disabled:cursor-not-allowed">
            {analyzing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {analyzing ? '分析中...' : 'AI 一键分析'}
          </button>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[#00d4aa] text-[#0a0e1a] rounded-lg text-sm font-semibold hover:bg-[#00b894] transition">
            <Plus size={16} />添加持仓
          </button>
        </div>
      </div>

      {/* 总览卡片 */}
      <div className="grid grid-cols-4 gap-4 mb-5">
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1 flex items-center gap-1"><Wallet size={12}/>总持仓</p>
          <p className="text-white text-xl font-bold">¥{totalCurrent.toLocaleString('zh-CN', {maximumFractionDigits:0})}</p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">总成本</p>
          <p className="text-white text-xl font-bold">¥{totalCost.toLocaleString('zh-CN', {maximumFractionDigits:0})}</p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">总盈亏</p>
          <p className={clsx('text-xl font-bold', totalProfit >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
            {totalProfit >= 0 ? '+' : ''}¥{totalProfit.toLocaleString('zh-CN', {maximumFractionDigits:0})}
          </p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">总收益率</p>
          <p className={clsx('text-xl font-bold', totalPct >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
            {totalPct >= 0 ? '+' : ''}{totalPct.toFixed(2)}%
          </p>
        </div>
      </div>

      {/* 分析错误提示 */}
      {analysisError && (
        <div className="flex items-center gap-2 text-[#f87171] bg-[#7f1d1d]/20 border border-[#7f1d1d]/40 rounded-lg p-3 mb-4 text-sm">
          ⚠️ {analysisError}
        </div>
      )}

      {/* 排序 */}
      <div className="flex items-center gap-2 mb-4 text-sm text-gray-400">
        <span>排序：</span>
        {([['amount','持仓金额'],['profit','收益率'],['name','名称']] as [SortKey,string][]).map(([k,l]) => (
          <button key={k} onClick={() => setSort(k)} className={clsx(
            'px-2 py-1 rounded transition',
            sort === k ? 'text-[#00d4aa]' : 'hover:text-white'
          )}>{l}</button>
        ))}
      </div>

      {/* 持仓列表 */}
      <div className="flex flex-col gap-3">
        {sorted.map(p => {
          const gain = pct(p.costNav, p.currentNav)
          const profit = p.amount - p.shares * p.costNav
          return (
            <div key={p.id} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4 hover:border-[#374151] transition">
              <div className="flex items-center gap-4">
                {/* 基金信息 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-semibold">{p.name}</span>
                    <span className="text-gray-500 text-xs">({p.code})</span>
                    <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', TYPE_COLORS[p.type])}>{p.type}</span>
                    {/* 今日信号 */}
                    {p.signal !== 'neutral' && (
                      <span className={clsx(
                        'flex items-center gap-1 text-xs px-2 py-0.5 rounded-full',
                        p.signal === 'bull' ? 'text-[#4ade80] bg-[#14532d]/40' : 'text-[#f87171] bg-[#7f1d1d]/40'
                      )}>
                        {p.signal === 'bull' ? <TrendingUp size={11}/> : <TrendingDown size={11}/>}
                        博主{p.signal === 'bull' ? '看多' : '看空'}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>{p.shares.toLocaleString()} 份</span>
                    <span>成本 {p.costNav.toFixed(3)}</span>
                    <span>现价 {p.currentNav.toFixed(3)}</span>
                  </div>
                </div>

                {/* 金额 + 盈亏 */}
                <div className="text-right flex-shrink-0">
                  <p className="text-white font-semibold">¥{p.amount.toLocaleString('zh-CN', {maximumFractionDigits:0})}</p>
                  <p className={clsx('text-sm', gain >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]')}>
                    {profit >= 0 ? '+' : ''}¥{profit.toFixed(0)} ({gain >= 0 ? '+' : ''}{gain.toFixed(2)}%)
                  </p>
                </div>

                {/* 删除 */}
                <button onClick={() => remove(p.id)}
                  className="p-2 text-gray-600 hover:text-[#f87171] transition flex-shrink-0">
                  <Trash2 size={16} />
                </button>
              </div>

              {/* 持仓占比进度条 */}
              <div className="mt-3">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>占总持仓</span>
                  <span>{(p.amount / totalCurrent * 100).toFixed(1)}%</span>
                </div>
                <div className="h-1.5 bg-[#1f2937] rounded-full overflow-hidden">
                  <div className={clsx('h-full rounded-full transition-all',
                    gain >= 0 ? 'bg-[#4ade80]' : 'bg-[#f87171]'
                  )} style={{ width: `${(p.amount / totalCurrent * 100).toFixed(1)}%` }} />
                </div>
              </div>

              {/* AI 分析建议 */}
              {analysisMap[p.code] && !analysisMap[p.code].error && (
                <div className="mt-3 pt-3 border-t border-[#1f2937]">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Sparkles size={12} className="text-[#00d4aa]" />
                    <span className="text-xs text-gray-400">AI 建议</span>
                    <span className={clsx(
                      'text-xs px-2 py-0.5 rounded-full border font-semibold',
                      REC_STYLE[analysisMap[p.code].recommendation] ?? 'text-gray-400 bg-gray-800 border-gray-700'
                    )}>
                      {analysisMap[p.code].recommendation}
                    </span>
                    <span className="text-xs text-gray-600 ml-auto">
                      置信度 {Math.round(analysisMap[p.code].confidence * 100)}%
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 leading-relaxed">
                    {analysisMap[p.code].reasoning}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {showAdd && <AddModal onAdd={addPosition} onClose={() => setShowAdd(false)} />}
    </div>
  )
}

