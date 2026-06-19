import { useState } from 'react'
import { ChevronDown, ChevronRight, BookOpen, Lightbulb, AlertTriangle, CheckCircle } from 'lucide-react'
import clsx from 'clsx'

type Lesson = {
  id: string
  title: string
  tag: '基础' | '进阶' | '策略' | '风险'
  duration: string
  sections: { heading: string; content: string }[]
}

const LESSONS: Lesson[] = [
  {
    id: 'what-is-fund',
    title: '基金是什么？和股票有什么区别',
    tag: '基础', duration: '3 分钟',
    sections: [
      { heading: '基金的本质',
        content: '基金是把很多人的钱汇集在一起，交给专业基金经理统一投资的工具。你买基金，相当于买了一篮子股票/债券的份额，风险比单买一只股票分散得多。' },
      { heading: '和股票的核心区别',
        content: '股票是你直接持有某家公司的股权，涨跌完全跟着这家公司走。基金是间接持有，基金经理帮你选股，你只需要选对基金经理或指数。新手更适合从基金入手，门槛低、风险分散。' },
      { heading: '场内 vs 场外',
        content: '场外基金在支付宝/天天基金等平台买，按每天收盘后的净值成交，适合长期定投。场内ETF在股票账户买卖，实时交易，价格随市场波动，适合有一定经验后再玩。' },
    ]
  },
  {
    id: 'nav-explained',
    title: '净值、份额、收益怎么算',
    tag: '基础', duration: '4 分钟',
    sections: [
      { heading: '净值是什么',
        content: '净值（NAV）= 基金总资产 / 总份额。比如基金总资产 1 亿，总份额 5000 万份，净值就是 2.00 元。净值每天收盘后更新一次。' },
      { heading: '你的收益怎么算',
        content: '收益 = (当前净值 - 买入净值) / 买入净值 × 100%。比如你在净值 1.50 时买入，现在净值 1.80，收益率 = (1.80-1.50)/1.50 = 20%。持仓金额 = 份额 × 当前净值。' },
      { heading: '分红的影响',
        content: '基金分红后净值会下降，但你的总资产不变（分红直接打到你账户）。所以看到净值突然跌别慌，先确认是不是分红导致的。' },
    ]
  },
  {
    id: 'index-fund',
    title: '指数基金：新手最推荐的入门品种',
    tag: '基础', duration: '5 分钟',
    sections: [
      { heading: '为什么推荐指数基金',
        content: '指数基金跟踪某个指数（如沪深300、纳斯达克100），不依赖基金经理的主观判断，费率低，长期来看跑赢大多数主动基金。巴菲特也推荐普通人买指数基金。' },
      { heading: '常见指数介绍',
        content: '沪深300：A股最大的300家公司，代表中国经济整体。中证500：中等规模公司，弹性更大。纳斯达克100：美国科技巨头（苹果、微软、英伟达等），适合看好美国科技的人。' },
      { heading: '怎么判断现在贵不贵',
        content: '看PE（市盈率）。PE越低说明越便宜。沪深300 PE历史均值约12倍，低于10倍可以考虑加仓，高于15倍要谨慎。可以在中证指数官网或集思录查到实时PE。' },
    ]
  },
  {
    id: 'dollar-cost',
    title: '定投策略：用时间换空间',
    tag: '策略', duration: '4 分钟',
    sections: [
      { heading: '什么是定投',
        content: '定投就是每隔固定时间（每周/每月）买入固定金额的基金，不管市场涨跌都坚持买。核心逻辑：跌的时候买得多，涨的时候买得少，长期摊低成本。' },
      { heading: '定投的正确姿势',
        content: '选波动大的品种（指数基金比债券基金更适合定投）。坚持至少1-2年，中途不要因为亏损就停止——亏损时正是买便宜货的时候。设定止盈目标，比如收益达到20%就分批卖出。' },
      { heading: '定投不是万能的',
        content: '如果市场长期单边下跌（比如日本失去的30年），定投也会亏。所以要选有长期增长逻辑的市场，A股和美股都有这个逻辑，但要做好持有3-5年的心理准备。' },
    ]
  },
  {
    id: 'risk-control',
    title: '风险控制：新手最容易踩的坑',
    tag: '风险', duration: '5 分钟',
    sections: [
      { heading: '不要把所有钱都投进去',
        content: '只用"闲钱"投资——3-6个月生活费要留着，不能动的钱（买房首付、应急备用金）绝对不能投。投资亏损是正常的，但不能影响正常生活。' },
      { heading: '不要追涨杀跌',
        content: '看到某只基金涨了30%才去买，往往是在高点接盘。看到亏了10%就割肉，往往是在低点卖出。散户亏钱的主要原因就是情绪化操作。' },
      { heading: '不要重仓单一品种',
        content: '哪怕再看好某只基金，单只仓位不要超过总投资的30%。分散投资不是因为你不相信它，而是因为你无法预测未来。' },
    ]
  },
  {
    id: 'read-signals',
    title: '怎么看懂本站的博主信号',
    tag: '进阶', duration: '3 分钟',
    sections: [
      { heading: '信号只是参考，不是指令',
        content: '博主的预测准确率即使是70%，也意味着30%的时候是错的。本站的信号是帮你做参考，最终决策还是你自己的。不要看到"看多"就全仓冲进去。' },
      { heading: '怎么用准确率筛选',
        content: '优先参考准确率≥65%、预测次数≥30次的博主。预测次数太少（<10次）的准确率参考价值不大，可能只是运气好。多个高准确率博主同时看多，信号更可靠。' },
      { heading: '结合自己的持仓看',
        content: '在"我的持仓"页面，每只基金旁边会显示今日博主信号。如果你持有的基金被多个博主看空，可以考虑减仓或观望，但不要因为一个博主看空就立刻卖出。' },
    ]
  },
]

