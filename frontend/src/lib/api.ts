/**
 * 统一 API 地址配置。
 * - 本地开发: VITE_API_URL=http://localhost:8001/api
 * - Vercel 部署: 在 Vercel 项目设置里配 VITE_API_URL 指向后端地址
 * - 未配置时 fallback 到 mock 模式（前端用内置假数据展示）
 */
export const API_URL = import.meta.env.VITE_API_URL || ''
export const USE_MOCK = !API_URL
