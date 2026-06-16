"""Crawler orchestrator — runs all crawlers, writes CrawlLog, persists to DB."""
import logging
import time
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.crawler.xueqiu import XueqiuCrawler
from app.crawler.weibo import WeiboCrawler, DEFAULT_WEIBO_KOLS
from app.crawler.sentiment import SentimentCrawler
from app.crawler.news import NewsCrawler
from app.crawler.fund_nav import FundNavCrawler, TRACKED_INDICES
from app.models.models import (
    Blogger, Prediction, News, MarketData, CrawlLog,
    RetailSentiment,
)
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


async def run_weibo_crawl(db: AsyncSession) -> dict:
    """爬取微博大V帖子并存入 predictions 表。"""
    t0 = time.time()
    saved_posts = 0
    skipped = 0
    fetched = 0
    snapshot = {"kols": []}
    error_msg = None

    try:
        # 从数据库读已关注的微博博主，没有则用默认
        db_bloggers_result = await db.execute(
            select(Blogger).where(
                Blogger.platform == "weibo",
                Blogger.is_active == True,
            )
        )
        db_bloggers = db_bloggers_result.scalars().all()

        # 如果DB没有微博博主，用默认KOL列表
        kols = []
        if db_bloggers:
            for b in db_bloggers:
                kols.append({"uid": b.platform_user_id, "username": b.username})
        else:
            kols = DEFAULT_WEIBO_KOLS

        async with WeiboCrawler() as crawler:
            for kol in kols:
                uid = kol["uid"]
                posts = await crawler.get_user_timeline(uid, page=1)
                fetched += len(posts)
                kol_saved = 0

                for post in posts:
                    if not post.get("post_url") or not post.get("content"):
                        skipped += 1
                        continue

                    # 检查是否已存在（微博和雪球共用 predictions 表）
                    exists = await db.execute(
                        select(Prediction).where(Prediction.post_url == post["post_url"])
                    )
                    if exists.scalar_one_or_none():
                        skipped += 1
                        continue

                    # 找到或创建微博博主记录
                    blogger = None
                    if db_bloggers:
                        for b in db_bloggers:
                            if b.platform_user_id == uid:
                                blogger = b
                                break

                    if not blogger:
                        blogger = Blogger(
                            platform="weibo",
                            platform_user_id=uid,
                            username=kol.get("username", ""),
                        )
                        db.add(blogger)
                        await db.flush()

                    pred = Prediction(
                        blogger_id=blogger.id,
                        post_url=post["post_url"],
                        post_content=post["content"],
                        post_time=post["post_time"],
                        raw_data=post.get("raw_data"),
                    )
                    db.add(pred)
                    saved_posts += 1
                    kol_saved += 1

                snapshot["kols"].append({
                    "username": kol.get("username", uid),
                    "uid": uid,
                    "fetched": len(posts),
                    "saved": kol_saved,
                })

            await db.commit()
        status = "success"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Weibo crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "weibo", status, fetched, saved_posts, skipped, duration, error_msg, snapshot)
    logger.info(f"Weibo crawl done: fetched={fetched} saved={saved_posts} skipped={skipped}")
    return {"saved_posts": saved_posts, "skipped": skipped, "fetched": fetched}


async def run_sentiment_crawl(db: AsyncSession) -> dict:
    """爬取散户情绪数据（akshare 微博NLP + 东财评论），存入 retail_sentiments 表。"""
    t0 = time.time()
    saved = 0
    fetched = 0
    snapshot: dict = {"sources": {}}
    error_msg = None

    try:
        async with SentimentCrawler() as crawler:
            now = datetime.utcnow()

            # 1. 微博舆情
            weibo = await crawler.get_weibo_sentiment(time_period="CNHOUR12")
            if weibo:
                fetched += 1
                rs = RetailSentiment(
                    source="weibo_nlp",
                    symbol="MARKET",
                    sentiment_score=weibo["sentiment_score"],
                    bullish_ratio=weibo["bullish_ratio"],
                    bearish_ratio=weibo["bearish_ratio"],
                    raw_data=weibo["raw_data"],
                    captured_at=now,
                )
                db.add(rs)
                saved += 1
                snapshot["sources"]["weibo_nlp"] = {
                    "score": weibo["sentiment_score"],
                    "bullish": weibo["bullish_ratio"],
                }

            # 2. 东财评论
            em = await crawler.get_em_comment_sentiment()
            if em:
                fetched += 1
                rs = RetailSentiment(
                    source="eastmoney_comment",
                    symbol="MARKET",
                    sentiment_score=em["sentiment_score"],
                    bullish_ratio=em["bullish_ratio"],
                    bearish_ratio=em["bearish_ratio"],
                    raw_data=em["raw_data"],
                    captured_at=now,
                )
                db.add(rs)
                saved += 1
                snapshot["sources"]["eastmoney_comment"] = {
                    "score": em["sentiment_score"],
                    "bullish": em["bullish_ratio"],
                }

            await db.commit()
        status = "success" if saved > 0 else "partial"
    except Exception as e:
        error_msg = str(e)
        status = "failed"
        logger.error(f"Sentiment crawl error: {e}")

    duration = time.time() - t0
    await _write_crawl_log(db, "sentiment", status, fetched, saved, 0, duration, error_msg, snapshot)
    logger.info(f"Sentiment crawl done: fetched={fetched} saved={saved}")
    return {"saved": saved, "fetched": fetched, "sources": snapshot.get("sources", {})}


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
