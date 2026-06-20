import { useState, useRef, useEffect } from 'react'
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

interface Cell { username: string; platform: string; accuracy: number; postCount: number; url?: string; x: number; y: number; w: number; h: number }
type TreeNode = Cell & { area: number }

function squarified(items: Cell[], x: number, y: number, w: number, h: number): Cell[] {
  const total = items.reduce((s, i) => s + i.postCount, 0)
  if (total === 0) return []
  const nodes: TreeNode[] = [...items]
    .sort((a, b) => b.postCount - a.postCount)
    .map(i => ({ ...i, area: (i.postCount / total) * w * h, x: 0, y: 0, w: 0, h: 0 }))
  const result: Cell[] = []

  function layoutRow(row: TreeNode[], rowArea: number, rx: number, ry: number, rw: number, rh: number, horiz: boolean) {
    const rowTotal = row.reduce((s, n) => s + n.area, 0)
    let pos = horiz ? ry : rx
    row.forEach(n => {
      const frac = n.area / rowTotal
      const cw = horiz ? rowArea / rh : rw * frac
      const ch = horiz ? rh * frac : rowArea / rw
      result.push({ ...n, x: horiz ? rx : pos, y: horiz ? pos : ry, w: cw, h: ch })
      pos += horiz ? ch : cw
    })
  }
  function worstRatio(row: TreeNode[], side: number): number {
    const rowArea = row.reduce((s, n) => s + n.area, 0)
    return row.reduce((worst, n) => Math.max(worst, Math.max((side*side*n.area)/(rowArea*rowArea), (rowArea*rowArea)/(side*side*n.area))), 0)
  }
  function squarify(ns: TreeNode[], rx: number, ry: number, rw: number, rh: number) {
    if (!ns.length) return
    const horiz = rw >= rh
    const side = horiz ? rh : rw
    let row: TreeNode[] = []
    for (let i = 0; i < ns.length; i++) {
      const candidate = [...row, ns[i]]
      if (!row.length || worstRatio(candidate, side) <= worstRatio(row, side)) row = candidate
      else {
        const rowArea = row.reduce((s, n) => s + n.area, 0)
        const rowDim = rowArea / side
        layoutRow(row, rowArea, rx, ry, rw, rh, horiz)
        if (horiz) squarify(ns.slice(i), rx + rowDim, ry, rw - rowDim, rh)
        else squarify(ns.slice(i), rx, ry + rowDim, rw, rh - rowDim)
        return
      }
    }
    if (row.length) layoutRow(row, row.reduce((s, n) => s + n.area, 0), rx, ry, rw, rh, horiz)
  }
  squarify(nodes, x, y, w, h)
  return result
}

const PLATFORM_LABEL: Record<string, string> = { weibo: '微博', eastmoney_analyst: '东财分析师' }

