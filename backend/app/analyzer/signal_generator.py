"""综合信号生成器 V2 — 合并情绪面 + 量化面，生成每日操作建议。

V1: 博主共识45% + 新闻情绪30% + 散户情绪25%  (纯情绪)
V2: 博主共识25% + 新闻情绪20% + 散户情绪15% + 资金面25% + 行业动能15%  (情绪+量化)

当量化数据不可用时，自动回退到V1三维权重。
"""
import logging
from datetime import datetime, date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_text
from app.analyzer.blogger_scorer import get_blogger_consensus, MIN_PREDICTIONS
from app.analyzer.news_analyzer import get_news_sentiment_score
from app.models.models import DailySignal, Blogger, Prediction, RetailSentiment, QuantSnapshot

logger = logging.getLogger(__name__)

# ── V2 五维权重（量化数据可用时）──
W_BLOGGER_V2 = 0.25
W_NEWS_V2 = 0.20
W_RETAIL_V2 = 0.15
W_FUND_FLOW_V2 = 0.25
W_INDUSTRY_V2 = 0.15

# ── V1 三维权重（量化数据不可用时回退）──
W_BLOGGER_V1 = 0.45
W_NEWS_V1 = 0.30
W_RETAIL_V1 = 0.25

# 散户情绪反向因子（True 时散户极度看多会减弱买入信号）
RETAIL_CONTRARIAN = True
RETAIL_CONTRARIAN_THRESHOLD = 0.6  # 散户情绪 > 0.6 时触发反向

# 信号阈值
SIGNAL_THRESHOLDS = [
    (0.6,  "strong_buy",  "强烈买入"),
    (0.2,  "buy",         "买入"),
    (-0.2, "hold",        "持有观望"),
    (-0.6, "sell",        "减仓"),
    (-999, "strong_sell", "强烈减仓"),
]

EXPLAIN_SYSTEM = """你是一个专业的基金投资顾问，擅长用简洁易懂的语言向普通投资者解释市场信号。
语气专业但不晦涩，适合投资新手阅读。不要使用"强烈推荐"等夸张表述，要客观中立。"""


