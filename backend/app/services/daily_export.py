"""每日数据导出 — 把当天所有抓取数据导出为 JSON 文件，便于人工审查。

导出目录结构：
~/clawd/fund-radar/data/
  YYYY-MM-DD/
    predictions.json      博主帖子 + LLM解析结果
    verifications.json    T+1验证结果
    news.json             新闻 + 情感分析
    market_data.json      指数行情
    crawl_logs.json       爬虫运行日志
    daily_signal.json     当日综合信号
"""
import json
import logging
import os
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Prediction, PredictionVerification, News,
    MarketData, CrawlLog, DailySignal, Blogger,
)

logger = logging.getLogger(__name__)

DATA_ROOT = Path.home() / "clawd" / "fund-radar" / "data"


def _json_serial(obj: Any) -> str:
    """JSON serializer for datetime objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def _dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_serial)
    logger.info(f"Exported {len(data) if isinstance(data, list) else 1} records → {path}")


async def export_daily(db: AsyncSession, target_date: date | None = None) -> Path:
    """导出指定日期（默认今天）的所有数据到 JSON 文件。"""
    if target_date is None:
        target_date = date.today()

    day_dir = DATA_ROOT / target_date.strftime("%Y-%m-%d")
    day_start = datetime.combine(target_date, datetime.min.time())
    day_end = day_start + timedelta(days=1)

    # 1. 博主帖子 + LLM解析
    result = await db.execute(
        select(Prediction)
        .options(selectinload(Prediction.blogger), selectinload(Prediction.verification))
        .where(Prediction.post_time >= day_start, Prediction.post_time < day_end)
        .order_by(Prediction.post_time.desc())
    )
    predictions = result.scalars().all()
    _dump(day_dir / "predictions.json", [
        {
            "id": p.id,
            "blogger": {
                "id": p.blogger.id,
                "username": p.blogger.username,
                "platform": p.blogger.platform,
                "accuracy_score": p.blogger.accuracy_score,
            },
            "post_url": p.post_url,
            "post_content": p.post_content,
            "post_time": p.post_time,
            "is_prediction": p.is_prediction,
            "predicted_direction": p.predicted_direction,
            "predicted_target": p.predicted_target,
            "confidence": p.confidence,
            "llm_reasoning": p.llm_reasoning,
            "llm_raw_response": p.llm_raw_response,
            "verification": {
                "verification_date": p.verification.verification_date,
                "actual_change_pct": p.verification.actual_change_pct,
                "is_correct": p.verification.is_correct,
            } if p.verification else None,
            "raw_data": p.raw_data,
        }
        for p in predictions
    ])

    # 2. T+1 验证结果（验证日期 = target_date）
    result = await db.execute(
        select(PredictionVerification)
        .options(selectinload(PredictionVerification.prediction))
        .where(
            PredictionVerification.verification_date >= day_start,
            PredictionVerification.verification_date < day_end,
        )
    )
    verifications = result.scalars().all()
    _dump(day_dir / "verifications.json", [
        {
            "id": v.id,
            "prediction_id": v.prediction_id,
            "verification_date": v.verification_date,
            "actual_change_pct": v.actual_change_pct,
            "is_correct": v.is_correct,
            "prediction_direction": v.prediction.predicted_direction if v.prediction else None,
            "prediction_target": v.prediction.predicted_target if v.prediction else None,
        }
        for v in verifications
    ])

    # 3. 新闻
    result = await db.execute(
        select(News)
        .where(News.publish_time >= day_start, News.publish_time < day_end)
        .order_by(News.publish_time.desc())
    )
    news_list = result.scalars().all()
    _dump(day_dir / "news.json", [
        {
            "id": n.id,
            "source": n.source,
            "title": n.title,
            "url": n.url,
            "publish_time": n.publish_time,
            "summary": n.summary,
            "sentiment_score": n.sentiment_score,
            "sentiment_label": n.sentiment_label,
            "llm_analysis": n.llm_analysis,
            "llm_raw_response": n.llm_raw_response,
        }
        for n in news_list
    ])

    # 4. 指数行情
    result = await db.execute(
        select(MarketData)
        .where(MarketData.trade_date >= day_start, MarketData.trade_date < day_end)
    )
    market = result.scalars().all()
    _dump(day_dir / "market_data.json", [
        {
            "symbol": m.symbol,
            "name": m.name,
            "trade_date": m.trade_date,
            "open": m.open_price,
            "high": m.high_price,
            "low": m.low_price,
            "close": m.close_price,
            "change_pct": m.change_pct,
            "volume": m.volume,
        }
        for m in market
    ])

    # 5. 爬虫日志
    result = await db.execute(
        select(CrawlLog)
        .where(CrawlLog.run_at >= day_start, CrawlLog.run_at < day_end)
        .order_by(CrawlLog.run_at)
    )
    logs = result.scalars().all()
    _dump(day_dir / "crawl_logs.json", [
        {
            "id": l.id,
            "crawler_name": l.crawler_name,
            "run_at": l.run_at,
            "status": l.status,
            "items_fetched": l.items_fetched,
            "items_saved": l.items_saved,
            "items_skipped": l.items_skipped,
            "duration_seconds": l.duration_seconds,
            "error_message": l.error_message,
        }
        for l in logs
    ])

    # 6. 当日综合信号
    result = await db.execute(
        select(DailySignal)
        .where(DailySignal.signal_date >= day_start, DailySignal.signal_date < day_end)
    )
    signal = result.scalar_one_or_none()
    _dump(day_dir / "daily_signal.json", {
        "signal_date": signal.signal_date if signal else target_date,
        "target_symbol": signal.target_symbol if signal else None,
        "final_signal": signal.final_signal if signal else None,
        "confidence": signal.confidence if signal else None,
        "blogger_consensus_score": signal.blogger_consensus_score if signal else None,
        "news_sentiment_score": signal.news_sentiment_score if signal else None,
        "reasoning": signal.reasoning if signal else None,
        "participating_bloggers": signal.participating_bloggers if signal else 0,
        "analyzed_news_count": signal.analyzed_news_count if signal else 0,
    } if signal else {"signal_date": target_date, "status": "not_generated_yet"})

    logger.info(f"Daily export complete → {day_dir}")
    return day_dir
