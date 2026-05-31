import { useState, useRef, useEffect } from 'react'
import { Send, Plus, Trash2, Bot, User, Sparkles } from 'lucide-react'
import clsx from 'clsx'

type Message = { role: 'user' | 'ai'; content: string; time: string }
type Review = { id: number; title: string; date: string; preview: string; messages: Message[] }

const now = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
const today = () => new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })

const INIT_REVIEWS: Review[] = [
  {
    id: 1, title: '5月第三周复盘', date: '2026-05-21',
    preview: '本周沪深300下跌1.2%，持仓整体跑赢大盘...',
    messages: [
      { role: 'user', content: '帮我复盘一下本周操作：周一加仓了沪深300ETF 2000元，周四白酒基金跌了3%没动，周五ETF拯救世界发出看多信号我没跟。', time: '09:15' },
      { role: 'ai', content: '本周操作整体偏稳健，有几点值得分析：\n\n**✅ 做对的地方**\n周一加仓沪深300ETF时机不错，当时PE约11倍，处于历史低位区间，符合"低估值加仓"的逻辑。\n\n**🤔 可以思考的地方**\n白酒基金跌3%没动——这个决策本身没问题，但需要明确你的理由是什么？是因为看好长期逻辑，还是只是不想亏损卖出？前者是策略，后者是情绪。\n\n**📌 关于ETF拯救世界的信号**\n没跟信号不一定是错的。他的7日准确率71%，意味着约30%的概率是错的。建议下次记录一下：当时为什么没跟？是有其他判断，还是犹豫了？复盘的价值就在这里。', time: '09:16' },
    ]
  },
]

const PROMPTS = [
  '帮我分析本周持仓表现',
  '我今天买入了XXX，帮我复盘决策逻辑',
  '为什么我总是追涨杀跌？',
  '帮我制定下周操作计划',
]

// 模拟 AI 回复
function mockAiReply(userMsg: string): string {
  if (userMsg.includes('追涨杀跌')) {
    return '追涨杀跌是人类大脑的默认模式，不是你的问题，是进化的结果。\n\n**根本原因：**\n大脑把"价格上涨"解读为"安全信号"，把"价格下跌"解读为"危险信号"。这在原始社会很有用，但在投资里完全反过来了。\n\n**实用的破解方法：**\n1. 买入前写下理由，不是"它在涨"，而是"PE低于历史均值X%"\n2. 设定机械规则：跌X%加仓，涨X%减仓，不允许情绪覆盖规则\n3. 复盘时专门记录"情绪驱动的操作"，看看结果如何\n\n你最近一次追涨杀跌是什么时候？说说具体情况，我帮你分析。'
  }
  if (userMsg.includes('计划') || userMsg.includes('下周')) {
    return '制定操作计划需要几个维度：\n\n**1. 市场判断**\n当前沪深300 PE约11.5倍，处于历史中低位，整体不贵。但短期情绪偏弱，不建议大幅加仓。\n\n**2. 建议操作框架**\n- 定投计划：按原计划执行，不因短期涨跌调整金额\n- 加仓条件：如果沪深300再跌3%以上，可以考虑额外加仓\n- 止盈条件：持仓收益超过15%，分批减仓1/3\n\n**3. 需要你告诉我的**\n你目前的仓位比例是多少？还有多少闲钱可以投？这样我能给更具体的建议。'
  }
  return '收到你的复盘内容。\n\n**我的分析：**\n你描述的操作有几个值得深入思考的点。投资决策的质量不只看结果，更要看决策时的逻辑是否清晰。\n\n**建议你回答这几个问题：**\n1. 这次操作的核心理由是什么？\n2. 如果结果相反，你会怎么解释？\n3. 下次遇到类似情况，你会怎么做？\n\n把这些写下来，复盘的价值才能真正体现出来。'
}