const TAG_COLORS = {
  '基础': 'text-[#60a5fa] bg-[#1e3a5f]/60',
  '进阶': 'text-[#a78bfa] bg-[#4c1d95]/40',
  '策略': 'text-[#4ade80] bg-[#14532d]/40',
  '风险': 'text-[#f87171] bg-[#7f1d1d]/40',
}

function LessonCard({ lesson }: { lesson: Lesson }) {
  const [open, setOpen] = useState(false)
  const [activeSection, setActiveSection] = useState(0)

  return (
    <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl overflow-hidden hover:border-[#374151] transition">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-4 px-5 py-4 text-left">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={clsx('text-xs px-2 py-0.5 rounded-full font-medium', TAG_COLORS[lesson.tag])}>{lesson.tag}</span>
            <span className="text-gray-500 text-xs">{lesson.duration}</span>
          </div>
          <h3 className="text-white font-semibold text-sm">{lesson.title}</h3>
        </div>
        {open ? <ChevronDown size={16} className="text-gray-400 shrink-0" /> : <ChevronRight size={16} className="text-gray-400 shrink-0" />}
      </button>

      {open && (
        <div className="border-t border-[#1f2937] flex">
          {/* 左侧章节导航 */}
          <div className="w-40 shrink-0 border-r border-[#1f2937] py-3">
            {lesson.sections.map((s, i) => (
              <button key={i} onClick={() => setActiveSection(i)}
                className={clsx('w-full text-left px-4 py-2 text-xs transition',
                  activeSection === i ? 'text-[#00d4aa] bg-[#00d4aa]/5' : 'text-gray-500 hover:text-gray-300'
                )}>
                {s.heading}
              </button>
            ))}
          </div>
          {/* 右侧内容 */}
          <div className="flex-1 p-5">
            <h4 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Lightbulb size={15} className="text-[#fbbf24]" />
              {lesson.sections[activeSection].heading}
            </h4>
            <p className="text-gray-300 text-sm leading-relaxed">
              {lesson.sections[activeSection].content}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function LearnPage() {
  const [filter, setFilter] = useState<'全部' | Lesson['tag']>('全部')
  const tags = ['全部', '基础', '策略', '进阶', '风险'] as const

  const filtered = LESSONS.filter(l => filter === '全部' || l.tag === filter)

  return (
    <div className="p-6 h-full flex flex-col overflow-auto">
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-white mb-1">新手教学</h1>
        <p className="text-gray-400 text-sm">从零开始学基金，每篇 3-5 分钟，看完就能上手</p>
      </div>

      {/* 进度提示 */}
      <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4 mb-5 flex items-center gap-4">
        <CheckCircle size={20} className="text-[#00d4aa] shrink-0" />
        <div className="flex-1">
          <p className="text-white text-sm font-medium">建议学习顺序：基础 → 策略 → 进阶 → 风险</p>
          <p className="text-gray-500 text-xs mt-0.5">先搞懂基础概念，再学操作策略，最后了解风险控制</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[#00d4aa] font-bold">{LESSONS.length}</p>
          <p className="text-gray-500 text-xs">篇文章</p>
        </div>
      </div>

      {/* 标签筛选 */}
      <div className="flex items-center gap-2 mb-4">
        <BookOpen size={14} className="text-gray-500" />
        {tags.map(t => (
          <button key={t} onClick={() => setFilter(t)} className={clsx(
            'px-3 py-1 rounded-full text-xs font-medium border transition',
            filter === t
              ? 'bg-[#00d4aa] text-[#0a0e1a] border-[#00d4aa]'
              : 'text-gray-400 border-[#1f2937] hover:border-gray-500'
          )}>{t}</button>
        ))}
      </div>

      {/* 文章列表 */}
      <div className="flex flex-col gap-3">
        {filtered.map(l => <LessonCard key={l.id} lesson={l} />)}
      </div>

      {/* 底部提示 */}
      <div className="mt-6 bg-[#0d1220] border border-[#fbbf24]/20 rounded-xl p-4 flex items-start gap-3">
        <AlertTriangle size={16} className="text-[#fbbf24] shrink-0 mt-0.5" />
        <p className="text-gray-400 text-xs leading-relaxed">
          本站内容仅供学习参考，不构成投资建议。基金投资有风险，过往业绩不代表未来表现。请根据自身风险承受能力做出投资决策。
        </p>
      </div>
    </div>
  )
}
