"""定时任务定义 — 每个任务对应一个独立函数，由 scheduler.py 注册。

任务时间表（北京时间，UTC+8）：
  09:35  市场数据抓取（开盘后拿昨日收盘数据）
  10:00  博主预测爬取 + LLM 解析
  10:30  新闻抓取 + 情绪分析
  15:30  收盘后再次抓取行情（确保当日数据完整）
  16:00  生成每日信号
  16:30  推送每日信号给用户
  16:45  T+1 验证 + 复盘检查
  17:00  净值更新（基金场外净值一般下午公布）
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def job_market_data():
    """抓取指数行情数据。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_market_data_crawl
    async with AsyncSessionLocal() as db:
        result = await run_market_data_crawl(db)
    logger.info(f"[scheduler] market_data: {result}")


async def job_xueqiu_crawl():
    """爬取雪球博主帖子 + LLM 解析预测方向。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_xueqiu_crawl
    from app.analyzer.prediction_parser import parse_unparsed_predictions
    async with AsyncSessionLocal() as db:
        crawl_result = await run_xueqiu_crawl(db)
        parse_result = await parse_unparsed_predictions(db)
    logger.info(f"[scheduler] xueqiu: crawl={crawl_result} parse={parse_result}")


async def job_weibo_crawl():
    """爬取微博大V帖子 + LLM 解析预测方向。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_weibo_crawl
    from app.analyzer.prediction_parser import parse_unparsed_predictions
    async with AsyncSessionLocal() as db:
        crawl_result = await run_weibo_crawl(db)
        parse_result = await parse_unparsed_predictions(db)
    logger.info(f"[scheduler] weibo: crawl={crawl_result} parse={parse_result}")


async def job_sentiment_crawl():
    """爬取散户情绪数据（akshare 微博NLP + 东财评论）。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_sentiment_crawl
    async with AsyncSessionLocal() as db:
        result = await run_sentiment_crawl(db)
    logger.info(f"[scheduler] sentiment: {result}")


async def job_news_crawl():
    """抓取财经新闻 + LLM 情绪分析。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_news_crawl
    from app.analyzer.news_analyzer import analyze_unanalyzed_news
    async with AsyncSessionLocal() as db:
        crawl_result = await run_news_crawl(db)
        analyze_result = await analyze_unanalyzed_news(db)
    logger.info(f"[scheduler] news: crawl={crawl_result} analyze={analyze_result}")


async def job_verify_blogger_predictions():
    """T+1 验证博主预测准确率。"""
    from app.core.database import AsyncSessionLocal
    from app.analyzer.blogger_scorer import verify_predictions
    async with AsyncSessionLocal() as db:
        result = await verify_predictions(db, datetime.utcnow())
    logger.info(f"[scheduler] blogger_verify: {result}")


async def job_generate_signal():
    """生成今日综合信号。"""
    from app.core.database import AsyncSessionLocal
    from app.analyzer.signal_generator import generate_daily_signal
    from app.crawler.fund_nav import TRACKED_INDICES
    async with AsyncSessionLocal() as db:
        for idx in TRACKED_INDICES:
            if idx["symbol"] == "NDX":
                continue
            result = await generate_daily_signal(db, idx["symbol"], idx["name"])
            if result:
                logger.info(f"[scheduler] signal generated: {idx['symbol']} → {result.final_signal}")


async def job_push_signal():
    """推送每日信号给所有绑定用户。"""
    from app.core.database import AsyncSessionLocal
    from app.services.signal_pusher import push_daily_signal
    async with AsyncSessionLocal() as db:
        result = await push_daily_signal(db)
    logger.info(f"[scheduler] push_signal: {result}")


async def job_signal_feedback():
    """T+1 验证系统信号 + 触发复盘（如需要）。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_signal_feedback
    from app.services.signal_feedback import push_pending_reviews
    async with AsyncSessionLocal() as db:
        feedback_result = await run_signal_feedback(db)
        push_result = await push_pending_reviews(db)
    logger.info(f"[scheduler] signal_feedback: {feedback_result} push={push_result}")


async def job_update_nav():
    """更新持仓净值（场外基金下午公布）。"""
    from app.core.database import AsyncSessionLocal
    from app.services.nav_updater import update_all_portfolio_nav
    async with AsyncSessionLocal() as db:
        result = await update_all_portfolio_nav(db)
    logger.info(f"[scheduler] nav_update: {result}")


async def start_polling():
    """长轮询接收 Telegram 消息，随服务启动持续运行。"""
    from app.core.database import AsyncSessionLocal
    from app.services.telegram_bot import bot
    from app.services.bot_handler import handle_update

    logger.info("[polling] Telegram polling started")
    offset = 0
    while True:
        try:
            updates = await bot.get_updates(offset=offset, timeout=30)
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    async with AsyncSessionLocal() as db:
                        await handle_update(update, db)
                except Exception as e:
                    logger.error(f"[polling] handle_update error: {e}")
        except Exception as e:
            logger.error(f"[polling] get_updates error: {e}")
            import asyncio
            await asyncio.sleep(5)
