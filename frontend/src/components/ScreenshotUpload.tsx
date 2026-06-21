import { useState, useRef } from 'react'
import { Upload, Scan, Loader2, CheckCircle2, X, AlertCircle, TrendingUp, TrendingDown } from 'lucide-react'
import clsx from 'clsx'

interface Fund {
  fund_name: string
  fund_code: string | null
  amount: number | null
  profit: number | null
  profit_pct: number | null
}

type Status = 'idle' | 'uploading' | 'recognizing' | 'preview' | 'importing' | 'done' | 'error'

export default function ScreenshotUpload({ onImported }: { onImported?: () => void }) {
  const [status, setStatus] = useState<Status>('idle')
  const [imagePreview, setImagePreview] = useState<string>('')
  const [imageBase64, setImageBase64] = useState<string>('')
  const [funds, setFunds] = useState<Fund[]>([])
  const [errorMsg, setErrorMsg] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // ── 选择图片 ──
  const handleFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setErrorMsg('请上传图片文件')
      setStatus('error')
      return
    }

    // 压缩图片（减少 base64 体积，加快 API 调用）
    const compressed = await compressImage(file, 800)
    setImagePreview(compressed.preview)
    setImageBase64(compressed.base64)
    setStatus('uploading')
    recognize(compressed.base64)
  }

  // ── 调 API 识别 ──
  const recognize = async (b64: string) => {
    setStatus('recognizing')
    setErrorMsg('')
    try {
      const resp = await fetch('/api/screenshot-ocr', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: b64 }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.error || `识别失败 (${resp.status})`)
      }
      setFunds(data.funds || [])
      setStatus('preview')
    } catch (err: any) {
      setErrorMsg(err.message || '识别失败')
      setStatus('error')
    }
  }

  // ── 确认导入 ──
  const confirmImport = async () => {
    setStatus('importing')
    setErrorMsg('')
    try {
      const resp = await fetch('/api/import-portfolio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ funds, mode: 'merge' }),
      })
      const data = await resp.json()
      if (!resp.ok) {
        throw new Error(data.error || `导入失败 (${resp.status})`)
      }
      setStatus('done')
      onImported?.()
    } catch (err: any) {
      setErrorMsg(err.message || '导入失败')
      setStatus('error')
    }
  }

  // ── 编辑识别结果 ──
  const editFund = (i: number, field: keyof Fund, value: any) => {
    setFunds(prev => prev.map((f, idx) => idx === i ? { ...f, [field]: value } : f))
  }
  const removeFund = (i: number) => setFunds(prev => prev.filter((_, idx) => idx !== i))

  const reset = () => {
    setStatus('idle')
    setFunds([])
    setImagePreview('')
    setImageBase64('')
    setErrorMsg('')
  }

  // ─────────────────────────────────
  // 渲染
  // ─────────────────────────────────
  if (status === 'idle' || status === 'error') {
    return (
      <div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 px-3 py-2 bg-[#1a1f2e] border border-[#2a3142] text-gray-300 rounded-lg text-sm hover:bg-[#222838] hover:text-white transition"
        >
          <Scan size={16} />
          <span>截图导入</span>
        </button>
        {status === 'error' && (
          <div className="mt-2 flex items-center gap-2 text-xs text-[#f87171]">
            <AlertCircle size={14} />
            <span>{errorMsg}</span>
            <button onClick={reset} className="text-gray-500 hover:text-white ml-1">重试</button>
          </div>
        )}
      </div>
    )
  }

  // 识别中
  if (status === 'uploading' || status === 'recognizing') {
    return (
      <div className="flex items-center gap-3 px-4 py-3 bg-[#0d1220] border border-[#1f2937] rounded-xl">
        {imagePreview && (
          <img src={imagePreview} alt="截图" className="w-12 h-16 object-cover rounded-lg" />
        )}
        <Loader2 className="animate-spin text-[#00d4aa]" size={18} />
        <span className="text-gray-400 text-sm">
          {status === 'uploading' ? '上传中...' : 'AI 识别中（约10秒）...'}
        </span>
      </div>
    )
  }

  // 导入中
  if (status === 'importing') {
    return (
      <div className="flex items-center gap-3 px-4 py-3 bg-[#0d1220] border border-[#1f2937] rounded-xl">
        <Loader2 className="animate-spin text-[#00d4aa]" size={18} />
        <span className="text-gray-400 text-sm">正在导入持仓...</span>
      </div>
    )
  }

  // 导入完成
  if (status === 'done') {
    return (
      <div className="flex items-center gap-3 px-4 py-3 bg-[#14532d]/20 border border-[#4ade80]/30 rounded-xl">
        <CheckCircle2 className="text-[#4ade80]" size={18} />
        <span className="text-[#4ade80] text-sm">导入成功！网页正在重建（约30秒后可见）</span>
        <button onClick={reset} className="text-gray-400 text-xs hover:text-white ml-auto">关闭</button>
      </div>
    )
  }

  // 预览识别结果
  if (status === 'preview') {
    const noCode = funds.filter(f => !f.fund_code).length
    return (
      <div className="bg-[#0d1220] border border-[#1f2937] rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-white font-semibold text-sm flex items-center gap-2">
            <Scan size={16} className="text-[#00d4aa]" />
            识别到 {funds.length} 只基金
          </h3>
          <button onClick={reset} className="text-gray-500 hover:text-white">
            <X size={18} />
          </button>
        </div>

        {noCode > 0 && (
          <div className="flex items-center gap-2 text-xs text-[#fbbf24] mb-3 px-3 py-2 bg-[#78350f]/20 rounded-lg">
            <AlertCircle size={14} />
            {noCode} 只基金未匹配到代码，请手动填写或删除
          </div>
        )}

        {/* 基金列表 */}
        <div className="space-y-2 max-h-[300px] overflow-y-auto">
          {funds.map((f, i) => (
            <div key={i} className="flex items-center gap-2 bg-[#111827] border border-[#1f2937] rounded-lg p-2">
              <span className={clsx(
                'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0',
                (f.profit ?? 0) >= 0 ? 'bg-[#14532d]/40 text-[#4ade80]' : 'bg-[#7f1d1d]/40 text-[#f87171]'
              )}>
                {f.profit !== null && f.profit >= 0 ? '+' : ''}
              </span>
              <div className="flex-1 min-w-0">
                <input
                  value={f.fund_name || ''}
                  onChange={e => editFund(i, 'fund_name', e.target.value)}
                  className="w-full bg-transparent text-white text-sm font-medium border-none outline-none truncate"
                />
                <div className="flex items-center gap-2">
                  <input
                    value={f.fund_code || ''}
                    onChange={e => editFund(i, 'fund_code', e.target.value)}
                    placeholder="代码"
                    className="w-24 bg-[#0d1220] border border-[#1f2937] rounded px-2 py-0.5 text-xs text-gray-300 outline-none focus:border-[#00d4aa]"
                  />
                  {f.amount && (
                    <span className="text-gray-400 text-xs">¥{f.amount.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}</span>
                  )}
                  {f.profit_pct !== null && (
                    <span className={clsx('text-xs flex items-center gap-0.5',
                      f.profit_pct >= 0 ? 'text-[#4ade80]' : 'text-[#f87171]'
                    )}>
                      {f.profit_pct >= 0 ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                      {f.profit_pct >= 0 ? '+' : ''}{f.profit_pct}%
                    </span>
                  )}
                </div>
              </div>
              <button onClick={() => removeFund(i)} className="text-gray-600 hover:text-[#f87171] p-1">
                <X size={14} />
              </button>
            </div>
          ))}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-3 mt-3">
          <button onClick={reset} className="flex-1 py-2 rounded-lg border border-[#1f2937] text-gray-400 text-sm hover:text-white transition">
            取消
          </button>
          <button onClick={confirmImport} className="flex-1 py-2 rounded-lg bg-[#00d4aa] text-[#0a0e1a] text-sm font-semibold hover:bg-[#00b894] transition">
            确认导入 {funds.length} 只
          </button>
        </div>
      </div>
    )
  }

  return null
}

/**
 * 压缩图片到指定宽度，返回 base64 和预览 URL
 */
async function compressImage(file: File, maxWidth: number): Promise<{ base64: string; preview: string }> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const img = new Image()
      img.onload = () => {
        const canvas = document.createElement('canvas')
        const scale = Math.min(1, maxWidth / img.width)
        canvas.width = img.width * scale
        canvas.height = img.height * scale
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85)
        // 去掉 "data:image/jpeg;base64," 前缀
        const base64 = dataUrl.split(',')[1]
        resolve({ base64, preview: dataUrl })
      }
      img.onerror = reject
      img.src = e.target!.result as string
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
