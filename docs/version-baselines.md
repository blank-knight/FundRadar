# FundRadar 版本基线 (Tags)

> 每个版本都有对应的 git tag，可以随时回退。
> 回退命令：`git reset --hard v1.0.0`（把 v1.0.0 换成你要的版本）

---

## 版本历史

### v2.0.0 — 五维信号全链路 (2026-06-17)
- **commit:** `d830e59`
- **内容：**
  - 量化数据接入（北向资金/指数资金流/行业排名/龙虎榜/PE/PB）
  - 信号系统 V1→V2：情绪+量化五维加权，缺失自动回退
  - 博主迁移：雪球废弃→微博大V(7位)+东财分析师TOP5
  - LLM降级链：glm-5-turbo→glm-4-flash
  - systemd服务部署 + Docker postgres/redis
  - Telegram @Fund_Radar_bot 推送验证（lifetime会员）
  - 107 tests passed
  - Alembic migration: quant_snapshots表
- **已知问题：** push2行业排名502（大陆IP风控）；jin10 SSL超时（WSL网络）

### v1.0.0 — 生产稳定版 (2026-06-16)
- **commit:** `8b91d02`
- **内容：**
  - 批量解析博主帖子，LLM调用从150次降到30次，解决429
  - 12个定时任务（09:35-17:00生产时间表）
  - 三维信号：博主45%+新闻30%+散户25%
  - Telegram推送验证通过
- **回退理由：** 如果你想要纯情绪三维信号（不要量化），回退到这里

### v0.5.0 — 三维信号系统 (2026-06-16)
- **commit:** `ce1f886`
- **内容：**
  - 散户情绪源：akshare(微博NLP+东财评论)+微博大V爬虫
  - 三维加权信号：博主+新闻+散户
  - 散户反向因子：极度看多时减弱买入信号
  - DB: RetailSentiment模型+migration

### v0.4.0 — 三维改造前基线 (2026-06-15)
- **commit:** `138c781`
- **内容：**
  - 雪球WAF+微博+散户情绪多数据源改造前的快照
  - 二维信号：博主+新闻

### v0.3.0 — 前端对接后端 (2026-06-15)
- **commit:** `97449a5`
- **内容：**
  - ReviewPage对接真实后端API
  - Mock降级机制

### v0.2.0 — Vercel前端上线 (2026-06-14)
- **commit:** `53caf2d`
- **内容：**
  - Vercel deploy + 信号复盘API
  - 前端首次上线

### v0.1.0 — 项目初始化 (2026-06-14)
- **commit:** `ef50ef7`
- **内容：**
  - FundRadar A股基金信号SaaS骨架
  - FastAPI + SQLAlchemy + PostgreSQL

---

## 如何回退

```bash
cd ~/clawd/fund-radar

# 查看所有版本
git tag -l -n1

# 回退到某个版本（本地改动会丢失）
git reset --hard v1.0.0

# 如果只是想看看某个版本的代码（不丢当前改动）
git stash
git checkout v1.0.0
# 看完后回来
git checkout main
git stash pop
```

## 版本号规则

- **v0.x** — 早期开发（二维/三维信号，基础功能）
- **v1.x** — 生产可用（三维信号稳定，TG推送通过）
- **v2.x** — 五维信号（量化数据接入，当前版本）
- **v3.x** — （计划）全前端对接 + VPS部署 + 商用化
