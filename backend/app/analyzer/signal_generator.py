"""综合信号生成器 — 合并博主共识 + 新闻情绪，生成每日操作建议。"""
import logging
from datetime import datetime, date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_text
from app.analyzer.blogger_scorer import get_blogger_consensus, MIN_PREDICTIONS
from app.analyzer.news_analyzer import get_news_sentiment_score
from app.models.models import DailySignal, Blogger, Prediction

logger = logging.getLogger(__name__)

# 权重
W_BLOGGER = 0.6
W_NEWS = 0.4

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

    # 1. 博主共识分
    blogger_score = await get_blogger_consensus(db, hours=72)

    # 2. 新闻情绪分
    news_score = await get_news_sentiment_score(db, hours=24)

    # 3. 综合分
    final_score = blogger_score * W_BLOGGER + news_score * W_NEWS

    # 4. 映射信号
    signal_key, signal_label = _score_to_signal(final_score)

    # 5. 统计参与博主数
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

    # 6. 统计分析新闻数
    from app.models.models import News
    news_count_result = await db.execute(
        select(News)
        .where(
            News.publish_time >= datetime.utcnow() - timedelta(hours=24),
            News.sentiment_score.isnot(None),
        )
    )
    analyzed_news = len(news_count_result.scalars().all())

    # 7. 置信度（基于数据量）
    confidence = _calc_confidence(participating_bloggers, analyzed_news, final_score)

    # 8. LLM 生成解释文字
    reasoning = await _generate_reasoning(
        signal_label=signal_label,
        final_score=final_score,
        blogger_score=blogger_score,
        news_score=news_score,
        confidence=confidence,
        participating_bloggers=participating_bloggers,
        analyzed_news=analyzed_news,
        target_name=target_name,
    )

    signal = DailySignal(
        signal_date=today,
        target_symbol=target_symbol,
        target_name=target_name,
        blogger_consensus_score=blogger_score,
        news_sentiment_score=news_score,
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
        f"(score={final_score:.3f}, confidence={confidence:.1f}%)"
    )
    return signal


def _score_to_signal(score: float) -> tuple[str, str]:
    for threshold, key, label in SIGNAL_THRESHOLDS:
        if score >= threshold:
            return key, label
    return "hold", "持有观望"


def _calc_confidence(bloggers: int, news: int, score: float) -> float:
    """置信度：数据越多、分数越极端，置信度越高。"""
    data_conf = min(1.0, (bloggers / 5 + news / 20) / 2)
    signal_strength = min(1.0, abs(score) / 0.6)
    return round((data_conf * 0.5 + signal_strength * 0.5) * 100, 1)


async def _generate_reasoning(
    signal_label: str,
    final_score: float,
    blogger_score: float,
    news_score: float,
    confidence: float,
    participating_bloggers: int,
    analyzed_news: int,
    target_name: str,
) -> str | None:
    direction = "偏多（看涨）" if blogger_score > 0 else "偏空（看跌）" if blogger_score < 0 else "中性"
    news_direction = "偏正面" if news_score > 0.1 else "偏负面" if news_score < -0.1 else "中性"

    prompt = f"""请为以下投资信号生成一段简洁的解释（150字以内）：

目标标的：{target_name}
今日信号：{signal_label}
置信度：{confidence:.1f}%

数据来源：
- 参与博主数：{participating_bloggers}位，博主共识方向：{direction}（共识分：{blogger_score:+.2f}）
- 分析新闻数：{analyzed_news}条，新闻情绪：{news_direction}（情绪分：{news_score:+.2f}）
- 综合得分：{final_score:+.3f}（博主权重60%，新闻权重40%）

要求：
1. 说明信号来源和主要依据
2. 提示数据局限性（如博主数量少、新闻有限等）
3. 末尾加一句风险提示
4. 语气客观，适合投资新手"""

    return await llm_text(EXPLAIN_SYSTEM, prompt)
