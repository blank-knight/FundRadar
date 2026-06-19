import { useState, useEffect } from 'react'
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import clsx from 'clsx'

import { API_URL, USE_MOCK } from '../lib/api'

type Review = {
  id: number
  target_symbol: string
  trigger_reason: string
  review_start: string
  review_end: string
  total_signals: number
  correct_signals: number
  accuracy_rate: number
  problem_diagnosis: string
  suggested_adjustments: string
  learning_points: string
  reviewed_at: string
}

function AccuracyBadge({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color = pct >= 70 ? 'text-[#4ade80] bg-[#14532d]/40'
    : pct >= 50 ? 'text-[#fbbf24] bg-[#78350f]/40'
    : 'text-[#f87171] bg-[#7f1d1d]/40'
  return (
    <span className={clsx('text-xs px-2 py-0.5 rounded-full font-semibold', color)}>
      {pct}% 准确率
    </span>
  )
}

function ReviewCard({ r }: { r: Review }) {
  const [open, setOpen] = useState(false)
  const start = r.review_start?.slice(0, 10) ?? ''
  const end   = r.review_end?.slice(0, 10) ?? ''
  const at    = r.reviewed_at?.slice(0, 16).replace('T', ' ') ?? ''

  return (
    <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl overflow-hidden hover:border-[#374151] transition">
      {/* 头部 */}
      <button
        className="w-full flex items-center gap-4 p-4 text-left"
        onClick={() => setOpen(o => !o)}
      >
        <div className="w-10 h-10 rounded-lg bg-[#1f2937] flex items-center justify-center shrink-0">
          <AlertTriangle size={18} className="text-[#fbbf24]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-white font-semibold">{r.target_symbol}</span>
            <AccuracyBadge rate={r.accuracy_rate} />
            <span className="text-gray-500 text-xs">
              {r.correct_signals}/{r.total_signals} 次正确
            </span>
          </div>
          <p className="text-gray-400 text-xs truncate">{r.trigger_reason}</p>
        </div>
        <div className="text-right shrink-0 mr-2">
          <p className="text-gray-500 text-xs flex items-center gap-1 justify-end">
            <Clock size={11} />{at}
          </p>
          <p className="text-gray-600 text-xs mt-0.5">{start} ~ {end}</p>
        </div>
        {open
          ? <ChevronUp size={16} className="text-gray-500 shrink-0" />
          : <ChevronDown size={16} className="text-gray-500 shrink-0" />
        }
      </button>

      {/* 展开详情 */}
      {open && (
        <div className="border-t border-[#1f2937] p-4 flex flex-col gap-4">
          <Section icon="🔎" title="问题诊断" text={r.problem_diagnosis} />
          <Section icon="🛠" title="改进建议" text={r.suggested_adjustments} />
          <Section icon="📚" title="新手学习要点" text={r.learning_points} accent />
        </div>
      )}
    </div>
  )
}

function Section({ icon, title, text, accent }: {
  icon: string; title: string; text: string; accent?: boolean
}) {
  return (
    <div className={clsx(
      'rounded-lg p-3',
      accent ? 'bg-[#00d4aa08] border border-[#00d4aa20]' : 'bg-[#111827]'
    )}>
      <p className="text-xs font-semibold text-gray-300 mb-1.5">{icon} {title}</p>
      <p className="text-gray-400 text-sm leading-relaxed whitespace-pre-wrap">{text}</p>
    </div>
  )
}

export default function SignalReviewPage() {
  const [reviews, setReviews] = useState<Review[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')
  const [symbol, setSymbol] = useState('')

  const load = async (sym?: string) => {
    setLoading(true)
    setError('')
    try {
      if (USE_MOCK) {
        await new Promise(r => setTimeout(r, 500))
        setReviews([])
        setError('')
        return
      }
      const params = new URLSearchParams({ limit: '20', offset: '0' })
      if (sym) params.set('symbol', sym)
      const res = await fetch(`${API_URL}/signals/reviews?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setReviews(data.items ?? data.reviews ?? [])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  return (
    <div className="p-3 md:p-6 h-full flex flex-col overflow-auto">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">信号复盘报告</h1>
          <p className="text-gray-400 text-sm">系统自动生成的信号准确率复盘，帮助优化策略</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load(symbol || undefined)}
            placeholder="按标的筛选，如 000300"
            className="bg-[#0d1220] border border-[#1f2937] rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#00d4aa] w-52"
          />
          <button
            onClick={() => load(symbol || undefined)}
            className="px-4 py-2 bg-[#00d4aa] text-[#0a0e1a] rounded-lg text-sm font-semibold hover:bg-[#00b894] transition"
          >
            搜索
          </button>
          {symbol && (
            <button
              onClick={() => { setSymbol(''); load() }}
              className="px-3 py-2 border border-[#1f2937] text-gray-400 rounded-lg text-sm hover:text-white transition"
            >
              清除
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex-1 flex items-center justify-center text-gray-500">加载中...</div>
      )}

      {error && (
        <div className="flex items-center gap-2 text-[#f87171] bg-[#7f1d1d]/20 border border-[#7f1d1d]/40 rounded-lg p-3 mb-4 text-sm">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {!loading && !error && reviews.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center text-gray-500 gap-3">
          <CheckCircle size={40} className="text-[#4ade80] opacity-50" />
          <p className="text-base">暂无复盘报告</p>
          <p className="text-sm text-gray-600">系统会在信号准确率持续偏低时自动生成复盘</p>
        </div>
      )}

      {!loading && reviews.length > 0 && (
        <div className="flex flex-col gap-3">
          {reviews.map(r => <ReviewCard key={r.id} r={r} />)}
        </div>
      )}
    </div>
  )
}
