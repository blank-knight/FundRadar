import { useState, useRef, useEffect } from 'react'
import { RefreshCw } from 'lucide-react'
import clsx from 'clsx'

const MOCK_BLOGGERS = [
  { id:1, name: '但斌',        accuracy: 62, predictions: 34,  followers: 480000, trend: [58,60,61,62,62], d1: +2,  d7: +4  },
  { id:2, name: 'ETF拯救世界', accuracy: 71, predictions: 89,  followers: 120000, trend: [65,67,70,71,71], d1: +1,  d7: +6  },
  { id:3, name: '持有封基',    accuracy: 68, predictions: 56,  followers: 85000,  trend: [60,63,66,68,68], d1: +2,  d7: +8  },
  { id:4, name: '雪球基金',    accuracy: 55, predictions: 120, followers: 320000, trend: [58,56,55,55,55], d1: -1,  d7: -3  },
  { id:5, name: '张坤',        accuracy: 73, predictions: 28,  followers: 210000, trend: [68,70,72,73,73], d1: +1,  d7: +5  },
  { id:6, name: '林园',        accuracy: 59, predictions: 45,  followers: 95000,  trend: [62,61,60,59,59], d1: -1,  d7: -3  },
  { id:7, name: '但斌助理',    accuracy: 48, predictions: 22,  followers: 30000,  trend: [50,49,48,48,48], d1: -2,  d7: -7  },
  { id:8, name: '价值投资者',  accuracy: 66, predictions: 38,  followers: 55000,  trend: [63,64,65,66,66], d1: +1,  d7: +3  },
]

function accuracyBg(acc: number) {
  if (acc >= 70) return '#14532d'
  if (acc >= 60) return '#166534'
  if (acc >= 50) return '#713f12'
  return '#7f1d1d'
}
function accuracyText(acc: number) {
  if (acc >= 70) return '#4ade80'
  if (acc >= 60) return '#86efac'
  if (acc >= 50) return '#fbbf24'
  return '#f87171'
}

interface Cell {
  id: number; name: string; accuracy: number; predictions: number
  followers: number; trend: number[]; d1: number; d7: number
  x: number; y: number; w: number; h: number
}

// 带 area 字段的节点类型
type TreeNode = Cell & { area: number }

// 标准 squarified treemap
function squarified(items: typeof MOCK_BLOGGERS, x: number, y: number, w: number, h: number): Cell[] {
  const total = items.reduce((s, i) => s + i.predictions, 0)
  const nodes: TreeNode[] = [...items]
    .sort((a, b) => b.predictions - a.predictions)
    .map(i => ({ ...i, area: (i.predictions / total) * w * h, x: 0, y: 0, w: 0, h: 0 }))

  const result: Cell[] = []

  function layoutRow(row: TreeNode[], rowArea: number, rx: number, ry: number, rw: number, rh: number, horiz: boolean) {
    const rowTotal = row.reduce((s: number, n: TreeNode) => s + n.area, 0)
    let pos = horiz ? ry : rx
    row.forEach((n: TreeNode) => {
      const frac = n.area / rowTotal
      const cw = horiz ? rowArea / rh : rw * frac
      const ch = horiz ? rh * frac : rowArea / rw
      result.push({ ...n, x: horiz ? rx : pos, y: horiz ? pos : ry, w: cw, h: ch })
      pos += horiz ? ch : cw
    })
  }

  function worstRatio(row: TreeNode[], side: number): number {
    const rowArea = row.reduce((s: number, n: TreeNode) => s + n.area, 0)
    return row.reduce((worst: number, n: TreeNode) => {
      const a = n.area
      const r1 = (side * side * a) / (rowArea * rowArea)
      const r2 = (rowArea * rowArea) / (side * side * a)
      return Math.max(worst, Math.max(r1, r2))
    }, 0)
  }

  function squarify(ns: TreeNode[], rx: number, ry: number, rw: number, rh: number) {
    if (!ns.length) return
    const horiz = rw >= rh
    const side = horiz ? rh : rw
    let row: TreeNode[] = []

    for (let i = 0; i < ns.length; i++) {
      const candidate = [...row, ns[i]]
      if (!row.length || worstRatio(candidate, side) <= worstRatio(row, side)) {
        row = candidate
      } else {
        const rowArea = row.reduce((s: number, n: TreeNode) => s + n.area, 0)
        const rowDim = rowArea / side
        layoutRow(row, rowArea, rx, ry, rw, rh, horiz)
        if (horiz) squarify(ns.slice(i), rx + rowDim, ry, rw - rowDim, rh)
        else squarify(ns.slice(i), rx, ry + rowDim, rw, rh - rowDim)
        return
      }
    }
    if (row.length) {
      const rowArea = row.reduce((s: number, n: TreeNode) => s + n.area, 0)
      layoutRow(row, rowArea, rx, ry, rw, rh, horiz)
    }
  }

  squarify(nodes, x, y, w, h)
  return result
}

