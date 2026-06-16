# 多数据源情绪分析模块设计文档

**模块名称:** Multi-Source Sentiment Engine
**创建时间:** 2026-06-16
**状态:** 开发中
**关联版本:** Phase 5（Post-MVP 增强）

---

## 1. 背景与问题

FundRadar 原始架构依赖单一数据源（雪球 KOL）生成博主共识分。实测发现：

| 问题 | 根因 | 影响 |
|------|------|------|
| 雪球 API 被 WAF 拦截 | 阿里云 WAF，`acw_tc` cookie 不足以通过 | 博主帖子爬不到 → `blogger_consensus_score` 永远 = 0 |
| 信号全部输出 hold | 共识分 0 → `final_score` 只靠新闻分（权重 40%）→ 阈值达不到 buy/sell | 产品核心价值失效 |
| 无散户情绪维度 | 设计中只有"博主观点"，缺少市场群体情绪 | 信号维度单一，置信度低 |

## 2. 目标

引入三个数据源，构建多维度情绪信号：

```
信号输入
├── A. 博主共识（KOL 观点）—— 雪球 + 微博
│   ├── 雪球: Playwright 过 WAF → 原 XueqiuCrawler
│   └── 微博: m.weibo.cn API → 新 WeiboCrawler
├── B. 散户情绪（群体情绪）—— akshare
│   ├── 微博舆情 NLP（金十数据源，个股多空比例）
│   └── 东财综合评分（5184只股票，机构参与度/关注指数）
└── C. 新闻情绪（已有）—— NewsCrawler + LLM
    └── 东方财富/新浪新闻（保持不变）
```

## 3. 架构设计

### 3.1 新增模块

```
backend/app/
├── crawler/
│   ├── xueqiu.py           # [改] 增加 Playwright WAF bypass
│   ├── weibo.py            # [新] 微博大V爬虫
│   ├── sentiment.py        # [新] akshare 散户情绪爬虫
│   └── orchestrator.py     # [改] 注册新爬虫任务
├── analyzer/
│   ├── blogger_scorer.py   # [改] get_blogger_consensus 支持多平台
│   └── signal_generator.py # [改] 三维度加权信号
├── models/
│   └── models.py           # [改] 新增 RetailSentiment 模型
├── schemas/
│   └── schemas.py          # [改] 新增 RetailSentiment schema
└── scheduler/
    └── jobs.py             # [改] 新增微博/情绪定时任务
```

### 3.2 数据模型变更

#### 新增表: `retail_sentiments`

```python
class RetailSentiment(Base):
    """散户情绪数据快照 — 每次爬取存一条。"""
    __tablename__ = "retail_sentiments"

    id: int                  # PK
    source: str              # "weibo_nlp" | "eastmoney_comment"
    symbol: str              # "000300" | "399006" 等，"MARKET" 表示全市场
    sentiment_score: float   # -1 到 1（统一标准化）
    bullish_ratio: float     # 看多比例 0-1（如有）
    bearish_ratio: float     # 看空比例 0-1（如有）
    raw_data: dict           # 原始数据快照
    captured_at: datetime    # 采集时间
    created_at: datetime     # 入库时间
```

#### DailySignal 表新增字段

```python
# 新增到 DailySignal
retail_sentiment_score: float   # 散户情绪分 -1 到 1（默认 0.0）
```

### 3.3 信号生成权重调整

原方案（2 维度）:
```
final_score = blogger_score * 0.6 + news_score * 0.4
```

新方案（3 维度）:
```
final_score = blogger_score * 0.45 + news_score * 0.30 + retail_score * 0.25
```

权重设计依据：
- 博主共识（KOL）权重最高 → 专业判断，有 T+1 验证机制
- 新闻情绪次之 → 事件驱动，影响面广
- 散户情绪最低 → 反向指标参考（散户极度看多往往是见顶信号）

**注意：** 散户情绪作为反向指标时，可在 signal_generator 中引入 `retail_contrarian_factor` 参数控制是否反向使用。

