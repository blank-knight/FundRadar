"""Crawler orchestrator — runs all crawlers, writes CrawlLog, persists to DB."""
import logging
import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crawler.xueqiu import XueqiuCrawler
from app.crawler.news import NewsCrawler
from app.crawler.fund_nav import FundNavCrawler, TRACKED_INDICES
from app.models.models import Blogger, Prediction, News, MarketData, CrawlLog
from app.core.config import settings

logger = logging.getLogger(__name__)


async def _write_crawl_log(
    db: AsyncSession,
    crawler_name: str,
    status: str,
    fetched: int,
    saved: int,
    skipped: int,
    duration: float,
    error: str | None = None,
    snapshot: dict | None = None,
) -> None:
    log = CrawlLog(
        crawler_name=crawler_name,
        run_at=datetime.utcnow(),
        status=status,
        items_fetched=fetched,
        items_saved=saved,
        items_skipped=skipped,
        duration_seconds=round(duration, 2),
        error_message=error,
        raw_snapshot=snapshot,
    )
    db.add(log)
    await db.commit()


async def run_xueqiu_crawl(db: AsyncSession) -> dict:
    """Crawl Xueqiu bloggers and save new posts."""
    t0 = time.time()
    saved_posts = 0
    skipped = 0
    fetched = 0
    snapshot = {"bloggers": []}
    error_msg = None

    try:
        # 从数据库读取所有启用的雪球博主
        db_bloggers_result = await db.execute(
            select(Blogger).where(
                Blogger.platform == "xueqiu",
                Blogger.is_active == True,
            )
        )
        db_bloggers = db_bloggers_result.scalars().all()

        async with XueqiuCrawler(cookie=getattr(settings, "XUEQIU_COOKIE", "")) as crawler:
            for blogger in db_bloggers:
                uid = blogger.platform_user_id

                posts = await crawler.get_user_posts(uid, count=10)
                fetched += len(posts)
                blogger_saved = 0
                for post in posts:
                    exists = await db.execute(
                        select(Prediction).where(Prediction.post_url == post["post_url"])
                    )
                    if exists.scalar_one_or_none():
                        skipped += 1
                        continue
                    pred = Prediction(
                        blogger_id=blogger.id,
                        post_url=post["post_url"],
                        post_content=post["post_content"],
                        post_time=post["post_time"],
                        raw_data=post["raw_data"],
                    )
                    db.add(pred)
                    saved_posts += 1
                    blogger_saved += 1

                snapshot["bloggers"].append({
                    "username": blogger.name or blogger.platform_user_id,
                    "uid": uid,
                    "fetched": len(posts),
                    "saved": blogger_saved,
                })

            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Xueqiu crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "xueqiu", status, fetched, saved_posts, skipped, duration, error_msg, snapshot)
    logger.info(f"Xueqiu crawl done: fetched={fetched} saved={saved_posts} skipped={skipped}")
    return {"saved_posts": saved_posts, "skipped": skipped, "fetched": fetched}


async def run_news_crawl(db: AsyncSession) -> dict:
    """Crawl financial news and save new articles."""
    t0 = time.time()
    saved = 0
    skipped = 0
    fetched = 0
    snapshot: dict = {}
    error_msg = None

    try:
        async with NewsCrawler() as crawler:
            articles = await crawler.get_all_news(count_each=30)
            fetched = len(articles)
            snapshot = {"sources": {}}
            for article in articles:
                src = article.get("source", "unknown")
                snapshot["sources"][src] = snapshot["sources"].get(src, 0) + 1
                if not article.get("url") or not article.get("publish_time"):
                    skipped += 1
                    continue
                exists = await db.execute(
                    select(News).where(News.url == article["url"])
                )
                if exists.scalar_one_or_none():
                    skipped += 1
                    continue
                news = News(
                    source=article["source"],
                    title=article["title"],
                    url=article["url"],
                    publish_time=article["publish_time"],
                    summary=article.get("summary"),
                )
                db.add(news)
                saved += 1
            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"News crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "news", status, fetched, saved, skipped, duration, error_msg, snapshot)
    logger.info(f"News crawl done: fetched={fetched} saved={saved} skipped={skipped}")
    return {"saved_articles": saved, "skipped": skipped, "fetched": fetched}


async def run_market_data_crawl(db: AsyncSession) -> dict:
    """Crawl index daily data and save to market_data."""
    t0 = time.time()
    saved = 0
    skipped = 0
    fetched = 0
    snapshot: dict = {"indices": []}
    error_msg = None

    try:
        async with FundNavCrawler() as crawler:
            for idx in TRACKED_INDICES:
                if idx["symbol"] == "NDX":
                    continue
                records = await crawler.get_index_daily(idx["em_code"], days=5)
                fetched += len(records)
                idx_saved = 0
                for rec in records:
                    exists = await db.execute(
                        select(MarketData).where(
                            MarketData.symbol == idx["symbol"],
                            MarketData.trade_date == rec["trade_date"],
                        )
                    )
                    if exists.scalar_one_or_none():
                        skipped += 1
                        continue
                    md = MarketData(
                        symbol=idx["symbol"],
                        name=idx["name"],
                        trade_date=rec["trade_date"],
                        open_price=rec["open_price"],
                        high_price=rec["high_price"],
                        low_price=rec["low_price"],
                        close_price=rec["close_price"],
                        change_pct=rec["change_pct"],
                        volume=rec.get("volume"),
                    )
                    db.add(md)
                    saved += 1
                    idx_saved += 1
                snapshot["indices"].append({"symbol": idx["symbol"], "fetched": len(records), "saved": idx_saved})
            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Market data crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "market_data", status, fetched, saved, skipped, duration, error_msg, snapshot)
    logger.info(f"Market data crawl done: fetched={fetched} saved={saved} skipped={skipped}")
    return {"saved_records": saved, "skipped": skipped, "fetched": fetched}


async def run_signal_feedback(db: AsyncSession) -> dict:
    """
    每日反馈调节任务：
    1. 验证昨天的信号
    2. 检查是否需要触发复盘
    返回执行摘要。
    """
    from app.services.signal_feedback import verify_daily_signal, check_and_trigger_review
    from app.crawler.fund_nav import TRACKED_INDICES

    today = datetime.utcnow()
    results = {}

    for idx in TRACKED_INDICES:
        symbol = idx["symbol"]
        if symbol == "NDX":
            continue  # 暂不验证海外指数

        verification = await verify_daily_signal(db, today, symbol)
        review = await check_and_trigger_review(db, symbol)

        results[symbol] = {
            "verified": verification is not None,
            "correct": verification.is_correct if verification else None,
            "review_triggered": review is not None,
            "review_id": review.id if review else None,
        }
        if verification:
            logger.info(
                f"[feedback] {symbol}: predicted={verification.predicted_signal} "
                f"actual={verification.actual_change_pct:+.2f}% correct={verification.is_correct}"
            )
        if review:
            logger.warning(f"[feedback] {symbol}: review triggered, id={review.id}")

    return results