const TIME_TABS = ['24H', '7D', '30D', '3M']

export default function BloggerHeatmap() {
  const [timeTab, setTimeTab] = useState('7D')
  const [loading, setLoading] = useState(false)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; item: typeof MOCK_BLOGGERS[0] } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const obs = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight })
    })
    obs.observe(el)
    setSize({ w: el.clientWidth, h: el.clientHeight })
    return () => obs.disconnect()
  }, [])

  const cells = size.w > 0
    ? squarified(MOCK_BLOGGERS, 0, 0, size.w, size.h)
    : []

  const refresh = () => { setLoading(true); setTimeout(() => setLoading(false), 800) }

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-white mb-1">博主热力图</h1>
        <p className="text-gray-400 text-sm">方块大小 = 预测次数 · 颜色 = 准确率 · 绿色越深越准</p>
      </div>

      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="flex bg-[#111827] border border-[#1f2937] rounded-lg p-0.5">
          {TIME_TABS.map(t => (
            <button key={t} onClick={() => setTimeTab(t)} className={clsx(
              'px-3 py-1.5 rounded-md text-sm font-medium transition',
              timeTab === t ? 'bg-[#00d4aa] text-[#0a0e1a]' : 'text-gray-400 hover:text-white'
            )}>{t}</button>
          ))}
        </div>
        <button onClick={refresh} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[#1f2937] text-gray-400 hover:text-white text-sm transition">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />刷新
        </button>
        <div className="ml-auto flex items-center gap-4 text-xs text-gray-500">
          {[['#14532d','≥70%'],['#166534','60-70%'],['#713f12','50-60%'],['#7f1d1d','<50%']].map(([c,l]) => (
            <span key={l} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm inline-block" style={{background:c}}/>
              {l}
            </span>
          ))}
        </div>
      </div>

      {/* 主体：左侧榜单 + 右侧热力图 */}
      <div className="flex-1 min-h-0 flex gap-4">

        {/* 左侧面板 */}
        <div className="w-52 flex-shrink-0 flex flex-col gap-4">
          {/* 上升榜 */}
          <div className="flex-1 bg-[#0d1220] border border-[#1f2937] rounded-2xl p-4 flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[#4ade80] text-base">▲</span>
              <span className="text-white text-sm font-semibold">准确率上升</span>
            </div>
            <div className="text-xs text-gray-500 flex justify-between mb-2 px-1">
              <span>博主</span>
              <span className="flex gap-3"><span>1D</span><span>7D</span></span>
            </div>
            <div className="flex flex-col gap-1.5 overflow-auto">
              {[...MOCK_BLOGGERS]
                .filter(b => b.d7 > 0)
                .sort((a, b) => b.d7 - a.d7)
                .map(b => (
                  <div key={b.id} className="flex items-center justify-between px-1 py-1 rounded-lg hover:bg-[#1f2937] transition">
                    <span className="text-gray-300 text-xs truncate max-w-[80px]">{b.name}</span>
                    <span className="flex gap-3 text-xs">
                      <span className={b.d1 >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]'}>
                        {b.d1 >= 0 ? '+' : ''}{b.d1}%
                      </span>
                      <span className={b.d7 >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]'}>
                        {b.d7 >= 0 ? '+' : ''}{b.d7}%
                      </span>
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* 下降榜 */}
          <div className="flex-1 bg-[#0d1220] border border-[#1f2937] rounded-2xl p-4 flex flex-col">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[#f87171] text-base">▼</span>
              <span className="text-white text-sm font-semibold">准确率下降</span>
            </div>
            <div className="text-xs text-gray-500 flex justify-between mb-2 px-1">
              <span>博主</span>
              <span className="flex gap-3"><span>1D</span><span>7D</span></span>
            </div>
            <div className="flex flex-col gap-1.5 overflow-auto">
              {[...MOCK_BLOGGERS]
                .filter(b => b.d7 < 0)
                .sort((a, b) => a.d7 - b.d7)
                .map(b => (
                  <div key={b.id} className="flex items-center justify-between px-1 py-1 rounded-lg hover:bg-[#1f2937] transition">
                    <span className="text-gray-300 text-xs truncate max-w-[80px]">{b.name}</span>
                    <span className="flex gap-3 text-xs">
                      <span className={b.d1 >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]'}>
                        {b.d1 >= 0 ? '+' : ''}{b.d1}%
                      </span>
                      <span className={b.d7 >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]'}>
                        {b.d7 >= 0 ? '+' : ''}{b.d7}%
                      </span>
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
        {/* 右侧热力图 */}
        <div ref={containerRef} className="flex-1 min-h-0 bg-[#0d1220] rounded-2xl border border-[#1f2937] relative overflow-hidden">
          {size.w > 0 && (
            <svg width={size.w} height={size.h}>
              {cells.map(cell => {
                const bg = accuracyBg(cell.accuracy)
                const tc = accuracyText(cell.accuracy)
                const gap = 3
                const cx = cell.x + gap, cy = cell.y + gap
                const cw = cell.w - gap*2, ch = cell.h - gap*2
                if (cw < 4 || ch < 4) return null

                // 迷你折线
                const lw = Math.min(cw - 20, 60), lh = 16
                const mn = Math.min(...cell.trend), mx = Math.max(...cell.trend)
                const rng = mx - mn || 1
                const pts = cell.trend.map((v, i) => {
                  const px = cx + 8 + (i / (cell.trend.length - 1)) * lw
                  const py = cy + ch - 22 + lh - ((v - mn) / rng) * lh
                  return `${px.toFixed(1)},${py.toFixed(1)}`
                }).join(' ')

                return (
                  <g key={cell.id}
                    onMouseEnter={e => setTooltip({ x: e.clientX, y: e.clientY, item: cell })}
                    onMouseLeave={() => setTooltip(null)}
                    style={{ cursor: 'pointer' }}>
                    <rect x={cx} y={cy} width={cw} height={ch} fill={bg} rx={8} />
                    {cw > 55 && ch > 36 && (
                      <text x={cx+8} y={cy+20} fill="#fff"
                        fontSize={Math.min(13, cw/5)} fontWeight={600}
                        style={{pointerEvents:'none'}}>
                        {cell.name.length > 7 ? cell.name.slice(0,6)+'…' : cell.name}
                      </text>
                    )}
                    {cw > 55 && ch > 52 && (
                      <text x={cx+8} y={cy+36} fill={tc} fontSize={11}
                        style={{pointerEvents:'none'}}>
                        {cell.accuracy}% 准确率
                      </text>
                    )}
                    {cw > 55 && ch > 90 && (
                      <>
                        <polyline points={pts} fill="none" stroke={tc}
                          strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" opacity={0.7}/>
                        <text x={cx+cw-8} y={cy+ch-8} fill="#6b7280"
                          fontSize={10} textAnchor="end" style={{pointerEvents:'none'}}>
                          {cell.predictions}次
                        </text>
                      </>
                    )}
                  </g>
                )
              })}
            </svg>
          )}

        {tooltip && (
          <div className="fixed z-50 pointer-events-none bg-[#1f2937] border border-[#374151] rounded-xl p-3 text-sm shadow-2xl"
            style={{ left: tooltip.x + 14, top: tooltip.y - 10 }}>
            <p className="text-white font-semibold mb-2">{tooltip.item.name}</p>
            <p className="text-gray-400 mb-0.5">准确率 <span style={{color:accuracyText(tooltip.item.accuracy)}}>{tooltip.item.accuracy}%</span></p>
            <p className="text-gray-400 mb-0.5">预测次数 <span className="text-white">{tooltip.item.predictions}</span></p>
            <p className="text-gray-400">粉丝数 <span className="text-white">{(tooltip.item.followers/10000).toFixed(0)}万</span></p>
          </div>
        )}
        </div>
      </div>
    </div>
  )
}
