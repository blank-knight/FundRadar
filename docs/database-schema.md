# FundRadar 数据库文档

**更新时间:** 2026-06-17
**数据库:** PostgreSQL 16 (Docker, 端口5433)
**连接:** localhost:5433 / user=fundradar / db=fundradar

## 快速查询

```bash
cd ~/clawd/fund-radar/backend
.venv/bin/python3 -c "
import asyncio; from dotenv import load_dotenv; load_dotenv('.env')
from app.core.database import AsyncSessionLocal
from sqlalchemy import text
async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text('你的SQL'))
        for row in r.fetchall(): print(row)
asyncio.run(main())
"
```

---

## 一、核心数据表

### 1. daily_signals — 每日综合信号（输出）

最终生成的投资信号，每天1条（标的=沪深300）。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| signal_date | timestamp | 信号日期 |
| target_symbol | varchar | 标的代码（如000300） |
| target_name | varchar | 标的名称（如沪深300） |
| blogger_consensus_score | float | 博主共识分 (-1~1) |
| news_sentiment_score | float | 新闻情绪分 (-1~1) |
| retail_sentiment_score | float | 散户情绪分 (-1~1) |
| fund_flow_score | float | 资金面得分 (-1~1) |
| industry_momentum_score | float | 行业动能得分 (-1~1, 可能为NULL) |
| final_signal | varchar | 信号: strong_buy/buy/hold/sell/strong_sell |
| confidence | float | 置信度 0~100% |
| reasoning | text | LLM生成的解释文本 |
| participating_bloggers | int | 参与博主数 |
| analyzed_news_count | int | 分析的新闻数 |
| created_at | timestamp | 创建时间 |

**查询示例:**
```sql
-- 查看所有历史信号
SELECT signal_date, final_signal, confidence,
       blogger_consensus_score, news_sentiment_score,
       retail_sentiment_score, fund_flow_score
FROM daily_signals ORDER BY signal_date;

-- 查看今天的信号
SELECT * FROM daily_signals
WHERE signal_date >= CURRENT_DATE;
```

---

### 2. news — 新闻（输入）

爬取的财经新闻，LLM分析后填充sentiment_score。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| source | varchar | 来源: eastmoney / eastmoney_fund |
| title | varchar | 标题 |
| url | varchar | 原文链接（唯一键） |
| publish_time | timestamp | 发布时间 |
| summary | text | 摘要 |
| sentiment_score | float | 情绪分 (-1~1, NULL=未分析) |
| sentiment_label | varchar | 情绪标签: positive/negative/neutral |
| llm_analysis | text | LLM分析原文 |
| llm_raw_response | json | LLM完整返回 |
| created_at | timestamp | 入库时间 |

**查询示例:**
```sql
-- 今天的新闻及情绪分析
SELECT title, sentiment_score, sentiment_label
FROM news WHERE publish_time >= CURRENT_DATE
ORDER BY publish_time DESC;

-- 只看负面新闻
SELECT title, sentiment_score FROM news
WHERE sentiment_score < -0.3
ORDER BY publish_time DESC LIMIT 20;
```

---

### 3. bloggers — 博主信息

支持多平台: weibo(微博大V), eastmoney_analyst(东财分析师), xueqiu(已废弃)

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| platform | varchar | 平台: weibo / eastmoney_analyst / xueqiu |
| platform_user_id | varchar | 平台内ID |
| username | varchar | 昵称 |
| avatar_url | varchar | 头像 |
| follower_count | int | 粉丝数 |
| accuracy_score | float | 综合准确率 0~100 |
| total_predictions | int | 总预测数 |
| correct_predictions | int | 正确预测数 |
| is_active | bool | 是否启用 |
| created_at | timestamp | |
| updated_at | timestamp | |

**当前博主列表:**
```
weibo:              但斌、林园、吴晓波、付鹏、杨德龙、任泽平、洪灏（7位）
eastmoney_analyst:  宇之光(国元)、魏鹏程(中信)、宫帅(广发)、唐凯(东北)、王文瑞(湘财)（5位）
xueqiu:             但斌（已停用 is_active=False）
```

