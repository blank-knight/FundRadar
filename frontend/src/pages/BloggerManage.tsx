import { useState } from 'react'
import { Search, Plus, Trash2, ExternalLink, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import clsx from 'clsx'

type Blogger = {
  id: number
  name: string
  platform: '雪球' | '微博' | '公众号'
  avatar: string
  accuracy: number
  predictions: number
  followers: number
  trend: 'up' | 'down' | 'flat'
  tags: string[]
  tracked: boolean
}

const MOCK_ALL: Blogger[] = [
  { id:1, name:'ETF拯救世界', platform:'雪球', avatar:'🎯', accuracy:71, predictions:89,  followers:120000, trend:'up',   tags:['ETF','指数'], tracked:true  },
  { id:2, name:'张坤',        platform:'雪球', avatar:'💎', accuracy:73, predictions:28,  followers:210000, trend:'up',   tags:['主动','价值'], tracked:true  },
  { id:3, name:'持有封基',    platform:'雪球', avatar:'📊', accuracy:68, predictions:56,  followers:85000,  trend:'up',   tags:['封基','债券'], tracked:true  },
  { id:4, name:'雪球基金',    platform:'雪球', avatar:'❄️', accuracy:55, predictions:120, followers:320000, trend:'down', tags:['综合'],       tracked:true  },
  { id:5, name:'但斌',        platform:'微博', avatar:'🍷', accuracy:62, predictions:34,  followers:480000, trend:'flat', tags:['价值','白酒'], tracked:true  },
  { id:6, name:'林园',        platform:'微博', avatar:'💊', accuracy:59, predictions:45,  followers:95000,  trend:'down', tags:['医药','价值'], tracked:true  },
  { id:7, name:'但斌助理',    platform:'雪球', avatar:'📉', accuracy:48, predictions:22,  followers:30000,  trend:'down', tags:['综合'],       tracked:false },
  { id:8, name:'价值投资者',  platform:'公众号',avatar:'📈', accuracy:66, predictions:38,  followers:55000,  trend:'up',   tags:['价值'],       tracked:false },
  { id:9, name:'指数基金定投',platform:'雪球', avatar:'📐', accuracy:64, predictions:51,  followers:78000,  trend:'up',   tags:['ETF','定投'], tracked:false },
  { id:10,name:'基金老司机',  platform:'公众号',avatar:'🚗', accuracy:61, predictions:67,  followers:140000, trend:'flat', tags:['综合','混合'], tracked:false },
]

const PLATFORMS = ['全部', '雪球', '微博', '公众号'] as const
const TAGS = ['全部', 'ETF', '指数', '价值', '医药', '白酒', '封基', '定投', '混合']

function AccuracyBadge({ acc }: { acc: number }) {
  const color = acc >= 70 ? 'text-[#4ade80]' : acc >= 60 ? 'text-[#86efac]' : acc >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]'
  return <span className={clsx('font-semibold text-sm', color)}>{acc}%</span>
}

function TrendIcon({ trend }: { trend: Blogger['trend'] }) {
  if (trend === 'up')   return <TrendingUp size={14} className="text-[#4ade80]" />
  if (trend === 'down') return <TrendingDown size={14} className="text-[#f87171]" />
  return <Minus size={14} className="text-gray-500" />
}

