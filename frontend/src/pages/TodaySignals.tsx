import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Star, Clock, Newspaper, Users, ChevronDown, ChevronUp, Globe, BarChart3, ExternalLink, Loader2 } from 'lucide-react'
import clsx from 'clsx'

// ── 数据类型 ──
interface NewsItem {
  title: string; url: string; source: string
  publishTime: string | null
  sentimentScore: number | null
  sentimentLabel: string | null
  summary?: string | null
}
interface PredictionItem {
  content: string; url: string
  direction: string | null; confidence: number
  postTime: string | null
  blogger: string; platform: string
}
interface SignalItem {
  target_name: string; target_symbol: string
  final_signal: string; confidence: number
  reasoning: string | null
  signal_date: string
  blogger_consensus_score: number | null
  news_sentiment_score: number | null
  retail_sentiment_score: number | null
  fund_flow_score: number | null
  industry_momentum_score: number | null
  analyzed_news_count: number | null
}

// ── 工具函数 ──
function fmtTime(iso: string | null): string {
  if (!iso) return '--:--'
  try { return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false }) }
  catch { return '--:--' }
}

function fmtDate(iso: string | null): string {
  if (!iso) return ''
  try { return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) }
  catch { return '' }
}

// ── UI 组件 ──
function SentimentBadge({ score, label }: { score: number | null; label: string | null }) {
  if (!label || score === null) return <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-400">待分析</span>
  const colorMap: Record<string, string> = {
    positive: 'bg-green-900/50 text-green-400 border-green-800',
    negative: 'bg-red-900/50 text-red-400 border-red-800',
    neutral: 'bg-gray-700/50 text-gray-300 border-gray-600',
  }
  return <span className={clsx('text-xs px-2 py-0.5 rounded border', colorMap[label])}>{score > 0 ? '+' : ''}{score.toFixed(2)}</span>
}

function PlatformBadge({ platform }: { platform: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    weibo: { label: '微博', cls: 'bg-red-900/40 text-red-300 border-red-800/50' },
    eastmoney_analyst: { label: '东财', cls: 'bg-orange-900/40 text-orange-300 border-orange-800/50' },
  }
  const info = map[platform] || { label: platform, cls: 'bg-gray-700 text-gray-300' }
  return <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border font-medium', info.cls)}>{info.label}</span>
}

function DirectionIcon({ direction }: { direction: string | null }) {
  if (direction === 'bullish') return <TrendingUp size={16} className="text-green-400" />
  if (direction === 'bearish') return <TrendingDown size={16} className="text-red-400" />
  return <div className="w-4 h-4 rounded-full bg-gray-600" />
}

function ScoreBar({ score, label }: { score: number | null; label: string }) {
  const pct = score !== null ? Math.abs(score) * 100 : 0
  const color = score === null ? 'bg-gray-600' : score > 0.3 ? 'bg-green-500' : score > 0 ? 'bg-green-600' : score < -0.3 ? 'bg-red-500' : 'bg-red-600'
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-14 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 max-w-[80px] md:max-w-[80px] w-full bg-gray-700 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-xs font-mono w-10 text-right shrink-0', score === null ? 'text-gray-600' : score > 0 ? 'text-green-400' : 'text-red-400')}>
        {score !== null ? (score > 0 ? '+' : '') + score.toFixed(2) : 'N/A'}
      </span>
    </div>
  )
}

function useApiData<T>(url: string) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    fetch(url).then(r => r.json()).then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [url])
  return { data, loading }
}

// ── 主组件 ──
const FILTERS = ['全部', '看多', '看空'] as const
type SourceTab = 'news' | 'bloggers'

