import { useState, useEffect } from 'react'
import { RefreshCw, Loader2 } from 'lucide-react'
import clsx from 'clsx'

interface BloggerData {
  username: string
  platform: string
  accuracy: number
  postCount: number
  url?: string
}

function accuracyBg(acc: number) {
  if (acc >= 0.7) return '#14532d'
  if (acc >= 0.6) return '#166534'
  if (acc >= 0.5) return '#713f12'
  return '#7f1d1d'
}
function accuracyText(acc: number) {
  if (acc >= 0.7) return '#4ade80'
  if (acc >= 0.6) return '#86efac'
  if (acc >= 0.5) return '#fbbf24'
  return '#f87171'
}

const PLATFORM_LABEL: Record<string, string> = { weibo: '微博', eastmoney_analyst: '东财分析师' }

export default function BloggerHeatmap() {
  const [bloggers, setBloggers] = useState<BloggerData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/data/bloggers.json')
      .then(r => r.json())
      .then(d => { setBloggers(d.items || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-full"><Loader2 className="animate-spin text-[#00d4aa]" size={32} /></div>
  }

  const sorted = [...bloggers].sort((a, b) => b.postCount - a.postCount)
  const maxPosts = sorted[0]?.postCount || 1

  return (
    <div className="p-3 md:p-6 h-full overflow-auto">
      {/* 标题 */}
      <div className="mb-3 md:mb-5">
        <h1 className="text-lg md:text-2xl font-bold text-white mb-1">博主热力图</h1>
        <p className="text-gray-400 text-xs md:text-sm">颜色 = 准确率 · 点击博主名跳转详情</p>
      </div>

      {/* 图例 */}
      <div className="flex items-center gap-3 md:gap-4 mb-4 text-[10px] md:text-xs text-gray-500 flex-wrap">
        {[['#14532d','≥70%'],['#166534','60-70%'],['#713f12','50-60%'],['#7f1d1d','<50%']].map(([c,l]) => (
          <span key={l} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm inline-block" style={{background:c}}/>{l}
          </span>
        ))}
      </div>

      {sorted.length === 0 ? (
        <div className="text-center text-gray-500 py-8 text-sm">暂无博主数据</div>
      ) : (
        /* 博主卡片网格 */
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2 md:gap-3">
          {sorted.map((b, i) => {
            const Wrapper = b.url ? 'a' : 'div'
            return (
              <Wrapper
                key={i}
                {...(b.url ? { href: b.url, target: '_blank', rel: 'noopener noreferrer' } : {})}
                className="rounded-xl p-3 border border-[#1f2937] hover:border-[#374151] transition flex flex-col gap-1"
                style={{ backgroundColor: accuracyBg(b.accuracy) }}
              >
                <span className="text-white text-xs md:text-sm font-semibold truncate">
                  {b.username.length > 8 ? b.username.slice(0, 7) + '…' : b.username}
                </span>
                <div className="flex items-center justify-between">
                  <span className="text-[10px] md:text-xs" style={{ color: accuracyText(b.accuracy) }}>
                    {(b.accuracy * 100).toFixed(0)}%
                  </span>
                  <span className="text-[10px] text-gray-400">{b.postCount}帖</span>
                </div>
                {/* 帖数条 */}
                <div className="h-1 bg-black/30 rounded-full overflow-hidden mt-0.5">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(b.postCount / maxPosts * 100)}%`,
                      backgroundColor: accuracyText(b.accuracy),
                    }}
                  />
                </div>
              </Wrapper>
            )
          })}
        </div>
      )}

      {/* 排名列表 */}
      <div className="mt-5">
        <h2 className="text-white text-sm font-semibold mb-3">准确率排名</h2>
        <div className="space-y-1">
          {[...bloggers].sort((a, b) => b.accuracy - a.accuracy).map((b, i) => {
            const Wrapper = b.url ? 'a' : 'div'
            return (
              <Wrapper
                key={i}
                {...(b.url ? { href: b.url, target: '_blank', rel: 'noopener noreferrer' } : {})}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-[#1f2937] transition"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-gray-600 text-xs w-5">{i + 1}</span>
                  <span className="text-gray-300 text-xs md:text-sm truncate">{b.username}</span>
                  <span className="text-gray-600 text-[10px]">{PLATFORM_LABEL[b.platform] || b.platform}</span>
                </div>
                <div className="flex items-center gap-3 text-xs shrink-0">
                  <span className="text-gray-500">{b.postCount}帖</span>
                  <span style={{ color: accuracyText(b.accuracy) }}>{(b.accuracy * 100).toFixed(0)}%</span>
                </div>
              </Wrapper>
            )
          })}
        </div>
      </div>
    </div>
  )
}
