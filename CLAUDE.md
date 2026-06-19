# FundRadar — Agent 代码生成规则

---

## ⚠️ ALWAYS（每次生成代码前强制执行）

1. **先读通用规则**: `~/clawd/CLAUDE.md`（铁律，跨所有项目）
2. **再读项目规则**: `memory-bank/vibe-coding-core.md`（本项目专属规则）
3. **读进度**: `memory-bank/progress.md`（了解当前进度）
4. **读架构**: `memory-bank/architecture.md`（了解项目结构）
5. 每完成一步 → 更新 `memory-bank/progress.md`

---

## 🔴 铁律（违反 = 失败）

- **禁止假数据**: Mock/Stub/Demo 数据不得进入任何代码路径（前端/后端/测试/文档）。先查数据库/API，用真实数据。没有数据就显示空状态。
- **先读再写**: 没读 memory-bank/ 就开始写代码 = 违规。
- **模块化**: 单文件不超过 300 行。
- **每步验证**: 代码必须测试通过才标记完成。

---

## FundRadar 技术栈

- 后端: FastAPI + SQLAlchemy + PostgreSQL (Docker, port 5433) + Redis
- 前端: Next.js + TypeScript + Vercel
- LLM: GLM-5-turbo (降级链 → glm-4-flash)
- 调度: APScheduler
- 数据源: akshare + 东财 + 微博 + 同花顺 + a-stock-data
- 部署: WSL本地 systemd (后端) + Vercel (前端)
- TG Bot: @Fund_Radar_bot

---

## 五维信号体系

1. 行情趋势 (market) — 沪深300指数技术面
2. 博主共识 (blogger) — 东财分析师评级 + 微博大V
3. 新闻情绪 (news) — 东财新闻 → LLM分析多空
4. 散户情绪 (retail) — 金十微博舆情 + 东财千股千评
5. 量化数据 (quant) — 北向资金 + 行业排名 + PE/PB + 龙虎榜
