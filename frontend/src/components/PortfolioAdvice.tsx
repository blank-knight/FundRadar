import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Minus, Eye, Flame, Lightbulb, Loader2, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

interface AdviceItem {
  code: string
  name: string
  action: string
  confidence: number
  reason: string
  key_news: string
}
interface SectorAlert {
  sector: string
  trend: string
  action: string
  reason: string
  heat: number
}
interface AdviceData {
  generated_at: string
  holdings: AdviceItem[]
  sector_alerts: SectorAlert[]
}

const ACTION_STYLE: Record<string, { icon: typeof TrendingUp; color: string; bg: string }> = {
  '加仓': { icon: TrendingUp, color: 'text-[#4ade80]', bg: 'bg-[#14532d]/40 border-[#4ade80]/30' },
  '减仓': { icon: TrendingDown, color: 'text-[#f87171]', bg: 'bg-[#7f1d1d]/40 border-[#f87171]/30' },
  '持有': { icon: Minus, color: 'text-[#60a5fa]', bg: 'bg-[#1e3a5f]/40 border-[#60a5fa]/30' },
  '观望': { icon: Eye, color: 'text-[#fbbf24]', bg: 'bg-[#78350f]/40 border-[#fbbf24]/30' },
}

function heatColor(heat: number) {
  if (heat >= 85) return 'text-[#f87171]'
  if (heat >= 70) return 'text-[#fbbf24]'
  return 'text-[#60a5fa]'
}

export default function PortfolioAdvice() {
  const [data, setData] = useState<AdviceData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/data/portfolio-advice.json')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center py-8"><Loader2 className="animate-spin text-[#00d4aa]" size={24} /></div>
  }

  if (!data) {
    return (
      <div className="text-center text-gray-500 py-8 text-sm">
        暂无分析数据
      </div>
    )
  }

  const genTime = data.generated_at
    ? new Date(data.generated_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    : ''

  return (
    <div className="space-y-4">
      {/* ── 我的仓位怎么办 ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Lightbulb size={16} className="text-[#00d4aa]" />
          <h2 className="text-white text-sm font-semibold">我的仓位怎么办</h2>
          {genTime && <span className="text-gray-600 text-[10px] ml-auto">更新于 {genTime}</span>}
        </div>

        {data.holdings.length === 0 ? (
          <div className="text-gray-500 text-sm bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
            请先在下方添加持仓，才能生成操作建议
          </div>
        ) : (
          <div className="space-y-2">
            {data.holdings.map((h, i) => {
              const style = ACTION_STYLE[h.action] || ACTION_STYLE['持有']
              const Icon = style.icon
              return (
                <div key={i} className={clsx('border rounded-xl p-3 md:p-4', style.bg)}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-white font-semibold text-sm">{h.name}</span>
                    <span className={clsx('flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-bold', style.color)}>
                      <Icon size={12} />{h.action}
                    </span>
                    <span className="text-gray-500 text-[10px] ml-auto">置信度 {h.confidence}%</span>
                  </div>
                  <p className="text-gray-300 text-xs leading-relaxed mb-1">{h.reason}</p>
                  {h.key_news && (
                    <p className="text-gray-500 text-[11px] mt-1.5 flex items-start gap-1">
                      <Flame size={11} className="shrink-0 mt-0.5 text-gray-600" />
                      {h.key_news}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── 赛道提醒 ── */}
      {data.sector_alerts.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Flame size={16} className="text-[#fbbf24]" />
            <h2 className="text-white text-sm font-semibold">你可能感兴趣的赛道</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {data.sector_alerts.map((s, i) => (
              <div key={i} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 hover:border-[#374151] transition">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-white text-sm font-medium">{s.sector}</span>
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border',
                    s.trend === '升温' ? 'text-[#f87171] bg-[#7f1d1d]/30 border-[#f87171]/30' :
                    s.trend === '降温' ? 'text-[#60a5fa] bg-[#1e3a5f]/30 border-[#60a5fa]/30' :
                    'text-gray-400 bg-gray-800 border-gray-700'
                  )}>{s.trend}</span>
                  <span className="text-[10px] text-gray-500 ml-auto">{s.action}</span>
                </div>
                <div className="flex items-center gap-2">
                  <p className="text-gray-400 text-[11px] flex-1">{s.reason}</p>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className={clsx('text-xs font-bold', heatColor(s.heat))}>{s.heat}</span>
                  </div>
                </div>
                <div className="h-1 bg-[#1f2937] rounded-full overflow-hidden mt-1.5">
                  <div className={clsx('h-full rounded-full',
                    s.heat >= 85 ? 'bg-[#f87171]' : s.heat >= 70 ? 'bg-[#fbbf24]' : 'bg-[#60a5fa]'
                  )} style={{ width: `${s.heat}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
