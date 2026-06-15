# FundRadar - 项目记忆

> 每次开工前读这个文件。

## 项目概况
- **路径**: ~/clawd/fund-radar
- **功能**: A股基金信号 SaaS，Python/FastAPI/PostgreSQL/Redis/React PWA
- **GitHub**: github.com/blank-knight/FundRadar
- **Telegram bot**: @Fund_Radar_bot (token已配置)
- **DB**: Docker postgres:5433（本机5432被占）

## 当前进度
- Phase 1-9 后端已完成
- Phase 2 前端 UI 全部6页面已完成
- 2026-06-15: Vercel 部署上线 + ReviewPage API 对接完成
- 所有页面支持 Mock 降级（VITE_API_URL 未配置时自动用 Mock 数据）
- 下一步: 后端部署(Railway/Fly.io) + 真实 JWT Auth 对接

## 技术栈
- 后端: Python / FastAPI
- 数据库: PostgreSQL (端口5433)
- 缓存: Redis
- 前端: React PWA (Vite + TypeScript + Tailwind CSS + recharts)
- 部署: 前端 Vercel（已上线），后端待部署

## Vercel 部署要点
- vercel.json 在项目根目录，installCommand/buildCommand 都 cd frontend
- VITE_API_URL 环境变量控制前端是否调真实 API
- 不配置 VITE_API_URL 时所有页面自动 Mock 降级，纯前端可正常展示

## 坑和注意事项
- DB 端口是 5433 不是默认的 5432
- 前端 auth 目前用 mock-token，真实 JWT 对接待做
