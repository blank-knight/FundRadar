# 量化数据接入设计文档

**模块名称:** Quantitative Data Engine (a-stock-data)
**创建时间:** 2026-06-17
**状态:** 已实现
**数据源:** [a-stock-data](https://github.com/simonlin1212/a-stock-data) — 纯 httpx 直连东财/腾讯/同花顺，无 akshare 依赖

---

## 1. 背景与目标

V1 版本信号系统依赖三维纯情绪数据（博主45% + 新闻30% + 散户25%），缺少量化面支撑。
本文档描述如何接入 [a-stock-data](https://github.com/simonlin1212/a-stock-data) 的量化数据源，
将信号系统升级为五维混合模型（情绪 + 量化）。

### 信号权重演进

| 版本 | 博主 | 新闻 | 散户 | 资金面 | 行业动能 | 触发条件 |
|------|------|------|------|--------|---------|---------|
| V1 | 45% | 30% | 25% | -- | -- | 量化数据不可用时自动回退 |
| V2 | 25% | 20% | 15% | 25% | 15% | 量化数据可用（默认） |

---

## 2. 数据源清单

| 数据 | API 来源 | 函数 | 输出 |
|------|---------|------|------|
| 北向资金 | 同花顺 hexin.cn | `hsgt_realtime()` | 沪深股通实时净流入(亿) |
| 指数资金流 | 东财 push2his | `index_fund_flow()` | 主力/超大单 120日净流入序列 |
| 行业排名 | 东财 push2 | `industry_comparison()` | 全市场~100个行业涨跌幅 |
| 龙虎榜 | 东财 datacenter | `daily_dragon_tiger()` | 当日上榜个股明细 |
| PE/PB 估值 | 腾讯 qt.gtimg.cn | `tencent_quote()` | 实时行情快照(价格/PE/PB) |
| 全球资讯 | 东财 7×24 | `eastmoney_global_news()` | 50条滚动快讯 |

### 内置防护

- **限流**: `em_get()` / `em_datacenter()` 内置 1 秒间隔 + 随机抖动（0.1~0.3s），防 IP 封禁
- **降级**: 单一数据源失败不影响整体信号，`fund_flow_score` 或 `industry_momentum_score` 置 None
- **重试**: httpx 请求最多 3 次重试，超时 15 秒

---

## 3. 数据模型

### 新增表: `quant_snapshots`

```python
class QuantSnapshot(Base):
    """量化数据快照 — 每个交易日采集后存一条。"""
    __tablename__ = "quant_snapshots"

    id: int                          # PK
    snapshot_date: datetime          # 采集时间

    # 北向资金
    northbound_hgt: float            # 沪股通净流入(亿)
    northbound_sgt: float            # 深股通净流入(亿)
    northbound_total: float          # 合计净流入(亿)

    # 指数资金流（沪深300）
    main_net_inflow: float           # 主力净流入(元)
    super_large_net: float           # 超大单净流入(元)
    large_net: float                 # 大单净流入(元)
    medium_net: float                # 中单净流入(元)
    small_net: float                 # 小单净流入(元)

    # 行业轮动
    industry_top3_json: dict         # TOP3 涨幅行业 [{name, change_pct, rank}, ...]
    industry_bottom3_json: dict      # BOTTOM3 跌幅行业
    industry_up_count: int           # 上涨行业数
    industry_down_count: int         # 下跌行业数
    industry_avg_change_pct: float   # 全行业平均涨跌幅(%)

    # 龙虎榜
    dragon_tiger_count: int          # 上榜个股数
    dragon_tiger_top_json: dict      # TOP5 净买入个股

    # 估值
    pe_000300: float                 # 沪深300 PE(TTM)
    pb_000300: float                 # 沪深300 PB
    dividend_yield_000300: float     # 沪深300 股息率

    # 衍生指标
    fund_flow_score: float           # 资金面综合得分 [-1, 1]
    industry_momentum_score: float   # 行业动能得分 [-1, 1]

    created_at: datetime             # 入库时间
```

### DailySignal 表新增字段

```python
fund_flow_score: float           # 资金面得分 [-1, 1]（默认 None）
industry_momentum_score: float   # 行业动能得分 [-1, 1]（默认 None）
```

### Migration

```bash
# d7e1f9a3b4c5 — add_quant_snapshot_and_signal_quant_fields
alembic upgrade head
```

---

## 4. 评分算法

### 4.1 资金面得分 `_compute_fund_flow_score(northbound, main_net_inflow)`

综合北向资金和主力资金流方向，归一化到 [-1, 1]：

| 条件 | 得分 |
|------|------|
| 北向 > +20亿 且 主力 > 0 | +0.6 ~ +1.0（看多） |
| 北向 < -20亿 且 主力 < 0 | -0.6 ~ -1.0（看空） |
| 两个方向矛盾或都在 ±10亿内 | ±0.1 ~ ±0.3（中性偏移） |
| 数据全部缺失 | None（触发 V1 回退） |

权重：北向资金 60% + 主力资金流 40%。

### 4.2 行业动能得分 `_compute_industry_momentum(industry_data)`

综合平均涨跌幅 + 上涨行业占比：

```python
score = avg_change_pct_normalized * 0.6 + (up_count / total_count - 0.5) * 2 * 0.4
```

- 全行业均涨 > +2% → score ≈ +0.8~1.0
- 全行业均跌 > -2% → score ≈ -0.8~-1.0
- 涨跌各半 → score ≈ 0

---

## 5. 信号生成 V2

### 5.1 五维加权

```python
# 量化数据可用时
final_score = (
    blogger_score * 0.25
    + news_score * 0.20
    + retail_score * 0.15
    + fund_flow_score * 0.25
    + industry_score * 0.15
)
```

### 5.2 权重自动重分配

| 场景 | 处理 |
|------|------|
| 资金面 + 行业动能均可用 | 标准五维权重 |
| 仅资金面可用 | 行业权重(15%)合并到资金面 → 资金面 40% |
| 仅行业动能可用 | 资金面权重(25%)合并到行业 → 行业 40% |
| 量化数据全部缺失 | 回退 V1 三维权重（博主45% + 新闻30% + 散户25%） |

### 5.3 置信度加成

量化数据可用时，置信度额外加成 20%：

```python
if quant_available:
    data_confidence = min(1.0, data_confidence * 1.2)
```

### 5.4 LLM 解释

V2 的 LLM 解释 prompt 包含量化数据摘要：
- 北向资金净流入方向
- 资金面得分
- 行业平均涨跌幅
- 明确标注权重分布（"博主25%、新闻20%、散户15%、资金面25%、行业动能15%"）

---

## 6. 定时任务

| 时间（北京） | 任务 | 说明 |
|-------------|------|------|
| 09:35 | `job_market_data` | 不变 |
| 10:00 | `job_xueqiu_crawl` | **改**: 微博大V + 东财分析师（雪球已废弃） |
| 10:15 | `job_weibo_crawl` | 不变（KOL帖子） |
| 10:45 | `job_sentiment_crawl` | 不变 |
| 10:30 | `job_news_crawl` | 不变 |
| 15:30 | `job_market_data` | 收盘补抓 |
| **15:35** | **`job_quant_crawl`** | 量化数据采集 |
| 15:35 | `job_verify_blogger_predictions` | 不变 |
| 16:00 | `job_generate_signal` | V2：五维加权 |
| 16:30 | `job_push_signal` | 推送到Telegram @Fund_Radar_bot |
| 16:45 | `job_signal_feedback` | 不变 |
| 17:00 | `job_update_nav` | 不变 |

**时间线设计**: `quant_crawl` 在 15:35 执行（收盘后5分钟），在 16:00 信号生成前完成。
misfire_grace_time = 600 秒（允许 10 分钟延迟）。

---

## 7. 模块结构

```
backend/app/
├── crawler/
│   ├── astock.py             # [新] 量化数据采集器（7个函数）
│   └── orchestrator.py       # [改] 新增 run_quant_crawl + 评分函数
├── analyzer/
│   └── signal_generator.py   # [改] V1→V2 五维加权 + 自动回退
├── models/
│   └── models.py             # [改] 新增 QuantSnapshot + DailySignal 字段
├── scheduler/
│   ├── jobs.py               # [改] 新增 job_quant_crawl
│   └── scheduler.py          # [改] 注册 quant_crawl 任务
└── alembic/versions/
    └── d7e1f9a3b4c5_*.py     # [新] migration
```

---

## 8. 降级与风险

| 风险 | 降级策略 |
|------|---------|
| 东财 push2 502（大陆 IP 风控） | 行业排名置 None，行业动能维度自动从五维中剔除 |
| 腾讯行情指数代码前缀不匹配 | PE/PB 置 None，不影响资金面得分 |
| 北向资金 API 失败 | `fund_flow_score` 仅依赖主力资金流 |
| 量化数据全部不可用 | 信号系统自动回退 V1 三维情绪权重 |
| `run_quant_crawl` 超时 | misfire_grace_time=600s，超时跳过本轮量化采集 |

---

## 9. 测试

### 单元测试（纯逻辑，无网络）

| 测试项 | 说明 |
|--------|------|
| V1 三维加权计算 | `_calc_v3_score()` 5种场景 |
| V2 五维权重之和 = 1.0 | `W_*_V2` 常量验证 |
| V5 全维度数据 | `_calc_v5_score()` 全有数据 |
| V5 部分量化缺失 | 权重重分配验证 |
| V5 量化全缺失回退 | 自动回退 V1 |
| 资金面评分 | 正/负/中性/None 场景 |
| 行业动能评分 | 涨/跌/平场景 |

### 集成测试（需网络）

| 测试项 | 数据源 |
|--------|--------|
| 北向资金实时 | hexin.cn ✅ 已验证 |
| 沪深300主力资金流 | push2his ✅ 已验证 |
| 行业排名 | push2 ⚠️ 间歇502 |

**当前**: 107 passed, 1 skipped, 0 failed

---

## 10. 已知问题 & 后续优化

- [ ] **腾讯行情指数前缀**: `000300` 需映射为 `sh000300` 才能获取 PE/PB
- [ ] **push2 行业排名备用方案**: 考虑换 IP 池或降低请求频率
- [ ] **权重自适应**: 根据各维度历史准确率动态调整权重
- [ ] **情绪动量**: 追踪情绪变化趋势（今天比昨天更看多/看空）
- [ ] **关键事件提取**: 从全球资讯中提取重大事件并加权影响
