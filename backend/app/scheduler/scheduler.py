"""APScheduler 调度器 — 随 FastAPI 启动/关闭。

所有时间以 Asia/Shanghai（UTC+8）为准。
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.jobs import (
    job_market_data,
    job_xueqiu_crawl,
    job_weibo_crawl,
    job_sentiment_crawl,
    job_news_crawl,
    job_verify_blogger_predictions,
    job_generate_signal,
    job_push_signal,
    job_signal_feedback,
    job_update_nav,
    job_quant_crawl,
    job_export_frontend,
)

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Shanghai"

scheduler = AsyncIOScheduler(timezone=TIMEZONE)


def setup_scheduler() -> AsyncIOScheduler:
    """注册所有定时任务，返回 scheduler 实例（未启动）。"""

    # 09:35 — 抓昨日收盘行情
    scheduler.add_job(
        job_market_data,
        CronTrigger(hour=9, minute=35, timezone=TIMEZONE),
        id="market_data_morning",
        name="行情数据（早）",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 10:00 — 爬雪球博主帖子 + 解析预测
    scheduler.add_job(
        job_xueqiu_crawl,
        CronTrigger(hour=10, minute=0, timezone=TIMEZONE),
        id="xueqiu_crawl",
        name="雪球博主爬取",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 10:15 — 爬微博大V帖子 + 解析预测
    scheduler.add_job(
        job_weibo_crawl,
        CronTrigger(hour=10, minute=15, timezone=TIMEZONE),
        id="weibo_crawl",
        name="微博大V爬取",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 10:30 — 抓新闻 + 情绪分析
    scheduler.add_job(
        job_news_crawl,
        CronTrigger(hour=10, minute=30, timezone=TIMEZONE),
        id="news_crawl",
        name="财经新闻爬取",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 10:45 — 爬散户情绪数据（akshare 微博NLP + 东财评论）
    scheduler.add_job(
        job_sentiment_crawl,
        CronTrigger(hour=10, minute=45, timezone=TIMEZONE),
        id="sentiment_crawl",
        name="散户情绪爬取",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 15:30 — 收盘后补抓当日行情
    scheduler.add_job(
        job_market_data,
        CronTrigger(hour=15, minute=30, timezone=TIMEZONE),
        id="market_data_close",
        name="行情数据（收盘）",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 15:35 — 采集量化数据（北向/资金流/行业轮动/龙虎榜/估值）
    # 必须在 16:00 信号生成前完成
    scheduler.add_job(
        job_quant_crawl,
        CronTrigger(hour=15, minute=35, timezone=TIMEZONE),
        id="quant_crawl",
        name="量化数据采集",
        replace_existing=True,
        misfire_grace_time=600,
    )

    # 15:35 — 验证博主预测
    scheduler.add_job(
        job_verify_blogger_predictions,
        CronTrigger(hour=15, minute=35, timezone=TIMEZONE),
        id="blogger_verify",
        name="博主预测验证",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 16:00 — 生成每日信号
    scheduler.add_job(
        job_generate_signal,
        CronTrigger(hour=16, minute=0, timezone=TIMEZONE),
        id="generate_signal",
        name="生成每日信号",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 16:30 — 推送信号给用户
    scheduler.add_job(
        job_push_signal,
        CronTrigger(hour=16, minute=30, timezone=TIMEZONE),
        id="push_signal",
        name="推送每日信号",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 16:45 — 信号反馈验证 + 复盘检查
    scheduler.add_job(
        job_signal_feedback,
        CronTrigger(hour=16, minute=45, timezone=TIMEZONE),
        id="signal_feedback",
        name="信号反馈复盘",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 17:00 — 更新持仓净值
    scheduler.add_job(
        job_update_nav,
        CronTrigger(hour=17, minute=0, timezone=TIMEZONE),
        id="update_nav",
        name="持仓净值更新",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # 17:05 — 导出前端数据 → git push → Vercel 自动重建
    # 在所有数据采集/信号生成/净值更新之后，确保前端拿到当天最新数据
    scheduler.add_job(
        job_export_frontend,
        CronTrigger(hour=17, minute=5, timezone=TIMEZONE),
        id="export_frontend",
        name="前端数据导出+推送",
        replace_existing=True,
        misfire_grace_time=600,
    )

    logger.info(f"[scheduler] {len(scheduler.get_jobs())} jobs registered")
    return scheduler