**查询示例:**
```sql
-- 查看博主列表和准确率
SELECT platform, username, follower_count, accuracy_score,
       total_predictions, correct_predictions, is_active
FROM bloggers ORDER BY platform, accuracy_score DESC;
```

---

### 4. predictions — 博主帖子/预测

微博帖子原文 + 东财分析师评级，LLM解析后填充predicted_direction。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| blogger_id | int | 关联bloggers.id |
| post_url | varchar | 帖子URL（唯一键） |
| post_content | text | 帖子内容 |
| post_time | timestamp | 发帖时间 |
| predicted_direction | varchar | 预测方向: bullish/bearish/neutral |
| predicted_target | varchar | 预测标的（股票代码） |
| confidence | float | 置信度 0~1 |
| llm_reasoning | text | LLM推理过程 |
| llm_raw_response | json | LLM完整返回 |
| is_verified | bool | 是否已验证(T+1) |
| is_prediction | bool | LLM判断是否为有效预测 |
| raw_data | json | 原始数据 |
| created_at | timestamp | |

**查询示例:**
```sql
-- 最近的博主预测
SELECT b.platform, b.username, p.post_time,
       p.predicted_direction, p.confidence, LEFT(p.post_content, 80)
FROM predictions p JOIN bloggers b ON p.blogger_id = b.id
WHERE p.is_prediction = True
ORDER BY p.post_time DESC;

-- 各平台预测数量统计
SELECT b.platform, COUNT(*),
       SUM(CASE WHEN p.predicted_direction='bullish' THEN 1 ELSE 0 END) as bullish,
       SUM(CASE WHEN p.predicted_direction='bearish' THEN 1 ELSE 0 END) as bearish
FROM predictions p JOIN bloggers b ON p.blogger_id = b.id
WHERE p.is_prediction = True
GROUP BY b.platform;
```

---

### 5. retail_sentiments — 散户情绪

第三方预分析的聚合结果（非我们自己做NLP）。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| source | varchar | 来源: weibo_nlp / eastmoney_comment |
| symbol | varchar | 标的（MARKET=全市场） |
| sentiment_score | float | 情绪分 (-1~1) |
| bullish_ratio | float | 看多比例 |
| bearish_ratio | float | 看空比例 |
| raw_data | json | 原始数据 |
| captured_at | timestamp | 采集时间 |
| created_at | timestamp | |

**数据来源说明:**
- `weibo_nlp`: 金十数据对50只热门股微博讨论的NLP分析结果
- `eastmoney_comment`: 东财千股千评对全市场5000+股票的综合评分

**查询示例:**
```sql
-- 最近的散户情绪
SELECT source, sentiment_score, bullish_ratio, bearish_ratio, captured_at
FROM retail_sentiments ORDER BY captured_at DESC;
```

---

### 6. quant_snapshots — 量化数据快照

每条记录是某一时刻的全部量化数据。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| snapshot_date | timestamp | 快照时间 |
| northbound_hgt | float | 沪股通净流入(亿) |
| northbound_sgt | float | 深股通净流入(亿) |
| northbound_total | float | 北向合计净流入(亿) |
| industry_avg_change_pct | float | 行业平均涨跌幅 |
| industry_top_json | json | 涨幅TOP行业 |
| industry_bottom_json | json | 跌幅TOP行业 |
| fund_flow_000300 | float | 沪深300主力净流入 |
| fund_flow_399006 | float | 创业板主力净流入 |
| fund_flow_000016 | float | 上证50主力净流入 |
| fund_flow_detail | json | 资金流明细 |
| dragon_tiger_count | int | 龙虎榜个股数 |
| dragon_tiger_net_buy_wan | float | 龙虎榜净买入(万) |
| dragon_tiger_top_json | json | 龙虎榜TOP |
| pe_000300 | float | 沪深300 PE |
| pb_000300 | float | 沪深300 PB |
| fund_flow_score | float | 资金面综合得分(-1~1) |
| industry_momentum_score | float | 行业动能得分(-1~1) |
| raw_data | json | 原始数据 |
| created_at | timestamp | |

