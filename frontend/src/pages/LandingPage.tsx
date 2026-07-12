import { useNavigate } from 'react-router-dom'
import { ChevronDown, ArrowRight, TrendingUp, Users, Newspaper, Brain } from 'lucide-react'

export default function LandingPage() {
  const navigate = useNavigate()

  const features = [
    { icon: TrendingUp, title: '五维信号体系', desc: '行情趋势、博主共识、新闻情绪、散户情绪、量化数据 — 五个维度交叉验证。' },
    { icon: Users, title: '博主评分引擎', desc: '追踪东财分析师和微博大V，LLM 解析预测方向，历史准确率自动评分。' },
    { icon: Newspaper, title: '新闻情绪监控', desc: '实时抓取东财新闻，GLM 大模型分析多空倾向，情绪得分可视化。' },
    { icon: Brain, title: '智能持仓建议', desc: '持仓截图上传自动识别，LLM 结合信号给出加减仓建议。' },
  ]

  return (
    <div className="relative min-h-screen bg-black text-white overflow-x-hidden">
      {/* ===== GLOBAL BACKGROUND VIDEO ===== */}
      <video
        autoPlay
        loop
        muted
        playsInline
        className="fixed inset-0 w-full h-full object-cover pointer-events-none"
        style={{ opacity: 0.35 }}
      >
        <source src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260307_083826_e938b29f-a43a-41ec-a153-3d4730578ab8.mp4" type="video/mp4" />
      </video>
      {/* Dark overlay so text stays readable */}
      <div className="fixed inset-0 bg-black/40 pointer-events-none" />

      {/* ===== GLOBAL BACKGROUND LAYERS ===== */}
      {/* Grid pattern */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
                            linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
          maskImage: 'radial-gradient(ellipse 80% 60% at 50% 0%, black 40%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse 80% 60% at 50% 0%, black 40%, transparent 100%)',
        }}
      />
      {/* Top center glow */}
      <div
        className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(0,212,170,0.06) 0%, transparent 60%)' }}
      />
      {/* Left glow */}
      <div
        className="fixed top-[40%] -left-32 w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.04) 0%, transparent 60%)' }}
      />
      {/* Right glow */}
      <div
        className="fixed top-[60%] -right-32 w-[400px] h-[400px] rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(168,85,247,0.03) 0%, transparent 60%)' }}
      />

      {/* ===== NAVBAR ===== */}
      <nav className="relative z-10 flex items-center justify-between px-8 md:px-28 py-4">
        <div className="flex items-center gap-12 md:gap-20">
          <div className="flex items-center gap-2">
            <div className="relative w-8 h-8 flex items-center justify-center">
              <div className="absolute inset-0 rounded-lg" style={{background: 'radial-gradient(circle, rgba(0,212,170,0.15) 0%, transparent 70%)'}} />
              <div className="relative w-7 h-7 rounded-lg bg-white flex items-center justify-center">
                <span className="text-black font-bold text-sm">F</span>
              </div>
            </div>
            <span className="text-xl font-bold tracking-tight">
              Fund<span className="serif-accent">Radar</span>
            </span>
          </div>
          <div className="hidden md:flex items-center gap-4 text-sm text-muted">
            <a href="#features" className="hover:text-white transition">功能</a>
            <a href="#features" className="hover:text-white transition flex items-center gap-1">
              产品 <ChevronDown size={14} className="opacity-50" />
            </a>
            <a href="#testimonial" className="hover:text-white transition">用户评价</a>
          </div>
        </div>
        <button
          onClick={() => navigate('/heatmap')}
          className="bg-white text-black rounded-lg text-sm font-semibold px-4 py-2 hover:opacity-85 transition"
        >
          进入面板
        </button>
      </nav>

      {/* ===== HERO ===== */}
      <section className="relative z-10 flex flex-col items-center px-4 mt-16 md:mt-20">
        {/* Tag pill */}
        <div className="liquid-glass flex items-center gap-2 px-3 py-2 rounded-lg mb-6 fade-up">
          <span className="bg-white text-black rounded-md text-sm font-medium px-2 py-0.5">New</span>
          <span className="text-sm text-muted">五维信号体系 2.0 已上线</span>
        </div>

        {/* Title */}
        <h1 className="text-5xl md:text-7xl tracking-[-2px] font-medium leading-[1.15] text-center mb-3 fade-up" style={{animationDelay: '0.1s', opacity: 0}}>
          基金投资。
          <br />
          <span className="serif-accent">一目了然</span>的信号面板。
        </h1>

        {/* Subtitle */}
        <p className="text-lg font-normal leading-6 opacity-90 mb-8 text-center fade-up" style={{color: 'hsl(210 17% 95%)', animationDelay: '0.2s', opacity: 0}}>
          FundRadar 帮你追踪基金信号、博主共识，<br />和数据驱动的投资决策。
        </p>

        {/* CTA */}
        <button
          onClick={() => navigate('/heatmap')}
          className="bg-white text-black rounded-full px-8 py-3.5 text-base font-medium hover:scale-[1.03] active:scale-[0.98] transition-transform fade-up"
          style={{animationDelay: '0.3s', opacity: 0}}
        >
          免费开始使用
        </button>
      </section>

      {/* ===== DASHBOARD PREVIEW ===== */}
      <section className="relative z-10 w-screen mt-12" style={{marginLeft: 'calc(-50vw + 50%)'}}>
        <div className="aspect-[16/9] relative overflow-hidden">
          {/* Mock dashboard card */}
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[90%] max-w-5xl rounded-2xl overflow-hidden border border-white/[0.06] bg-[#080808]">
            {/* Title bar */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.04]">
              <div className="flex gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
                <div className="w-2.5 h-2.5 rounded-full bg-white/10" />
              </div>
              <span className="text-xs text-muted ml-2">fundradar.app/heatmap</span>
            </div>
            {/* Body */}
            <div className="grid grid-cols-3 gap-4 p-6">
              {/* Left: signal cards */}
              <div className="space-y-3">
                <div className="card-glass p-3">
                  <div className="text-xs text-muted mb-1">沪深300</div>
                  <div className="text-2xl font-semibold text-accent">看多</div>
                  <div className="text-xs text-muted mt-1">置信度 78%</div>
                  <div className="mt-2 h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full rounded-full bg-accent" style={{width: '78%'}} />
                  </div>
                </div>
                <div className="card-glass p-3">
                  <div className="text-xs text-muted mb-1">创业板</div>
                  <div className="text-2xl font-semibold text-red-400">看空</div>
                  <div className="text-xs text-muted mt-1">置信度 64%</div>
                  <div className="mt-2 h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full rounded-full bg-red-400" style={{width: '64%'}} />
                  </div>
                </div>
                <div className="card-glass p-3">
                  <div className="text-xs text-muted mb-1">中证500</div>
                  <div className="text-2xl font-semibold text-accent">看多</div>
                  <div className="text-xs text-muted mt-1">置信度 71%</div>
                  <div className="mt-2 h-1.5 rounded-full bg-white/5 overflow-hidden">
                    <div className="h-full rounded-full bg-accent" style={{width: '71%'}} />
                  </div>
                </div>
              </div>
              {/* Center: chart */}
              <div className="card-glass p-4 col-span-2">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-sm text-muted">信号趋势</div>
                    <div className="text-lg font-semibold">近30天五维信号</div>
                  </div>
                  <div className="flex gap-2 text-xs">
                    <span className="text-accent">● 行情</span>
                    <span className="text-blue-400">● 博主</span>
                    <span className="text-yellow-400">● 情绪</span>
                  </div>
                </div>
                {/* SVG line chart */}
                <svg viewBox="0 0 400 120" className="w-full h-32">
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00d4aa" stopOpacity="0.2" />
                      <stop offset="100%" stopColor="#00d4aa" stopOpacity="0" />
                    </linearGradient>
                  </defs>
                  {/* Grid */}
                  {[0,30,60,90,120].map(y => (
                    <line key={y} x1="0" y1={y} x2="400" y2={y} stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                  ))}
                  {/* Lines */}
                  <path d="M0,90 C50,85 100,60 150,55 C200,50 250,30 300,35 C350,40 400,20 400,20" stroke="#00d4aa" strokeWidth="2" fill="none" strokeLinecap="round" />
                  <path d="M0,90 C50,85 100,60 150,55 C200,50 250,30 300,35 C350,40 400,20 400,20 L400,120 L0,120 Z" fill="url(#g1)" />
                  <path d="M0,100 C50,95 100,80 150,70 C200,65 250,50 300,48 C350,46 400,35 400,35" stroke="#3b82f6" strokeWidth="1.5" fill="none" strokeOpacity="0.5" strokeLinecap="round" />
                  <path d="M0,110 C50,100 100,90 150,85 C200,80 250,70 300,68 C350,66 400,55 400,55" stroke="#eab308" strokeWidth="1.5" fill="none" strokeOpacity="0.5" strokeLinecap="round" />
                </svg>
              </div>
            </div>
          </div>
          {/* Bottom fade */}
          <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-black to-transparent pointer-events-none" />
        </div>
      </section>

      {/* ===== FEATURES ===== */}
      <section id="features" className="relative z-10 px-8 md:px-28 py-24 md:py-32">
        <div className="max-w-3xl mx-auto text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-medium tracking-tight leading-[1.2] mb-4">
            数据驱动的<br />
            <span className="serif-accent">智能</span>基金分析。
          </h2>
          <p className="text-muted text-lg">不凭感觉做投资。每个信号都有数据支撑。</p>
        </div>

        <div className="grid md:grid-cols-2 gap-6 max-w-4xl mx-auto">
          {features.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="card-glass p-6 group">
              <div className="w-10 h-10 rounded-lg bg-white/[0.04] flex items-center justify-center mb-4 group-hover:bg-accent/10 transition">
                <Icon size={20} className="text-accent" />
              </div>
              <h3 className="text-lg font-semibold mb-2">{title}</h3>
              <p className="text-muted text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ===== TESTIMONIAL ===== */}
      <section id="testimonial" className="relative z-10 px-8 md:px-28 py-24 md:py-32">
        <div className="max-w-3xl mx-auto">
          <div className="text-5xl mb-6 opacity-20 font-serif">"</div>
          <p className="text-2xl md:text-4xl font-medium leading-[1.3] mb-8">
            FundRadar 让我不再凭感觉买卖基金。
            <br />
            <span className="text-muted">五个维度的信号交叉验证，让投资决策变得</span>
            <span className="serif-accent">有据可依</span>。
          </p>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full border-2 border-white/20 bg-white/5 flex items-center justify-center">
              <span className="text-muted text-lg font-medium">S</span>
            </div>
            <div>
              <div className="font-semibold">Steven Tao</div>
              <div className="text-sm text-muted">独立开发者 / 定投爱好者</div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== CTA ===== */}
      <section className="relative z-10 px-8 md:px-28 py-24">
        <div className="text-center max-w-xl mx-auto">
          <h2 className="text-3xl md:text-5xl font-medium tracking-tight mb-4">
            准备好了吗？
          </h2>
          <p className="text-muted text-lg mb-8">三秒进入面板，开始数据驱动的投资之旅。</p>
          <button
            onClick={() => navigate('/heatmap')}
            className="inline-flex items-center gap-2 bg-white text-black rounded-full px-8 py-3.5 text-base font-medium hover:scale-[1.03] active:scale-[0.98] transition-transform"
          >
            免费开始使用 <ArrowRight size={18} />
          </button>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="relative z-10 px-8 md:px-28 py-12 border-t border-white/[0.04]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-white flex items-center justify-center">
              <span className="text-black font-bold text-xs">F</span>
            </div>
            <span className="text-sm font-semibold">FundRadar</span>
          </div>
          <p className="text-xs text-muted">A股基金信号 SaaS · 数据驱动投资决策</p>
        </div>
      </footer>
    </div>
  )
}