export default function ReviewPage() {
  const [reviews, setReviews] = useState(INIT_REVIEWS)
  const [activeId, setActiveId] = useState(1)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const active = reviews.find(r => r.id === activeId)!

  const sendMessage = () => {
    if (!input.trim() || loading) return
    const userMsg: Message = { role: 'user', content: input.trim(), time: now() }
    const updated = reviews.map(r => r.id === activeId
      ? { ...r, messages: [...r.messages, userMsg], preview: input.trim().slice(0, 30) + '...' }
      : r
    )
    setReviews(updated)
    setInput('')
    setLoading(true)
    setTimeout(() => {
      const aiMsg: Message = { role: 'ai', content: mockAiReply(userMsg.content), time: now() }
      setReviews(prev => prev.map(r => r.id === activeId
        ? { ...r, messages: [...r.messages, aiMsg] }
        : r
      ))
      setLoading(false)
    }, 900)
  }

  const newReview = () => {
    const id = Date.now()
    const r: Review = { id, title: `${today()}复盘`, date: new Date().toISOString().slice(0,10), preview: '新建复盘...', messages: [] }
    setReviews(prev => [r, ...prev])
    setActiveId(id)
  }

  const deleteReview = (id: number) => {
    const rest = reviews.filter(r => r.id !== id)
    setReviews(rest)
    if (activeId === id) setActiveId(rest[0]?.id ?? 0)
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [active?.messages.length, loading])

  return (
    <div className="h-full flex overflow-hidden">
      {/* 左侧：复盘列表 */}
      <div className="w-56 shrink-0 border-r border-[#1f2937] flex flex-col bg-[#0a0e1a]">
        <div className="p-3 border-b border-[#1f2937]">
          <button onClick={newReview}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-[#00d4aa]/10 text-[#00d4aa] text-sm font-medium hover:bg-[#00d4aa]/20 transition">
            <Plus size={15} />新建复盘
          </button>
        </div>
        <div className="flex-1 overflow-auto py-2">
          {reviews.map(r => (
            <div key={r.id} onClick={() => setActiveId(r.id)}
              className={clsx('group px-3 py-2.5 cursor-pointer flex items-start gap-2 transition',
                activeId === r.id ? 'bg-[#1f2937]' : 'hover:bg-[#111827]'
              )}>
              <div className="flex-1 min-w-0">
                <p className={clsx('text-sm font-medium truncate', activeId === r.id ? 'text-white' : 'text-gray-300')}>{r.title}</p>
                <p className="text-gray-500 text-xs truncate mt-0.5">{r.preview}</p>
                <p className="text-gray-600 text-xs mt-0.5">{r.date}</p>
              </div>
              <button onClick={e => { e.stopPropagation(); deleteReview(r.id) }}
                className="opacity-0 group-hover:opacity-100 p-1 text-gray-600 hover:text-[#f87171] transition shrink-0">
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* 右侧：对话区 */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-5 py-3 border-b border-[#1f2937] flex items-center gap-3">
          <Sparkles size={16} className="text-[#00d4aa]" />
          <div>
            <p className="text-white font-semibold text-sm">{active?.title}</p>
            <p className="text-gray-500 text-xs">和 AI 一起复盘，沉淀投资经验</p>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-5 flex flex-col gap-4">
          {active?.messages.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center gap-6 text-center">
              <div className="w-14 h-14 rounded-2xl bg-[#00d4aa]/10 flex items-center justify-center">
                <Bot size={28} className="text-[#00d4aa]" />
              </div>
              <div>
                <p className="text-white font-semibold mb-1">开始今天的复盘</p>
                <p className="text-gray-500 text-sm">描述你的操作、想法或困惑，AI 帮你分析</p>
              </div>
              <div className="grid grid-cols-2 gap-2 w-full max-w-md">
                {PROMPTS.map(p => (
                  <button key={p} onClick={() => setInput(p)}
                    className="text-left px-3 py-2.5 rounded-xl border border-[#1f2937] text-gray-400 text-xs hover:border-[#374151] hover:text-white transition">
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {active?.messages.map((m, i) => (
            <div key={i} className={clsx('flex gap-3', m.role === 'user' ? 'flex-row-reverse' : 'flex-row')}>
              <div className={clsx('w-8 h-8 rounded-full flex items-center justify-center shrink-0',
                m.role === 'user' ? 'bg-[#1f2937]' : 'bg-[#00d4aa]/15'
              )}>
                {m.role === 'user' ? <User size={15} className="text-gray-300" /> : <Bot size={15} className="text-[#00d4aa]" />}
              </div>
              <div className={clsx('max-w-[75%] rounded-2xl px-4 py-3 text-sm',
                m.role === 'user'
                  ? 'bg-[#1f2937] text-white rounded-tr-sm'
                  : 'bg-[#0d1220] border border-[#1f2937] text-gray-200 rounded-tl-sm'
              )}>
                {m.content.split('\n').map((line, j) => {
                  const bold = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                  return <p key={j} className={j > 0 ? 'mt-1.5' : ''} dangerouslySetInnerHTML={{ __html: bold }} />
                })}
                <p className="text-gray-600 text-xs mt-2">{m.time}</p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-[#00d4aa]/15 flex items-center justify-center shrink-0">
                <Bot size={15} className="text-[#00d4aa]" />
              </div>
              <div className="bg-[#0d1220] border border-[#1f2937] rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex gap-1 items-center h-5">
                  {[0,1,2].map(i => (
                    <div key={i} className="w-1.5 h-1.5 rounded-full bg-[#00d4aa] animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="p-4 border-t border-[#1f2937]">
          <div className="flex gap-3 items-end">
            <textarea value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() } }}
              placeholder="描述今天的操作、想法或困惑... (Enter 发送，Shift+Enter 换行)"
              rows={2}
              className="flex-1 bg-[#111827] border border-[#1f2937] rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#00d4aa] resize-none" />
            <button onClick={sendMessage} disabled={!input.trim() || loading}
              className="p-3 rounded-xl bg-[#00d4aa] text-[#0a0e1a] hover:bg-[#00b894] disabled:opacity-40 disabled:cursor-not-allowed transition shrink-0">
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
