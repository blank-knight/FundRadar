import { useState } from 'react'
import { TrendingUp, TrendingDown, Star, Clock, Newspaper, Users, ChevronDown, ChevronUp, Globe, BarChart3, ExternalLink } from 'lucide-react'
import clsx from 'clsx'

// ─── Mock: 信号 ───
type Signal = {
  id: number
  direction: 'bull' | 'bear'
  fundName: string
  fundCode: string
  blogger: { name: string; accuracy: number; avatar: string }
  confidence: number
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

// ─── Mock: 新闻 ───
type NewsItem = {
  id: number
  source: 'eastmoney' | 'eastmoney_fund'
  title: string
  url: string
  publishTime: string
  sentimentScore: number | null  // -1~1, null=未分析
  sentimentLabel: 'positive' | 'negative' | 'neutral' | null
  summary?: string
}

const MOCK_NEWS: NewsItem[] = [
  { id: 170, source: 'eastmoney', title: '文远知行：计划在瑞士苏黎世推出商业化Robotaxi服务',
    url: 'https://fund.eastmoney.com/a/202606173774495418.html', publishTime: '10:22', sentimentScore: 0.70, sentimentLabel: 'positive',
    summary: '文远知行WeRide宣布计划在瑞士苏黎世推出商业化Robotaxi自动驾驶出租车服务，加速欧洲市场布局。' },
  { id: 169, source: 'eastmoney', title: '福特汽车公司宣布召回44,963辆美国境内车辆',
    url: 'https://fund.eastmoney.com/a/202606173774497687.html', publishTime: '09:55', sentimentScore: -0.50, sentimentLabel: 'negative',
    summary: '福特汽车宣布因安全隐患召回近4.5万辆美国境内车辆，涉及多个车型。' },
  { id: 168, source: 'eastmoney', title: '捷捷微电：目前公司订单饱满 各产品线均保持较高的产能利用率',
    url: 'https://fund.eastmoney.com/a/202606173774501010.html', publishTime: '09:30', sentimentScore: 0.50, sentimentLabel: 'positive',
    summary: '捷捷微电在互动平台表示，目前公司订单饱满，各产品线均保持较高的产能利用率，经营情况良好。' },
  { id: 167, source: 'eastmoney', title: '海得控制：目前尚未在CPO封装领域布局',
    url: 'https://fund.eastmoney.com/a/202606173774499889.html', publishTime: '09:10', sentimentScore: 0.00, sentimentLabel: 'neutral',
    summary: '海得控制在互动平台回应投资者提问，表示公司目前尚未在CPO封装领域进行布局。' },
  { id: 166, source: 'eastmoney', title: '丰元股份旗下锂能科技公司增资至14.74亿 增幅约20%',
    url: 'https://fund.eastmoney.com/a/202606173774501219.html', publishTime: '10:45', sentimentScore: 0.70, sentimentLabel: 'positive',
    summary: '丰元股份旗下锂能科技公司注册资本增至14.74亿元，增幅约20%，显示股东对锂电业务前景看好。' },
  { id: 165, source: 'eastmoney', title: '海光信息DCU率先完成GLM-5.2 Day-0适配',
    url: 'https://fund.eastmoney.com/a/202606173774498883.html', publishTime: '08:30', sentimentScore: 0.80, sentimentLabel: 'positive',
    summary: '海光信息宣布其DCU加速卡率先完成对智谱GLM-5.2大模型的Day-0适配，国产AI算力生态持续完善。' },
  { id: 164, source: 'eastmoney', title: '阿里云新增巴黎、柔佛地域 扩建日本、墨西哥数据中心',
    url: 'https://fund.eastmoney.com/a/202606173774502678.html', publishTime: '11:08', sentimentScore: 0.70, sentimentLabel: 'positive',
    summary: '阿里云宣布新增巴黎和柔佛两个地域，同时扩建日本和墨西哥数据中心，全球基础设施持续扩张。' },
  { id: 163, source: 'eastmoney', title: '上纬新材旗下启元机器人将在深圳开设亚洲首家线下门店',
    url: 'https://fund.eastmoney.com/a/202606173774502460.html', publishTime: '13:00', sentimentScore: 0.50, sentimentLabel: 'positive',
    summary: '上纬新材旗下启元机器人宣布将在深圳开设亚洲首家线下门店，加速机器人产品商业化落地。' },
  { id: 190, source: 'eastmoney_fund', title: '智谱GLM-5.2上线京东云',
    url: 'https://fund.eastmoney.com/a/202606173774611532.html', publishTime: '15:20', sentimentScore: null, sentimentLabel: null },
  { id: 181, source: 'eastmoney_fund', title: '小米公司：西安警方侦破使用AI造谣我司刑案 4人被刑拘',
    url: 'https://fund.eastmoney.com/a/202606173774641662.html', publishTime: '14:00', sentimentScore: null, sentimentLabel: null },
]

// ─── Mock: 博主帖子 ───
type PredictionItem = {
  id: number
  platform: 'weibo' | 'eastmoney_analyst'
  username: string
  avatar: string
  postTime: string
  postContent: string
  postUrl?: string
  predictedDirection: 'bullish' | 'bearish' | 'neutral' | null
  confidence: number | null
  isPrediction: boolean
  rawExtra?: string  // 分析师额外信息
}

const MOCK_PREDICTIONS: PredictionItem[] = [
  { id: 1, platform: 'eastmoney_analyst', username: '宇之光-国元证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【宇之光(国元证券)】最新评级: 盛科通信(688702) — 买入',
    postUrl: 'em_analyst://11000470931/688702',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 369.06% | 排名 #1' },
  { id: 2, platform: 'eastmoney_analyst', username: '魏鹏程-中信证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【魏鹏程(中信证券)】最新评级: 新易盛(300502) — 买入',
    postUrl: 'em_analyst://11000423631/300502',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 269.43% | 排名 #2' },
  { id: 3, platform: 'eastmoney_analyst', username: '宫帅-广发证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【宫帅(广发证券)】最新评级: 大中矿业(001203) — 增持',
    postUrl: 'em_analyst://11000276336/001203',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 186.51% | 排名 #3' },
  { id: 4, platform: 'eastmoney_analyst', username: '唐凯-东北证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【唐凯(东北证券)】最新评级: 恒盛能源(605580) — 买入',
    postUrl: 'em_analyst://11000252335/605580',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 179.89% | 排名 #4' },
  { id: 5, platform: 'eastmoney_analyst', username: '王文瑞-湘财证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【王文瑞(湘财证券)】最新评级: 兆易创新(603986) — 增持',
    postUrl: 'em_analyst://11000435034/603986',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 179.86% | 排名 #5' },
  { id: 6, platform: 'eastmoney_analyst', username: '刘京昭-上海证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【刘京昭(上海证券)】最新评级: 中际旭创(300308)',
    postUrl: 'em_analyst://11000396132/300308',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 133.07% | 排名 #10' },
  { id: 7, platform: 'eastmoney_analyst', username: '黎江涛-华鑫证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【黎江涛(华鑫证券)】最新评级: 新宙邦(300037)',
    postUrl: 'em_analyst://11000264733/300037',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 124.99% | 排名 #13' },
  { id: 8, platform: 'eastmoney_analyst', username: '杨天薇-招银国际', avatar: '🏛️', postTime: '15:35',
    postContent: '【杨天薇(招银国际)】最新评级: 中际旭创(300308)',
    postUrl: 'em_analyst://11000359033/300308',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 114.24% | 排名 #17' },
  { id: 9, platform: 'eastmoney_analyst', username: '傅鸿浩-华鑫证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【傅鸿浩(华鑫证券)】最新评级: 海鸥股份(603269)',
    postUrl: 'em_analyst://11000253763/603269',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 112.99% | 排名 #18' },
  { id: 10, platform: 'eastmoney_analyst', username: '张航-国盛证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【张航(国盛证券)】最新评级: 索通发展(603612)',
    postUrl: 'em_analyst://11000375033/603612',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 112.20% | 排名 #19' },
  { id: 11, platform: 'eastmoney_analyst', username: '王保庆-华福证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【王保庆(华福证券)】最新评级: 天齐锂业(002466)',
    postUrl: 'em_analyst://11000237635/002466',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 110.25% | 排名 #20' },
  { id: 12, platform: 'eastmoney_analyst', username: '华立-中国银河', avatar: '🏛️', postTime: '15:35',
    postContent: '【华立(中国银河)】最新评级: 藏格矿业(000408)',
    postUrl: 'em_analyst://11000249940/000408',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 107.71% | 排名 #22' },
  { id: 13, platform: 'eastmoney_analyst', username: '丁士涛-国联民生', avatar: '🏛️', postTime: '15:35',
    postContent: '【丁士涛(国联民生)】最新评级: 盐湖股份(000792)',
    postUrl: 'em_analyst://11000178766/000792',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 106.00% | 排名 #23' },
  { id: 14, platform: 'eastmoney_analyst', username: '孙二春-开源证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【孙二春(开源证券)】最新评级: 云铝股份(000807)',
    postUrl: 'em_analyst://11000393435/000807',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 104.94% | 排名 #26' },
  { id: 15, platform: 'eastmoney_analyst', username: '彭棋-华龙证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【彭棋(华龙证券)】最新评级: 中国巨石(600176)',
    postUrl: 'em_analyst://11000378545/600176',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 104.45% | 排名 #27' },
  { id: 16, platform: 'eastmoney_analyst', username: '许勇其-华安证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【许勇其(华安证券)】最新评级: 腾远钴业(301219)',
    postUrl: 'em_analyst://11000342542/301219',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 103.92% | 排名 #29' },
  { id: 17, platform: 'eastmoney_analyst', username: '宋嘉吉-国盛证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【宋嘉吉(国盛证券)】最新评级: 东阳光(600673)',
    postUrl: 'em_analyst://11000177081/600673',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 103.26% | 排名 #30' },
  { id: 18, platform: 'eastmoney_analyst', username: '李国盛-申万宏源', avatar: '🏛️', postTime: '15:35',
    postContent: '【李国盛(申万宏源)】最新评级: 锐捷网络(301165)',
    postUrl: 'em_analyst://11000332332/301165',
    predictedDirection: 'bullish', confidence: 1.0, isPrediction: true,
    rawExtra: '年度收益率 100.35% | 排名 #32' },
  { id: 19, platform: 'eastmoney_analyst', username: '张真桢-国金证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【张真桢(国金证券)】最新评级: 广和通(300638)',
    postUrl: 'em_analyst://11000323532/300638',
    predictedDirection: 'bullish', confidence: 0.97, isPrediction: true,
    rawExtra: '年度收益率 96.51% | 排名 #34' },
  { id: 20, platform: 'eastmoney_analyst', username: '蒋颖-开源证券', avatar: '🏛️', postTime: '15:35',
    postContent: '【蒋颖(开源证券)】最新评级: 大位科技(600589)',
    postUrl: 'em_analyst://11000300437/600589',
    predictedDirection: 'bullish', confidence: 0.95, isPrediction: true,
    rawExtra: '年度收益率 94.51% | 排名 #36' },
]

// ─── Mock: 信号维度评分 ───
const MOCK_DIMENSIONS = {
  blogger: { score: 1.0, label: '博主共识', count: 5 },
  news: { score: 0.40, label: '新闻情绪', count: 47 },
  retail: { score: -0.19, label: '散户情绪', count: 2 },
  fundFlow: { score: -0.81, label: '资金面', count: 1 },
  industry: { score: null, label: '行业动能', count: 0 },
}

// ─── Components ───

const FILTERS = ['全部', '看多', '看空'] as const
const SORTS = [
  { label: '置信度', key: 'confidence' },
  { label: '准确率', key: 'accuracy' },
  { label: '时间', key: 'time' },
] as const

type SourceTab = 'news' | 'bloggers'

function SentimentBadge({ score, label }: { score: number | null; label: string | null }) {
  if (!label || score === null) {
    return <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-400">待分析</span>
  }
  const colorMap: Record<string, string> = {
    positive: 'bg-green-900/50 text-green-400 border-green-800',
    negative: 'bg-red-900/50 text-red-400 border-red-800',
    neutral: 'bg-gray-700/50 text-gray-300 border-gray-600',
  }
  return (
    <span className={clsx('text-xs px-2 py-0.5 rounded border', colorMap[label])}>
      {score > 0 ? '+' : ''}{score.toFixed(2)}
    </span>
  )
}

function PlatformBadge({ platform }: { platform: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    weibo: { label: '微博', cls: 'bg-red-900/40 text-red-300 border-red-800/50' },
    eastmoney_analyst: { label: '东财', cls: 'bg-orange-900/40 text-orange-300 border-orange-800/50' },
  }
  const info = map[platform] || { label: platform, cls: 'bg-gray-700 text-gray-300' }
  return <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border font-medium', info.cls)}>{info.label}</span>
}

function DirectionIcon({ direction }: { direction: 'bullish' | 'bearish' | 'neutral' | null }) {
  if (direction === 'bullish') return <TrendingUp size={16} className="text-green-400" />
  if (direction === 'bearish') return <TrendingDown size={16} className="text-red-400" />
  return <div className="w-4 h-4 rounded-full bg-gray-600" />
}

function ScoreBar({ score, label, count, maxW = 'max-w-[80px]' }: { score: number | null; label: string; count: number; maxW?: string }) {
  const pct = score !== null ? Math.abs(score) * 100 : 0
  const color = score === null ? 'bg-gray-600'
    : score > 0.3 ? 'bg-green-500'
    : score > 0 ? 'bg-green-600'
    : score < -0.3 ? 'bg-red-500'
    : 'bg-red-600'

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 w-14 shrink-0">{label}</span>
      <div className={clsx('flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden', maxW)}>
        <div className={clsx('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-xs font-mono w-10 text-right shrink-0',
        score === null ? 'text-gray-600' : score > 0 ? 'text-green-400' : 'text-red-400'
      )}>
        {score !== null ? (score > 0 ? '+' : '') + score.toFixed(2) : 'N/A'}
      </span>
    </div>
  )
}

export default function TodaySignals() {
  const [filter, setFilter] = useState<typeof FILTERS[number]>('全部')
  const [sort, setSort] = useState<typeof SORTS[number]['key']>('confidence')
  const [sourceTab, setSourceTab] = useState<SourceTab>('news')
  const [sourceExpanded, setSourceExpanded] = useState(true)

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

  const analyzedNews = MOCK_NEWS.filter(n => n.sentimentScore !== null).length
  const bullishBloggers = MOCK_PREDICTIONS.filter(p => p.predictedDirection === 'bullish').length

  return (
    <div className="p-6 flex flex-col min-h-0 overflow-auto">
      {/* ── 1. 信号总览 ── */}
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

      {/* ── 2. 信号维度评分 ── */}
      <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4 mb-5">
        <h3 className="text-gray-300 text-sm font-medium mb-3 flex items-center gap-2">
          <BarChart3 size={14} className="text-[#00d4aa]" />
          信号维度评分
        </h3>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {Object.entries(MOCK_DIMENSIONS).map(([, v]) => (
            <ScoreBar key={v.label} score={v.score} label={v.label} count={v.count} />
          ))}
        </div>
      </div>

      {/* ── 3. 数据源面板 ── */}
      <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl overflow-hidden mb-5">
        {/* 标题栏 */}
        <button
          onClick={() => setSourceExpanded(!sourceExpanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition"
        >
          <div className="flex items-center gap-3">
            <Globe size={16} className="text-[#00d4aa]" />
            <span className="text-white text-sm font-medium">数据溯源</span>
            <span className="text-gray-500 text-xs">
              新闻 {analyzedNews}/{MOCK_NEWS.length} 已分析
              <span className="mx-2 text-gray-700">|</span>
              博主 {bullishBloggers} 看多 / {MOCK_PREDICTIONS.length} 条
            </span>
          </div>
          {sourceExpanded ? <ChevronUp size={16} className="text-gray-500" /> : <ChevronDown size={16} className="text-gray-500" />}
        </button>

        {sourceExpanded && (
          <>
            {/* Tab切换 */}
            <div className="flex border-t border-[#1f2937]">
              <button
                onClick={() => setSourceTab('news')}
                className={clsx(
                  'flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition border-b-2',
                  sourceTab === 'news'
                    ? 'text-[#00d4aa] border-[#00d4aa] bg-[#00d4aa08]'
                    : 'text-gray-400 border-transparent hover:text-gray-200'
                )}
              >
                <Newspaper size={14} />
                新闻 ({MOCK_NEWS.length})
              </button>
              <button
                onClick={() => setSourceTab('bloggers')}
                className={clsx(
                  'flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition border-b-2',
                  sourceTab === 'bloggers'
                    ? 'text-[#00d4aa] border-[#00d4aa] bg-[#00d4aa08]'
                    : 'text-gray-400 border-transparent hover:text-gray-200'
                )}
              >
                <Users size={14} />
                博主动态 ({MOCK_PREDICTIONS.length})
              </button>
            </div>

            {/* 新闻列表 */}
            {sourceTab === 'news' && (
              <div className="min-h-[200px] max-h-[50vh] overflow-y-auto divide-y divide-[#1f2937]/50">
                {MOCK_NEWS.map(n => (
                  <div key={n.id} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition">
                    <span className="text-gray-500 text-xs font-mono mt-0.5 shrink-0 w-10">{n.publishTime}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={clsx(
                          'text-[10px] px-1.5 py-0.5 rounded border',
                          n.source === 'eastmoney' ? 'bg-blue-900/30 text-blue-300 border-blue-800/40' : 'bg-purple-900/30 text-purple-300 border-purple-800/40'
                        )}>
                          {n.source === 'eastmoney' ? '东财' : '基金'}
                        </span>
                        <SentimentBadge score={n.sentimentScore} label={n.sentimentLabel} />
                      </div>
                      {n.url.startsWith('http') ? (
                        <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-gray-200 text-sm leading-snug mb-1 hover:text-[#00d4aa] transition inline-flex items-center gap-1">
                          {n.title}
                          <ExternalLink size={12} className="text-gray-600 shrink-0" />
                        </a>
                      ) : (
                        <p className="text-gray-200 text-sm leading-snug mb-1">{n.title}</p>
                      )}
                      {n.summary && (
                        <p className="text-gray-500 text-xs leading-relaxed line-clamp-2">{n.summary}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* 博主帖子列表 */}
            {sourceTab === 'bloggers' && (
              <div className="min-h-[200px] max-h-[50vh] overflow-y-auto divide-y divide-[#1f2937]/50">
                {MOCK_PREDICTIONS.map(p => (
                  <div key={p.id} className="flex items-start gap-3 px-4 py-3 hover:bg-white/[0.03] transition">
                    <span className="text-gray-500 text-xs font-mono mt-0.5 shrink-0 w-10">{p.postTime}</span>
                    <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
                      <span className="text-base">{p.avatar}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-white text-sm font-medium">{p.username}</span>
                        <PlatformBadge platform={p.platform} />
                        {p.isPrediction && p.predictedDirection && (
                          <div className="flex items-center gap-1">
                            <DirectionIcon direction={p.predictedDirection} />
                            <span className={clsx('text-[10px]',
                              p.predictedDirection === 'bullish' ? 'text-green-400' : p.predictedDirection === 'bearish' ? 'text-red-400' : 'text-gray-400'
                            )}>
                              {p.predictedDirection === 'bullish' ? '看多' : p.predictedDirection === 'bearish' ? '看空' : '中性'}
                            </span>
                          </div>
                        )}
                      </div>
                      <p className="text-gray-300 text-sm leading-snug">{p.postContent}</p>
                      {p.rawExtra && (
                        <p className="text-gray-500 text-xs mt-1">{p.rawExtra}</p>
                      )}
                      {p.postUrl && (
                        (() => {
                          let realUrl = null
                          if (p.postUrl.startsWith('http')) {
                            realUrl = p.postUrl
                          } else if (p.postUrl.startsWith('em_analyst://')) {
                            const analystId = p.postUrl.split('//')[1]?.split('/')[0]
                            if (analystId) {
                              realUrl = `https://data.eastmoney.com/invest/invest/${analystId}.html`
                            }
                          }
                          if (!realUrl) return null
                          return (
                            <a href={realUrl} target="_blank" rel="noopener noreferrer"
                               className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-[#00d4aa] mt-1 transition">
                              <ExternalLink size={11} /> 分析师主页
                            </a>
                          )
                        })()
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* ── 4. 筛选 + 排序 ── */}
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

      {/* ── 5. 信号卡片流 ── */}
      <div className="flex flex-col gap-3">
        {sorted.map(sig => (
          <div key={sig.id} className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4 hover:border-[#374151] transition flex items-center gap-4">
            <div className={clsx(
              'w-12 h-12 rounded-full flex items-center justify-center flex-shrink-0',
              sig.direction === 'bull' ? 'bg-[#14532d]' : 'bg-[#7f1d1d]'
            )}>
              {sig.direction === 'bull'
                ? <TrendingUp size={24} className="text-[#4ade80]" />
                : <TrendingDown size={24} className="text-[#f87171]" />
              }
            </div>
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
