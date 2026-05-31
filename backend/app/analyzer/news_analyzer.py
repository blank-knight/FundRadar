"""新闻情感分析 — 批量处理，加权平均得出市场情绪分。"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_json
from app.models.models import News

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的A股市场情感分析师。
分析财经新闻对A股市场的情感倾向，重点关注：
- 货币政策（降准降息=正面，收紧=负面）
- 监管政策（支持=正面，限制=负面）
- 宏观经济数据（超预期=正面，不及预期=负面）
- 外部环境（中美关系、美联储政策等）
- 企业盈利（超预期=正面）

请严格按JSON数组格式返回，不要有任何额外文字。"""

USER_TEMPLATE = """分析以下财经新闻对A股市场的情感倾向：

{news_list}

请返回JSON数组，每条新闻对应一个对象：
[
  {{
    "id": 新闻序号,
    "sentiment": "positive / negative / neutral",
    "score": -1.0到1.0（-1极度负面，0中性，1极度正面）,
    "reason": "一句话理由"
  }},
  ...
]"""


async def analyze_news_batch(db: AsyncSession, news_items: list) -> list[dict]:
    """批量分析新闻情感，每批最多20条。"""
    if not news_items:
        return []

    # 构建新闻列表文本
    news_text = "\n".join(
        f"{i+1}. {n.title}" + (f"（{n.summary[:100]}）" if n.summary else "")
        for i, n in enumerate(news_items)
    )

    raw = await llm_json(
        system=SYSTEM_PROMPT,
        user=USER_TEMPLATE.format(news_list=news_text),
    )

    if not isinstance(raw, list):
        logger.warning("News sentiment LLM returned non-list")
        return []

    return raw


async def analyze_unanalyzed_news(db: AsyncSession, hours: int = 24) -> dict:
    """分析最近N小时内还没有情感分析的新闻。"""
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(News)
        .where(
            News.publish_time >= since,
            News.sentiment_score.is_(None),
        )
        .order_by(News.publish_time.desc())
        .limit(100)
    )
    news_list = result.scalars().all()

    if not news_list:
        return {"analyzed": 0}

    # 分批处理，每批20条
    batch_size = 20
    total_analyzed = 0

    for i in range(0, len(news_list), batch_size):
        batch = news_list[i:i + batch_size]
        results = await analyze_news_batch(db, batch)

        # 把结果写回 DB
        result_map = {r["id"]: r for r in results if isinstance(r, dict) and "id" in r}
        for j, news in enumerate(batch):
            r = result_map.get(j + 1)
            if not r:
                continue
            news.sentiment_score = float(r.get("score", 0.0))
            news.sentiment_label = r.get("sentiment", "neutral")
            news.llm_analysis = r.get("reason", "")
            news.llm_raw_response = r
            total_analyzed += 1

        await db.commit()

    logger.info(f"News sentiment analysis done: {total_analyzed}/{len(news_list)}")
    return {"analyzed": total_analyzed, "total": len(news_list)}


async def get_news_sentiment_score(db: AsyncSession, hours: int = 24) -> float:
    """计算最近N小时新闻的加权情感分（越新权重越高）。返回 -1 到 1。"""
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(News)
        .where(
            News.publish_time >= since,
            News.sentiment_score.isnot(None),
        )
        .order_by(News.publish_time.desc())
        .limit(50)
    )
    news_list = result.scalars().all()

    if not news_list:
        return 0.0

    # 指数衰减权重：越新权重越高
    now = datetime.utcnow()
    total_weight = 0.0
    weighted_sum = 0.0

    for news in news_list:
        age_hours = (now - news.publish_time).total_seconds() / 3600
        weight = 2 ** (-age_hours / 12)  # 半衰期12小时
        weighted_sum += (news.sentiment_score or 0.0) * weight
        total_weight += weight

    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0