async def generate_daily_signal(
    db: AsyncSession,
    target_symbol: str = "000300",
    target_name: str = "沪深300",
) -> DailySignal | None:
    """生成今日综合投资信号。"""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # 检查今天是否已生成
    exists_result = await db.execute(
        select(DailySignal).where(DailySignal.signal_date == today)
    )
    existing = exists_result.scalar_one_or_none()
    if existing:
        logger.info("Daily signal already generated for today")
        return existing

    # ── 1. 情绪面数据 ──
    blogger_score = await get_blogger_consensus(db, hours=72)
    news_score = await get_news_sentiment_score(db, hours=24)
    retail_score = await get_retail_sentiment_score(db, hours=6)

    # 散户情绪反向处理
    retail_effective = retail_score
    if RETAIL_CONTRARIAN and retail_score > RETAIL_CONTRARIAN_THRESHOLD:
        retail_effective = -retail_score * 0.5
        logger.info(f"Contrarian mode: retail_score={retail_score:.2f} → effective={retail_effective:.2f}")

    # ── 2. 量化面数据 ──
    quant = await _get_latest_quant(db)
    fund_flow_score = quant.fund_flow_score if quant else None
    industry_score = quant.industry_momentum_score if quant else None

    # ── 3. 综合分计算 ──
    quant_available = fund_flow_score is not None or industry_score is not None

    if quant_available:
        final_score, weights_used = _calc_v5_score(
            blogger_score, news_score, retail_effective,
            fund_flow_score, industry_score,
        )
        logger.info(f"V5 signal: blogger={blogger_score:+.2f} news={news_score:+.2f} "
                     f"retail={retail_effective:+.2f} ff={fund_flow_score} ind={industry_score} "
                     f"→ final={final_score:+.4f}")
    else:
        # V1 回退
        final_score = _calc_v3_score(
            blogger_score, news_score, retail_effective,
            W_BLOGGER_V1, W_NEWS_V1, W_RETAIL_V1,
        )
        weights_used = "v1_3dim"
        logger.info(f"V1 signal (quant unavailable): blogger={blogger_score:+.2f} "
                     f"news={news_score:+.2f} retail={retail_effective:+.2f} "
                     f"→ final={final_score:+.4f}")

    # ── 4. 映射信号 ──
    signal_key, signal_label = _score_to_signal(final_score)

    # ── 5. 统计数据 ──
    since_72h = datetime.utcnow() - timedelta(hours=72)
    blogger_count_result = await db.execute(
        select(Prediction.blogger_id)
        .where(
            Prediction.post_time >= since_72h,
            Prediction.is_prediction == True,
        )
        .distinct()
    )
    participating_bloggers = len(blogger_count_result.scalars().all())

    from app.models.models import News
    news_count_result = await db.execute(
        select(News)
        .where(
            News.publish_time >= datetime.utcnow() - timedelta(hours=24),
            News.sentiment_score.isnot(None),
        )
    )
    analyzed_news = len(news_count_result.scalars().all())

    # ── 6. 置信度 ──
    confidence = _calc_confidence(participating_bloggers, analyzed_news, final_score, quant_available)

    # ── 7. LLM 解释 ──
    reasoning = await _generate_reasoning(
        signal_label=signal_label,
        final_score=final_score,
        blogger_score=blogger_score,
        news_score=news_score,
        retail_score=retail_score,
        confidence=confidence,
        participating_bloggers=participating_bloggers,
        analyzed_news=analyzed_news,
        target_name=target_name,
        quant=quant,
        quant_available=quant_available,
    )

    # ── 8. 存储 ──
    signal = DailySignal(
        signal_date=today,
        target_symbol=target_symbol,
        target_name=target_name,
        blogger_consensus_score=blogger_score,
        news_sentiment_score=news_score,
        retail_sentiment_score=retail_score,
        fund_flow_score=fund_flow_score,
        industry_momentum_score=industry_score,
        final_signal=signal_key,
        confidence=confidence,
        reasoning=reasoning or f"今日{target_name}信号：{signal_label}",
        participating_bloggers=participating_bloggers,
        analyzed_news_count=analyzed_news,
    )
    db.add(signal)
    await db.commit()

    logger.info(
        f"Daily signal generated: {signal_key} "
        f"(score={final_score:.3f}, confidence={confidence:.1f}%, weights={weights_used})"
    )
    return signal