### 3.4 各数据源技术方案

#### 方案 A: 雪球 — Playwright 过 WAF

**问题:** 雪球使用阿里云 WAF，httpx 直连返回 WAF 验证页面而非 JSON。
**方案:** 用 Playwright headless 浏览器访问雪球首页，自动执行 WAF JS 验证，提取完整 cookie（含 `xq_a_token` 等），注入回 httpx client。

```
Playwright launch → GET xueqiu.com → WAF JS 自动执行 → 提取 cookies
→ httpx.AsyncClient(cookies=extracted) → 正常调用 API
```

**依赖:** `playwright`（需 `playwright install chromium`）
**降级策略:** Playwright 不可用时 fallback 到手动配置的 `XUEQIU_COOKIE` 环境变量。

#### 方案 C: 微博 — m.weibo.cn 移动端 API

**问题:** 微博 PC 端 API 需要复杂鉴权，IP 容易被封（实测返回 432）。
**方案:** 使用 `m.weibo.cn` 移动端 H5 API，鉴权门槛低，cookie 容易获取。

**API 端点:**
- 搜索: `GET /api/container/getIndex?containerid=100103type=1&q={keyword}`
- 用户时间线: `GET /api/container/getIndex?containerid=107603{uid}`

**KOL 列表（与雪球重叠的财经大V）:**
- 但斌（微博粉丝 2700万+）
- 林园
- 侯安扬
- 财经大V持续扩充...

**降级策略:** 微博 API 失败时静默跳过，不影响其他数据源。

#### 方案 B: akshare 散户情绪

**数据源:** 金十数据中心微博舆情 + 东方财富个股评论

| akshare 函数 | 数据 | 输出 |
|-------------|------|------|
| `stock_js_weibo_report(time_period)` | 微博舆情报告 | 50 只个股的多空 rate |
| `stock_comment_em()` | 东财综合评论 | 5184 只股票的综合得分/机构参与度 |

**情绪标准化:**
- 微博 rate > 1.0 → bullish, < 1.0 → bearish，映射到 [-1, 1]
- 东财综合得分 → 归一化到 [0, 1] → 映射到 [-1, 1]
- 两个源加权平均得到最终 `retail_sentiment_score`

**优势:** 免费、稳定、无需鉴权、akshare 维护。

## 4. 定时任务变更

| 时间（北京） | 任务 | 说明 |
|-------------|------|------|
| 09:35 | `job_market_data` | 不变 |
| 10:00 | `job_xueqiu_crawl` | 改：先用 Playwright 刷 cookie |
| **10:10** | **`job_weibo_crawl`** | **新：微博大V帖子爬取** |
| **10:20** | **`job_sentiment_crawl`** | **新：akshare 散户情绪** |
| 10:30 | `job_news_crawl` | 不变 |
| 15:30 | `job_market_data` | 不变（二次抓取） |
| 16:00 | `job_generate_signal` | 改：三维度加权 |
| 16:30 | `job_push_signal` | 改：推送消息含散户情绪 |
| 16:45 | `job_signal_feedback` | 不变 |
| 17:00 | `job_update_nav` | 不变 |

## 5. 测试策略

### 5.1 测试文件规划

```
backend/tests/
├── test_crawlers.py          # [改] 新增微博/情绪爬虫测试
├── test_multi_source.py      # [新] 多数据源集成测试
└── test_e2e.py               # [改] E2E 加散户情绪维度
```

### 5.2 测试矩阵