**数据来源:** a-stock-data (github.com/simonlin1212/a-stock-data)
- 北向资金: 同花顺接口
- 资金流: 东财push2his
- 行业排名: 东财push2（⚠️ 常返回502）
- 龙虎榜: 东财datacenter
- 估值: 腾讯接口

**查询示例:**
```sql
-- 最近一条量化快照
SELECT snapshot_date, northbound_total, fund_flow_score,
       industry_momentum_score, pe_000300, pb_000300
FROM quant_snapshots ORDER BY snapshot_date DESC LIMIT 1;
```

---

### 7. market_data — 行情数据

跟踪指数的每日行情。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| symbol | varchar | 指数代码: 000300/399006/000016 |
| name | varchar | 指数名称 |
| trade_date | timestamp | 交易日 |
| open_price | float | 开盘 |
| high_price | float | 最高 |
| low_price | float | 最低 |
| close_price | float | 收盘 |
| change_pct | float | 涨跌幅(%) |
| volume | float | 成交量 |
| created_at | timestamp | |

---

### 8. crawl_logs — 爬取日志

每次爬取的执行记录。

| 列名 | 类型 | 说明 |
|------|------|------|
| id | int | 主键 |
| crawler_name | varchar | 爬虫名: market_data/news/bloggers_multi/sentiment/quant |
| run_at | timestamp | 执行时间 |
| status | varchar | success/partial/failed/skipped |
| items_fetched | int | 获取数 |
| items_saved | int | 入库数 |
| items_skipped | int | 跳过数（已存在） |
| error_message | text | 错误信息 |
| raw_snapshot | json | 爬取快照 |
| duration_seconds | float | 耗时 |

**查询示例:**
```sql
-- 按天看哪些爬虫跑了
SELECT DATE(run_at), crawler_name, status, items_saved
FROM crawl_logs
ORDER BY run_at DESC;

-- 最近失败的爬取
SELECT crawler_name, run_at, error_message
FROM crawl_logs WHERE status = 'failed'
ORDER BY run_at DESC LIMIT 10;
```

---

## 二、辅助表

### prediction_verifications — 博主预测T+1验证

| 列名 | 说明 |
|------|------|
| prediction_id | 关联predictions.id |
| verification_date | 验证日期 |
| actual_change_pct | 实际涨跌幅 |
| is_correct | 预测是否正确 |

### signal_verifications — 信号T+1验证

| 列名 | 说明 |
|------|------|
| signal_id | 关联daily_signals.id |
| predicted_signal | 预测信号 |
| actual_change_pct | 实际涨跌幅 |
| is_correct | 是否正确 |

### signal_reviews — 信号复盘

连续错误时触发的LLM自动复盘记录。

### users — 用户

| plan | 说明 |
|------|------|
| free | 免费用户（推送只有基本信号） |
| lifetime | 终身会员（推送完整分析） |

### orders — 订单
### portfolio — 持仓
### portfolio_analyses — 持仓分析
### watchlist — 关注列表
### trade_reviews — 交易复盘

---

## 三、数据流关系

```
market_data ──────────────────┐
                              ├──→ signal_generator ──→ daily_signals ──→ signal_pusher ──→ Telegram
news ──→ news_analyzer ───────┤
predictions ──→ blogger_scorer┤
retail_sentiments ───────────┤
quant_snapshots ─────────────┘

bloggers ──→ orchestrator ──→ predictions（微博帖子+分析师评级）
news_crawler ──→ news
sentiment_crawler ──→ retail_sentiments
quant_crawler ──→ quant_snapshots

每次爬取 ──→ crawl_logs（记录成功/失败/耗时）
```

---

## 四、当前数据量（2026-06-17）

| 表 | 总量 | 时间范围 |
|----|------|----------|
| news | 190条 | 05-29 ~ 06-17 |
| predictions | 5条 | 06-17 |
| retail_sentiments | 2条 | 06-17 |
| quant_snapshots | 1条 | 06-17 |
| market_data | 39条 | 05-29 ~ 06-17 |
| daily_signals | 4条 | 05-29, 05-31, 06-15, 06-17 |
| crawl_logs | 43条 | 05-29 ~ 06-17 |
| bloggers | 15条 | — |