export default function BloggerManage() {
  const [bloggers, setBloggers] = useState(MOCK_ALL)
  const [query, setQuery] = useState('')
  const [platform, setPlatform] = useState<typeof PLATFORMS[number]>('全部')
  const [tag, setTag] = useState('全部')
  const [tab, setTab] = useState<'tracked' | 'all'>('tracked')

  const toggle = (id: number) => {
    setBloggers(prev => prev.map(b => b.id === id ? { ...b, tracked: !b.tracked } : b))
  }

  const filtered = bloggers.filter(b => {
    if (tab === 'tracked' && !b.tracked) return false
    if (query && !b.name.includes(query)) return false
    if (platform !== '全部' && b.platform !== platform) return false
    if (tag !== '全部' && !b.tags.includes(tag)) return false
    return true
  })

  const trackedCount = bloggers.filter(b => b.tracked).length

  return (
    <div className="p-3 md:p-6 h-full flex flex-col overflow-auto">
      {/* 标题 */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-white mb-1">博主管理</h1>
        <p className="text-gray-400 text-sm">追踪优质博主，系统自动抓取并评估其预测准确率</p>
      </div>

      {/* 统计 */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">追踪中</p>
          <p className="text-white text-2xl font-bold">{trackedCount}</p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">平均准确率</p>
          <p className="text-2xl font-bold">
            <AccuracyBadge acc={Math.round(bloggers.filter(b=>b.tracked).reduce((s,b)=>s+b.accuracy,0)/trackedCount)} />
          </p>
        </div>
        <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
          <p className="text-gray-400 text-xs mb-1">今日预测总数</p>
          <p className="text-white text-2xl font-bold">{bloggers.filter(b=>b.tracked).reduce((s,b)=>s+b.predictions,0)}</p>
        </div>
      </div>

      {/* tab + 搜索 */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        <div className="flex bg-[#111827] border border-[#1f2937] rounded-lg p-0.5">
          <button onClick={() => setTab('tracked')} className={clsx(
            'px-3 py-1.5 rounded-md text-sm font-medium transition',
            tab === 'tracked' ? 'bg-[#00d4aa] text-[#0a0e1a]' : 'text-gray-400 hover:text-white'
          )}>已追踪 {trackedCount}</button>
          <button onClick={() => setTab('all')} className={clsx(
            'px-3 py-1.5 rounded-md text-sm font-medium transition',
            tab === 'all' ? 'bg-[#00d4aa] text-[#0a0e1a]' : 'text-gray-400 hover:text-white'
          )}>发现博主</button>
        </div>
        <div className="flex-1 relative min-w-[180px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input value={query} onChange={e => setQuery(e.target.value)}
            placeholder="搜索博主名称..."
            className="w-full bg-[#111827] border border-[#1f2937] rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#00d4aa]" />
        </div>
      </div>

      {/* 平台 + 标签筛选 */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {PLATFORMS.map(p => (
          <button key={p} onClick={() => setPlatform(p)} className={clsx(
            'px-3 py-1 rounded-full text-xs font-medium border transition',
            platform === p
              ? 'bg-[#00d4aa] text-[#0a0e1a] border-[#00d4aa]'
              : 'text-gray-400 border-[#1f2937] hover:border-gray-500'
          )}>{p}</button>
        ))}
        <div className="w-px h-4 bg-[#1f2937] mx-1" />
        {TAGS.map(t => (
          <button key={t} onClick={() => setTag(t)} className={clsx(
            'px-3 py-1 rounded-full text-xs font-medium border transition',
            tag === t
              ? 'bg-[#1f2937] text-white border-[#374151]'
              : 'text-gray-500 border-[#1f2937] hover:text-gray-300'
          )}>{t}</button>
        ))}
      </div>

      {/* 博主列表 */}
      <div className="flex flex-col gap-2">
        {filtered.length === 0 && (
          <div className="text-center text-gray-500 py-12">没有找到匹配的博主</div>
        )}
        {filtered.map(b => (
          <div key={b.id} className="bg-[#0d1220] border border-[#1f2937] rounded-xl px-4 py-3 flex items-center gap-4 hover:border-[#374151] transition">
            {/* 头像 */}
            <div className="w-10 h-10 rounded-full bg-[#1f2937] flex items-center justify-center text-xl flex-shrink-0">
              {b.avatar}
            </div>

            {/* 名字 + 平台 + 标签 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-white font-semibold text-sm">{b.name}</span>
                <span className="text-xs text-gray-500 bg-[#1f2937] px-2 py-0.5 rounded-full">{b.platform}</span>
                {b.tags.map(t => (
                  <span key={t} className="text-xs text-[#00d4aa] bg-[#00d4aa]/10 px-2 py-0.5 rounded-full">{t}</span>
                ))}
              </div>
              <div className="flex items-center gap-3 text-xs text-gray-500">
                <span>{(b.followers/10000).toFixed(0)}万粉丝</span>
                <span>{b.predictions} 次预测</span>
              </div>
            </div>

            {/* 准确率 + 趋势 */}
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <TrendIcon trend={b.trend} />
              <AccuracyBadge acc={b.accuracy} />
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center gap-2 flex-shrink-0">
              <button className="p-1.5 text-gray-500 hover:text-gray-300 transition">
                <ExternalLink size={15} />
              </button>
              {b.tracked ? (
                <button onClick={() => toggle(b.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#1f2937] text-gray-300 hover:bg-[#7f1d1d] hover:text-[#f87171] text-xs font-medium transition">
                  <Trash2 size={13} />取消追踪
                </button>
              ) : (
                <button onClick={() => toggle(b.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#00d4aa]/10 text-[#00d4aa] hover:bg-[#00d4aa]/20 text-xs font-medium transition">
                  <Plus size={13} />追踪
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}