async def _get_latest_quant(db: AsyncSession) -> QuantSnapshot | None:
    """获取最近一条量化快照（24小时内）。"""
    since = datetime.utcnow() - timedelta(hours=24)
    result = await db.execute(
        select(QuantSnapshot)
        .where(QuantSnapshot.snapshot_date >= since)
        .order_by(QuantSnapshot.snapshot_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _calc_v5_score(
    blogger: float,
    news: float,
    retail: float,
    fund_flow: float | None,
    industry: float | None,
) -> tuple[float, str]:
    """V5 五维加权计算 — 自动处理量化维度部分缺失。

    Returns: (score, weights_desc)
    """
    # 如果某个量化维度缺失，把它的权重按比例分给另一个量化维度
    # 如果两个都缺失，不应被调用（调用方已检查）
    if fund_flow is None and industry is not None:
        w_ff = 0.0
        w_ind = W_FUND_FLOW_V2 + W_INDUSTRY_V2
    elif fund_flow is not None and industry is None:
        w_ff = W_FUND_FLOW_V2 + W_INDUSTRY_V2
        w_ind = 0.0
    elif fund_flow is not None and industry is not None:
        w_ff = W_FUND_FLOW_V2
        w_ind = W_INDUSTRY_V2
    else:
        # 都缺失 — 回退到V1
        return _calc_v3_score(blogger, news, retail, W_BLOGGER_V1, W_NEWS_V1, W_RETAIL_V1), "v1_fallback"

    score = (
        blogger * W_BLOGGER_V2
        + news * W_NEWS_V2
        + retail * W_RETAIL_V2
        + (fund_flow or 0) * w_ff
        + (industry or 0) * w_ind
    )
    return round(score, 4), "v5_5dim"


def _calc_v3_score(
    blogger: float,
    news: float,
    retail: float,
    w_blogger: float,
    w_news: float,
    w_retail: float,
) -> float:
    """V1 三维加权计算综合分。"""
    score = blogger * w_blogger + news * w_news + retail * w_retail
    return round(score, 4)


def _score_to_signal(score: float) -> tuple[str, str]:
    for threshold, key, label in SIGNAL_THRESHOLDS:
        if score >= threshold:
            return key, label
    return "hold", "持有观望"


def _calc_confidence(
    bloggers: int, news: int, score: float, quant: bool = False
) -> float:
    """置信度：数据越多、分数越极端，置信度越高。

    V2 中量化数据可用时额外加成。
    """
    data_conf = min(1.0, (bloggers / 5 + news / 20) / 2)
    if quant:
        data_conf = min(1.0, data_conf * 1.2)  # 量化数据加成 20%
    signal_strength = min(1.0, abs(score) / 0.6)
    return round((data_conf * 0.5 + signal_strength * 0.5) * 100, 1)


async def _generate_reasoning(
    signal_label: str,
    final_score: float,
    blogger_score: float,
    news_score: float,
    retail_score: float,
    confidence: float,
    participating_bloggers: int,
    analyzed_news: int,
    target_name: str,
    quant: QuantSnapshot | None = None,
    quant_available: bool = False,
) -> str | None:
    direction = "偏多（看涨）" if blogger_score > 0 else "偏空（看跌）" if blogger_score < 0 else "中性"
    news_direction = "偏正面" if news_score > 0.1 else "偏负面" if news_score < -0.1 else "中性"

    # 构建量化数据描述
    quant_lines = ""
    if quant_available and quant:
        nb = f"北向净流入{quant.northbound_total:+.1f}亿" if quant.northbound_total is not None else "北向数据缺失"
        ff = f"资金面得分{quant.fund_flow_score:+.2f}" if quant.fund_flow_score is not None else "资金面缺失"
        ind_avg = f"行业均涨{quant.industry_avg_change_pct:+.2f}%" if quant.industry_avg_change_pct is not None else ""
        pe = f"PE={quant.pe_000300:.1f}" if quant.pe_000300 else ""

        quant_lines = f"""
量化面数据：
- {nb}，{ff}
- {ind_avg} {pe}
"""
        weight_desc = "博主25%、新闻20%、散户15%、资金面25%、行业动能15%"
    else:
        quant_lines = "\n量化面数据：暂不可用（使用纯情绪权重）\n"
        weight_desc = "博主45%、新闻30%、散户25%"

    prompt = f"""请为以下投资信号生成一段简洁的解释（200字以内）：

目标标的：{target_name}
今日信号：{signal_label}
置信度：{confidence:.1f}%

情绪面数据：
- 参与博主数：{participating_bloggers}位，博主共识方向：{direction}（共识分：{blogger_score:+.2f}）
- 分析新闻数：{analyzed_news}条，新闻情绪：{news_direction}（情绪分：{news_score:+.2f}）
- 散户情绪分：{retail_score:+.2f}
{quant_lines}
综合得分：{final_score:+.3f}（权重：{weight_desc}）

要求：
1. 说明信号来源和主要依据，区分情绪面和量化面
2. 如有量化数据，重点解读北向资金和资金流方向
3. 提示数据局限性
4. 末尾加一句风险提示
5. 语气客观，适合投资新手"""

    return await llm_text(EXPLAIN_SYSTEM, prompt)


async def get_retail_sentiment_score(db: AsyncSession, hours: int = 6) -> float:
    """获取最近N小时散户情绪平均分。

    查询 retail_sentiments 表中最近记录，
    按来源加权平均后返回 [-1, 1] 的情绪分。
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(RetailSentiment).where(
            RetailSentiment.captured_at >= since,
        )
    )
    records = result.scalars().all()

    if not records:
        return 0.0

    # 按来源分组求平均
    source_scores: dict[str, list[float]] = {}
    for r in records:
        source_scores.setdefault(r.source, []).append(r.sentiment_score)

    # 各来源等权平均
    source_avgs = [sum(scores) / len(scores) for scores in source_scores.values()]
    return round(sum(source_avgs) / len(source_avgs), 4)