export default function BloggerHeatmap() {
  const [bloggers, setBloggers] = useState<BloggerData[]>([])
  const [loading, setLoading] = useState(true)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; item: BloggerData } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    fetch('/data/bloggers.json').then(r => r.json()).then(d => { setBloggers(d.items || []); setLoading(false) }).catch(() => setLoading(false))
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }))
    obs.observe(el)
    setSize({ w: el.clientWidth, h: el.clientHeight })
    return () => obs.disconnect()
  }, [])

  const cells = size.w > 0
    ? squarified(bloggers.map(b => ({ ...b, x: 0, y: 0, w: 0, h: 0 })), 0, 0, size.w, size.h)
    : []

  if (loading) return <div className="flex items-center justify-center h-full"><Loader2 className="animate-spin text-[#00d4aa]" size={32} /></div>

  return (
    <div className="p-3 md:p-6 h-full flex flex-col">
      <div className="mb-3 md:mb-5">
        <h1 className="text-lg md:text-2xl font-bold text-white mb-1">博主热力图</h1>
        <p className="text-gray-400 text-xs md:text-sm">方块大小 = 预测次数 · 颜色 = 准确率 · 绿色越深越准</p>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[#1f2937] text-gray-400 hover:text-white text-sm transition">
          <RefreshCw size={14} />刷新
        </button>
        <div className="ml-auto flex items-center gap-4 text-xs text-gray-500">
          {[['#14532d','≥70%'],['#166534','60-70%'],['#713f12','50-60%'],['#7f1d1d','<50%']].map(([c,l]) => (
            <span key={l} className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-sm inline-block" style={{background:c}}/>{l}</span>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex flex-col md:flex-row gap-3 md:gap-4">
        {/* 博主列表 - 手机横向滚动，电脑侧边栏 */}
        <div className="md:w-52 md:flex-shrink-0 bg-[#0d1220] border border-[#1f2937] rounded-2xl p-3 md:p-4">
          <span className="text-white text-sm font-semibold mb-2 md:mb-3 hidden md:block">博主准确率排名</span>
          {bloggers.length === 0 ? (
            <div className="text-center text-gray-500 py-8 text-sm">暂无数据</div>
          ) : (
            <div className="flex md:flex-col gap-2 overflow-x-auto md:overflow-y-auto">
              {[...bloggers].sort((a, b) => b.accuracy - a.accuracy).map((b, i) => {
                const Wrapper = b.url ? 'a' : 'div'
                return (
                <Wrapper key={i} {...(b.url ? { href: b.url, target: '_blank', rel: 'noopener noreferrer' } : {})} className="flex items-center justify-between px-2 md:px-1 py-1.5 rounded-lg hover:bg-[#1f2937] transition whitespace-nowrap shrink-0 md:shrink cursor-pointer">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-gray-600 text-xs w-4">{i + 1}</span>
                    <span className="text-gray-300 text-xs truncate max-w-[60px] md:max-w-[80px] hover:text-[#00d4aa]">{b.username}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-gray-500 hidden md:inline">{b.postCount}帖</span>
                    <span style={{ color: accuracyText(b.accuracy) }}>{(b.accuracy * 100).toFixed(0)}%</span>
                  </div>
                </Wrapper>
                )
              })}
            </div>
          )}
        </div>

        {/* 热力图 */}
        <div ref={containerRef} className="h-[300px] md:h-auto md:flex-1 md:min-h-0 bg-[#0d1220] rounded-2xl border border-[#1f2937] relative overflow-hidden">
          {bloggers.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center text-gray-500 text-sm">暂无博主数据</div>
          ) : size.w > 0 && (
            <svg width={size.w} height={size.h}>
              {cells.map((cell, i) => {
                const bg = accuracyBg(cell.accuracy)
                const tc = accuracyText(cell.accuracy)
                const gap = 3
                const cx = cell.x + gap, cy = cell.y + gap
                const cw = cell.w - gap * 2, ch = cell.h - gap * 2
                if (cw < 4 || ch < 4) return null
                return (
                  <g key={i} onMouseEnter={e => setTooltip({ x: e.clientX, y: e.clientY, item: cell })} onMouseLeave={() => setTooltip(null)} onClick={() => cell.url && window.open(cell.url, '_blank')} style={{ cursor: cell.url ? 'pointer' : 'default' }}>
                    <rect x={cx} y={cy} width={cw} height={ch} fill={bg} rx={8} />
                    {cw > 55 && ch > 36 && (
                      <text x={cx + 8} y={cy + 20} fill="#fff" fontSize={Math.min(13, cw / 5)} fontWeight={600} style={{ pointerEvents: 'none' }}>
                        {cell.username.length > 7 ? cell.username.slice(0, 6) + '…' : cell.username}
                      </text>
                    )}
                    {cw > 55 && ch > 52 && (
                      <text x={cx + 8} y={cy + 36} fill={tc} fontSize={11} style={{ pointerEvents: 'none' }}>
                        {(cell.accuracy * 100).toFixed(0)}% 准确率
                      </text>
                    )}
                    {cw > 55 && ch > 70 && (
                      <text x={cx + 8} y={cy + 52} fill="#9ca3af" fontSize={10} style={{ pointerEvents: 'none' }}>
                        {PLATFORM_LABEL[cell.platform] || cell.platform}
                      </text>
                    )}
                    {cw > 55 && ch > 90 && (
                      <text x={cx + cw - 8} y={cy + ch - 8} fill="#6b7280" fontSize={10} textAnchor="end" style={{ pointerEvents: 'none' }}>
                        {cell.postCount}次
                      </text>
                    )}
                  </g>
                )
              })}
            </svg>
          )}
          {tooltip && (
            <div className="fixed z-50 pointer-events-none bg-[#1f2937] border border-[#374151] rounded-xl p-3 text-sm shadow-2xl" style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}>
              <p className="text-white font-semibold mb-1">{tooltip.item.username}</p>
              <p className="text-gray-400 mb-0.5">平台 <span className="text-white">{PLATFORM_LABEL[tooltip.item.platform] || tooltip.item.platform}</span></p>
              <p className="text-gray-400 mb-0.5">准确率 <span style={{ color: accuracyText(tooltip.item.accuracy) }}>{(tooltip.item.accuracy * 100).toFixed(0)}%</span></p>
              <p className="text-gray-400">预测次数 <span className="text-white">{tooltip.item.postCount}</span></p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