export default function TodaySignals() {
  const [filter, setFilter] = useState<typeof FILTERS[number]>('全部')
  const [sourceTab, setSourceTab] = useState<SourceTab>('news')
  const [sourceExpanded, setSourceExpanded] = useState(true)

  const { data: newsData, loading: newsLoading } = useApiData<{ items: NewsItem[] }>('/data/news.json')
  const { data: predData, loading: predLoading } = useApiData<{ items: PredictionItem[] }>('/data/predictions.json')
  const { data: sigData, loading: sigLoading } = useApiData<{ items: SignalItem[] }>('/data/signals.json')

  if (newsLoading || predLoading || sigLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="animate-spin text-[#00d4aa]" size={32} /></div>
  }

  const news = newsData?.items || []
  const predictions = predData?.items || []
  const signals = sigData?.items || []
  const latest = signals[0] // 最新一天的信号

  const bullCount = signals.filter(s => s.final_signal === 'buy').length
  const bearCount = signals.filter(s => s.final_signal === 'sell').length
  const avgConf = signals.length ? (signals.reduce((s, sig) => s + (sig.confidence || 0), 0) / signals.length).toFixed(1) : '0.0'
  const analyzedNews = news.filter(n => n.sentimentScore !== null).length
  const bullishBloggers = predictions.filter(p => p.direction === 'bullish').length

  const filteredSignals = signals.filter(s => {
    if (filter === '看多') return s.final_signal === 'buy'
    if (filter === '看空') return s.final_signal === 'sell'
    return true
  })

  return (
    <div className="p-3 md:p-6 flex flex-col min-h-0 overflow-auto">
      {/* 1. 信号总览 */}
      <div className="grid grid-cols-3 gap-2 md:gap-4 mb-3 md:mb-5">
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">今日信号</p>
          <p className="text-white text-2xl font-bold">{signals.length || '—'}</p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">看多/看空</p>
          <p className="text-white text-2xl font-bold">
            <span className="text-[#4ade80]">{bullCount || '—'}</span>
            <span className="text-gray-500 mx-1">/</span>
            <span className="text-[#f87171]">{bearCount || '—'}</span>
          </p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">平均置信度</p>
          <p className="text-white text-2xl font-bold">{avgConf} {parseFloat(avgConf) > 0 && <span className="text-[#fbbf24]">★</span>}</p>
        </div>
      </div>

      {/* 2. 信号维度评分 */}
      {latest && (
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4 mb-5">
          <h3 className="text-gray-300 text-sm font-medium mb-3 flex items-center gap-2">
            <BarChart3 size={14} className="text-[#00d4aa]" />
            信号维度评分 — {latest.target_name} ({fmtDate(latest.signal_date)})
          </h3>
          <div className="grid grid-cols-2 md:flex md:flex-wrap gap-x-4 md:gap-x-6 gap-y-2">
            <ScoreBar score={latest.blogger_consensus_score} label="博主共识" />
            <ScoreBar score={latest.news_sentiment_score} label="新闻情绪" />
            <ScoreBar score={latest.retail_sentiment_score} label="散户情绪" />
            <ScoreBar score={latest.fund_flow_score} label="资金面" />
            <ScoreBar score={latest.industry_momentum_score} label="行业动能" />
          </div>
        </div>
      )}

      {/* 3. 数据源面板 */}
      <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl overflow-hidden mb-5">
        <button onClick={() => setSourceExpanded(!sourceExpanded)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition">
          <div className="flex items-center gap-3">
            <Globe size={16} className="text-[#00d4aa]" />
            <span className="text-white text-sm font-medium">数据溯源</span>
            <span className="text-gray-500 text-xs">
              新闻 {analyzedNews}/{news.length} 已分析
              <span className="mx-2 text-gray-700">|</span>
              博主 {bullishBloggers} 看多 / {predictions.length} 条
            </span>
          </div>
          {sourceExpanded ? <ChevronUp size={16} className="text-gray-500" /> : <ChevronDown size={16} className="text-gray-500" />}
        </button>

        {sourceExpanded && (
          <>
            <div className="flex border-t border-[#1f2937]">
              <button onClick={() => setSourceTab('news')} className={clsx('flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition border-b-2', sourceTab === 'news' ? 'text-[#00d4aa] border-[#00d4aa] bg-[#00d4aa08]' : 'text-gray-400 border-transparent hover:text-gray-200')}>
                <Newspaper size={14} /> 新闻 ({news.length})
              </button>
              <button onClick={() => setSourceTab('bloggers')} className={clsx('flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition border-b-2', sourceTab === 'bloggers' ? 'text-[#00d4aa] border-[#00d4aa] bg-[#00d4aa08]' : 'text-gray-400 border-transparent hover:text-gray-200')}>
                <Users size={14} /> 博主动态 ({predictions.length})
              </button>
            </div>

            {/* 新闻列表 */}
            {sourceTab === 'news' && (
              <div className="min-h-[200px] max-h-[50vh] overflow-y-auto divide-y divide-[#1f2937]/50">
                {news.length === 0 ? (
                  <div className="text-center text-gray-500 py-8 text-sm">暂无新闻数据</div>
                ) : news.map((n, i) => (
                  <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition">
                    <span className="text-gray-500 text-xs font-mono mt-0.5 shrink-0 w-10">{fmtTime(n.publishTime)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', n.source === 'eastmoney' ? 'bg-blue-900/30 text-blue-300 border-blue-800/40' : 'bg-purple-900/30 text-purple-300 border-purple-800/40')}>
                          {n.source === 'eastmoney' ? '东财' : n.source === 'eastmoney_fund' ? '基金' : n.source}
                        </span>
                        <SentimentBadge score={n.sentimentScore} label={n.sentimentLabel} />
                      </div>
                      {n.url?.startsWith('http') ? (
                        <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-gray-200 text-sm leading-snug mb-1 hover:text-[#00d4aa] transition inline-flex items-center gap-1">
                          {n.title}<ExternalLink size={12} className="text-gray-600 shrink-0" />
                        </a>
                      ) : <p className="text-gray-200 text-sm leading-snug mb-1">{n.title}</p>}
                      {n.summary && <p className="text-gray-500 text-xs leading-relaxed line-clamp-2">{n.summary}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 博主帖子列表 */}
            {sourceTab === 'bloggers' && (
              <div className="min-h-[200px] max-h-[50vh] overflow-y-auto divide-y divide-[#1f2937]/50">
                {predictions.length === 0 ? (
                  <div className="text-center text-gray-500 py-8 text-sm">暂无博主动态</div>
                ) : predictions.map((p, i) => (
                  <div key={i} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition">
                    <span className="text-gray-500 text-xs font-mono mt-0.5 shrink-0 w-10">{fmtTime(p.postTime)}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-white text-sm font-medium">{p.blogger}</span>
                        <PlatformBadge platform={p.platform} />
                        {p.direction && (
                          <div className="flex items-center gap-1">
                            <DirectionIcon direction={p.direction} />
                            <span className={clsx('text-[10px]', p.direction === 'bullish' ? 'text-green-400' : p.direction === 'bearish' ? 'text-red-400' : 'text-gray-400')}>
                              {p.direction === 'bullish' ? '看多' : p.direction === 'bearish' ? '看空' : '中性'}
                            </span>
                          </div>
                        )}
                      </div>
                      <p className="text-gray-300 text-sm leading-snug">{p.content}</p>
                      {p.url?.startsWith('http') && (
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-[#00d4aa] mt-1 transition">
                          <ExternalLink size={11} /> 查看详情
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* 4. 筛选 + 信号卡片 */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex bg-[#111827] border border-[#1f2937] rounded-lg p-0.5">
          {FILTERS.map(f => (
            <button key={f} onClick={() => setFilter(f)} className={clsx('px-3 py-1.5 rounded-md text-sm font-medium transition', filter === f ? 'bg-[#00d4aa] text-[#0a0e1a]' : 'text-gray-400 hover:text-white')}>{f}</button>
          ))}
        </div>
        <div className="ml-auto text-sm text-gray-500">共 {filteredSignals.length} 条信号</div>
      </div>

      <div className="flex flex-col gap-3">
        {filteredSignals.length === 0 ? (
          <div className="text-center text-gray-500 py-8 text-sm">暂无信号数据</div>
        ) : filteredSignals.map((sig, i) => (
          <div key={i} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-3 md:p-4 hover:border-[#374151] transition flex items-center gap-3 md:gap-4">
            <div className={clsx('w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center flex-shrink-0', sig.final_signal === 'buy' ? 'bg-[#14532d]' : sig.final_signal === 'sell' ? 'bg-[#7f1d1d]' : 'bg-[#374151]')}>
              {sig.final_signal === 'buy' ? <TrendingUp size={20} className="md:hidden text-[#4ade80]" /> : sig.final_signal === 'sell' ? <TrendingDown size={20} className="md:hidden text-[#f87171]" /> : <div className="w-5 h-5 md:hidden rounded-full bg-gray-500" />}
              {sig.final_signal === 'buy' ? <TrendingUp size={24} className="hidden md:block text-[#4ade80]" /> : sig.final_signal === 'sell' ? <TrendingDown size={24} className="hidden md:block text-[#f87171]" /> : <div className="hidden md:block w-6 h-6 rounded-full bg-gray-500" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-white font-semibold text-base truncate">{sig.target_name}</h3>
                <span className="text-gray-500 text-xs">({sig.target_symbol})</span>
                <span className={clsx('text-xs px-2 py-0.5 rounded', sig.final_signal === 'buy' ? 'bg-green-900/40 text-green-400' : sig.final_signal === 'sell' ? 'bg-red-900/40 text-red-400' : 'bg-gray-700 text-gray-300')}>
                  {sig.final_signal === 'buy' ? '买入' : sig.final_signal === 'sell' ? '卖出' : '持有'}
                </span>
              </div>
              {sig.reasoning && <p className="text-gray-400 text-sm line-clamp-2">{sig.reasoning}</p>}
              <p className="text-gray-600 text-xs mt-1">{fmtDate(sig.signal_date)}</p>
            </div>
            <div className="flex flex-col items-end gap-2 flex-shrink-0">
              <div className="flex items-center gap-0.5">
                {Array.from({ length: 5 }).map((_, j) => (
                  <Star key={j} size={14} className={clsx(j < Math.round(sig.confidence || 0), 'text-[#fbbf24] fill-[#fbbf24]', 'text-gray-600')} />
                ))}
              </div>
              <div className="flex items-center gap-1 text-gray-500 text-xs">
                <span>{(sig.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
