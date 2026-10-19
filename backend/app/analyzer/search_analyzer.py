"""搜索舆情 LLM 分析 — 将搜索引擎结果交给 LLM 判断多空情绪。

与 news_analyzer.py 的区别:
  - news_analyzer: 逐条分析新闻情感（单源、结构化）
  - search_analyzer: 批量分析搜索结果摘要（多源、定性）

输出: 综合情绪分 [-1, 1] + 关键观点摘要
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_json, llm_text
from app.models.models import SearchSentiment

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的A股市场分析师。
你将收到来自搜索引擎的多条金融分析结果（研报摘要、论坛讨论、媒体观点）。
请综合判断这些信息对A股市场（尤其是沪深300）的整体多空情绪。

重点关注:
- 机构观点（看多/看空/中性）
- 散户情绪（贪婪/恐惧）
- 政策面信号
- 资金面动向
- 事件驱动因素

请严格按JSON格式返回，不要有任何额外文字。"""

USER_TEMPLATE = """以下是搜索引擎返回的金融分析结果：

{search_results}

请综合分析以上信息，判断当前市场情绪。返回JSON对象：
{{
  "sentiment": "bullish / bearish / neutral",
  "score": -1.0到1.0的浮点数（-1=极度看空, 0=中性, 1=极度看多）,
  "bullish_count": 看多观点数量,
  "bearish_count": 看空观点数量,
  "neutral_count": 中性观点数量,
  "key_points": ["关键观点1", "关键观点2", "关键观点3"],
  "summary": "一段100字以内的综合判断"
}}"""


async def analyze_search_results(
    db: AsyncSession,
    search_items: list[dict],
) -> SearchSentiment | None:
    """分析搜索结果，生成情绪分并存储。

    Args:
        db: 数据库会话
        search_items: 搜索结果列表 [{"title", "snippet", "url", "source"}, ...]

    Returns:
        SearchSentiment 对象，或 None（失败时）
    """
    if not search_items:
        logger.warning("No search items to analyze")
        return None

    # 构建搜索结果文本（最多20条，避免 token 过多）
    items = search_items[:20]
    search_text = "\n\n".join(
        f"[{i+1}] {item.get('title', '')}\n    {item.get('snippet', '')[:200]}"
        for i, item in enumerate(items)
    )

    raw = await llm_json(
        system=SYSTEM_PROMPT,
        user=USER_TEMPLATE.format(search_results=search_text),
    )

    if not isinstance(raw, dict) or "score" not in raw:
        logger.warning(f"Search sentiment LLM returned unexpected format: {str(raw)[:200]}")
        return None

    score = float(raw.get("score", 0.0))
    score = max(-1.0, min(1.0, score))  # clamp

    sentiment = SearchSentiment(
        sentiment_score=score,
        sentiment_label=raw.get("sentiment", "neutral"),
        result_count=len(items),
        bullish_count=int(raw.get("bullish_count", 0)),
        bearish_count=int(raw.get("bearish_count", 0)),
        neutral_count=int(raw.get("neutral_count", 0)),
        key_points=raw.get("key_points", []),
        summary=raw.get("summary", ""),
        query_terms=list({item.get("query", "") for item in items if item.get("query")}),
        raw_results=[{
            "title": item.get("title", ""),
            "snippet": item.get("snippet", "")[:300],
            "url": item.get("url", ""),
            "source": item.get("source", ""),
        } for item in items],
        llm_raw_response=raw,
    )

    db.add(sentiment)
    await db.commit()

    logger.info(
        f"Search sentiment analyzed: score={score:+.2f} "
        f"({raw.get('sentiment', 'neutral')}) "
        f"from {len(items)} results "
        f"[B:{raw.get('bullish_count', 0)} N:{raw.get('neutral_count', 0)} "
        f"S:{raw.get('bearish_count', 0)}]"
    )
    return sentiment


async def get_search_sentiment_score(db: AsyncSession, hours: int = 12) -> float:
    """获取最近N小时搜索舆情平均分。返回 [-1, 1]。

    指数衰减加权（半衰期 6 小时），越新的搜索结果权重越高。
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(SearchSentiment)
        .where(SearchSentiment.captured_at >= since)
        .order_by(SearchSentiment.captured_at.desc())
        .limit(10)
    )
    records = result.scalars().all()

    if not records:
        return 0.0

    now = datetime.utcnow()
    total_weight = 0.0
    weighted_sum = 0.0

    for r in records:
        age_hours = (now - r.captured_at).total_seconds() / 3600
        weight = 2 ** (-age_hours / 6)  # 半衰期 6 小时
        weighted_sum += (r.sentiment_score or 0.0) * weight
        total_weight += weight

    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0