| 类别 | 测试项 | 网络依赖 | 预期数量 |
|------|--------|---------|---------|
| **雪球 Playwright** | | | |
| - cookie 提取 | Playwright 启动 → 雪球首页 → cookie 包含 xq_a_token | ✅ 网络 | 1 |
| - 降级模式 | 无 Playwright → fallback 手动 cookie | ❌ Mock | 1 |
| - API 调用 | 拿到 cookie 后 httpx 调 timeline API | ✅ 网络 | 2 |
| **微博** | | | |
| - 搜索 API | m.weibo.cn 搜索"基金" → 返回微博列表 | ✅ 网络 | 1 |
| - 用户时间线 | 指定大V UID → 返回帖子列表 | ✅ 网络 | 1 |
| - HTML 清洗 | 去除 `<a>` `<span>` 等标签 | ❌ 纯逻辑 | 2 |
| - 情绪解析 | 帖子文本 → bullish/bearish/neutral | ❌ Mock | 3 |
| **散户情绪** | | | |
| - akshare 微博 NLP | stock_js_weibo_report → 标准化 score | ✅ 网络 | 1 |
| - akshare 东财评论 | stock_comment_em → 标准化 score | ✅ 网络 | 1 |
| - 多源聚合 | 两源加权 → 最终 retail_score | ❌ 纯逻辑 | 3 |
| - 标准化 | rate/score → [-1,1] 映射 | ❌ 纯逻辑 | 4 |
| **信号生成** | | | |
| - 三维加权 | blogger+news+retail → final_score | ❌ 纯逻辑 | 5 |
| - 反向因子 | retail 极度看多 → 信号减弱 | ❌ 纯逻辑 | 2 |
| - 降级 | 某源缺失 → 权重自动重分配 | ❌ 纯逻辑 | 3 |
| **E2E** | | | |
| - 全链路 | 三源数据 → 信号 → 推送 | ✅ 网络 | 1 |

**预计新增测试: ~30 条**

### 5.3 测试标记

```python
# pyproject.toml
markers = [
    "network: 需要网络连接",
    "llm: 调用 LLM API（耗费 token）",
    "browser: 需要 Playwright 浏览器环境",
    "slow: 执行时间 > 10s",
]
```

## 6. 依赖变更

```toml
# pyproject.toml 新增
"playwright >= 1.40.0",
```

安装后需执行:
```bash
playwright install chromium
```

## 7. 风险与降级

| 风险 | 降级策略 |
|------|---------|
| Playwright 服务器环境不可用 | Fallback 手动 cookie（`XUEQIU_COOKIE`） |
| 微博 API 封 IP | 增加延迟（3-5s），失败静默跳过 |
| akshare 接口变更 | try-catch 包裹，记录 CrawlLog，score=0 |
| 某数据源全部失败 | signal_generator 自动重分配权重（两源 → 等比放大） |

## 8. 变更清单

### 新增文件
- `backend/app/crawler/weibo.py` — 微博大V爬虫
- `backend/app/crawler/sentiment.py` — akshare 散户情绪爬虫
- `backend/tests/test_multi_source.py` — 多数据源测试
- `docs/multi-source-sentiment.md` — 本文档

### 修改文件
- `backend/app/crawler/xueqiu.py` — 增加 Playwright WAF bypass
- `backend/app/crawler/orchestrator.py` — 注册微博/情绪爬虫
- `backend/app/analyzer/blogger_scorer.py` — 多平台共识计算
- `backend/app/analyzer/signal_generator.py` — 三维加权信号
- `backend/app/models/models.py` — 新增 RetailSentiment + DailySignal 字段
- `backend/app/schemas/schemas.py` — 新增 RetailSentiment schema
- `backend/app/scheduler/jobs.py` — 新增定时任务
- `backend/app/scheduler/scheduler.py` — 注册新任务
- `backend/alembic/versions/` — 新增 migration
- `backend/pyproject.toml` — 新增 playwright 依赖

## 9. 实现顺序

1. **DB 层** — 模型 + migration（其他都依赖这步）
2. **方案 B（散户情绪）** — 最简单，akshare 现成，立刻有数据
3. **方案 A（雪球 Playwright）** — 改造现有代码
4. **方案 C（微博）** — 全新模块
5. **信号生成器** — 三维加权
6. **orchestrator + scheduler** — 集成
7. **测试** — 全量通过
8. **文档 + 提交** — 更新 progress.md + push
