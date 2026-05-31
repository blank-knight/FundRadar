import { useState } from 'react'
import { TrendingUp, TrendingDown, Star, Clock } from 'lucide-react'
import clsx from 'clsx'

type Signal = {
  id: number
  direction: 'bull' | 'bear'  // 看多/看空
  fundName: string
  fundCode: string
  blogger: { name: string; accuracy: number; avatar: string }
  confidence: number  // 1-5星
  reason: string
  time: string
}

const MOCK_SIGNALS: Signal[] = [
  { id: 1, direction: 'bull', fundName: '易方达蓝筹精选', fundCode: '005827',
    blogger: { name: 'ETF拯救世界', accuracy: 71, avatar: '🎯' },
    confidence: 5, reason: '科技板块反弹信号明确，建议加仓', time: '09:15' },
  { id: 2, direction: 'bull', fundName: '华夏沪深300ETF', fundCode: '510330',
    blogger: { name: '张坤', accuracy: 73, avatar: '💎' },
    confidence: 4, reason: '大盘企稳，指数基金配置时机', time: '08:50' },
  { id: 3, direction: 'bear', fundName: '招商中证白酒', fundCode: '161725',
    blogger: { name: '但斌', accuracy: 62, avatar: '🍷' },
    confidence: 3, reason: '白酒板块短期承压，建议观望', time: '08:30' },
  { id: 4, direction: 'bull', fundName: '南方中证500ETF', fundCode: '510500',
    blogger: { name: '持有封基', accuracy: 68, avatar: '📊' },
    confidence: 4, reason: '中小盘估值修复行情启动', time: '09:00' },
  { id: 5, direction: 'bear', fundName: '天弘医药100', fundCode: '001550',
    blogger: { name: '林园', accuracy: 59, avatar: '💊' },
    confidence: 2, reason: '医药板块政策不确定性增加', time: '07:45' },
  { id: 6, direction: 'bull', fundName: '兴全合润混合', fundCode: '163406',
    blogger: { name: '价值投资者', accuracy: 66, avatar: '📈' },
    confidence: 5, reason: '价值回归，长期配置良机', time: '09:20' },
]

const FILTERS = ['全部', '看多', '看空'] as const
const SORTS = [
  { label: '置信度', key: 'confidence' },
  { label: '准确率', key: 'accuracy' },
  { label: '时间', key: 'time' },
] as const

export default function TodaySignals() {
  const [filter, setFilter] = useState<typeof FILTERS[number]>('全部')
  const [sort, setSort] = useState<typeof SORTS[number]['key']>('confidence')

  const filtered = MOCK_SIGNALS.filter(s => {
    if (filter === '看多') return s.direction === 'bull'
    if (filter === '看空') return s.direction === 'bear'
    return true
  })

  const sorted = [...filtered].sort((a, b) => {
    if (sort === 'confidence') return b.confidence - a.confidence
    if (sort === 'accuracy') return b.blogger.accuracy - a.blogger.accuracy
    if (sort === 'time') return a.time.localeCompare(b.time)
    return 0
  })

  const bullCount = MOCK_SIGNALS.filter(s => s.direction === 'bull').length
  const bearCount = MOCK_SIGNALS.filter(s => s.direction === 'bear').length
  const avgConf = (MOCK_SIGNALS.reduce((s, sig) => s + sig.confidence, 0) / MOCK_SIGNALS.length).toFixed(1)

  return (
    <div className="p-6 h-full flex flex-col overflow-auto">
      {/* 顶部统计卡片 */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">今日信号</p>
          <p className="text-white text-2xl font-bold">{MOCK_SIGNALS.length}</p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">看多/看空</p>
          <p className="text-white text-2xl font-bold">
            <span className="text-[#4ade80]">{bullCount}</span>
            <span className="text-gray-500 mx-1">/</span>
            <span className="text-[#f87171]">{bearCount}</span>
          </p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">平均置信度</p>
          <p className="text-white text-2xl font-bold">{avgConf} <span className="text-[#fbbf24]">★</span></p>
        </div>
      </div>

      {/* 筛选 + 排序 */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex bg-[#111827] border border-[#1f2937] rounded-lg p-0.5">
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f)} className={clsx(
              'px-3 py-1.5 rounded-md text-sm font-medium transition',
              filter === f ? 'bg-[#00d4aa] text-[#0a0e1a]' : 'text-gray-400 hover:text-white'
            )}>{f}</button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>排序：</span>
          {SORTS.map(s => (
            <button key={s.key} onClick={() => setSort(s.key)} className={clsx(
              'px-2 py-1 rounded transition',
              sort === s.key ? 'text-[#00d4aa]' : 'hover:text-white'
            )}>{s.label}</button>
          ))}
        </div>
        <div className="ml-auto text-sm text-gray-500">
          共 {sorted.length} 条信号
        </div>
      </div>

      {/* 信号卡片流 */}
      <div className="flex flex-col gap-3">
        {sorted.map(sig => (
          <div key={sig.id} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4 hover:border-[#374151] transition flex items-center gap-4">
            {/* 左侧方向图标 */}
            <div className={clsx(
              'w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0',
              sig.direction === 'bull' ? 'bg-[#14532d]' : 'bg-[#7f1d1d]'
            )}>
              {sig.direction === 'bull'
                ? <TrendingUp size={24} className="text-[#4ade80]" />
                : <TrendingDown size={24} className="text-[#f87171]" />
              }
            </div>

            {/* 中间内容 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-white font-semibold text-base truncate">{sig.fundName}</h3>
                <span className="text-gray-500 text-xs">({sig.fundCode})</span>
              </div>
              <div className="flex items-center gap-3 mb-2">
                <div className="flex items-center gap-1.5">
                  <span className="text-xl">{sig.blogger.avatar}</span>
                  <span className="text-gray-300 text-sm">{sig.blogger.name}</span>
                  <span className="text-[#00d4aa] text-xs font-medium">{sig.blogger.accuracy}%</span>
                </div>
              </div>
              <p className="text-gray-400 text-sm">{sig.reason}</p>
            </div>

            {/* 右侧置信度 + 时间 */}
            <div className="flex flex-col items-end gap-2 flex-shrink-0">
              <div className="flex items-center gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star key={i} size={14} className={clsx(
                    i < sig.confidence ? 'text-[#fbbf24] fill-[#fbbf24]' : 'text-gray-600'
                  )} />
                ))}
              </div>
              <div className="flex items-center gap-1 text-gray-500 text-xs">
                <Clock size={12} />
                <span>{sig.time}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
