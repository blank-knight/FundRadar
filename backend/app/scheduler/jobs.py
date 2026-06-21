"""定时任务定义 — 每个任务对应一个独立函数，由 scheduler.py 注册。

任务时间表（北京时间，UTC+8）：
  09:35  市场数据抓取（开盘后拿昨日收盘数据）
  10:00  博主预测爬取 + LLM 解析
  10:15  微博大V爬取
  10:30  新闻抓取 + 情绪分析
  10:45  散户情绪爬取
  15:30  收盘后再次抓取行情
  15:35  量化数据采集 + 博主预测验证
  16:00  生成每日信号
  16:30  推送每日信号给用户
  16:45  T+1 验证 + 复盘检查
  17:00  净值更新
"""

import asyncio
import functools
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 各任务独立超时（秒）── 单步超时不阻塞后续步骤 ──
JOB_TIMEOUTS = {
    "market_data": 60,
    "xueqiu": 120,       # 博主爬取+LLM解析，耗时长
    "weibo": 90,
    "news": 120,          # 新闻爬取+LLM分析
    "sentiment": 60,     # 散户情绪（akshare）
    "quant": 90,          # 量化数据（多个HTTP源）
    "blogger_verify": 60,
    "generate_signal": 60,
    "push_signal": 30,
    "signal_feedback": 60,
    "update_nav": 30,
    "export_frontend": 120,  # 导出+git push+Vercel重建
    "portfolio_advisor": 300,  # LLM分析持仓建议（多次API调用，耗时）
}


def with_timeout(job_name: str):
    """装饰器：给 job 加独立超时+异常隔离。

    - 超时：记录日志，不抛异常，不影响其他 job
    - 异常：捕获记录，不传播到 scheduler
    """
    timeout_sec = JOB_TIMEOUTS.get(job_name, 60)

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            t0 = datetime.utcnow()
            try:
                result = await asyncio.wait_for(
                    fn(*args, **kwargs),
                    timeout=timeout_sec,
                )
                elapsed = (datetime.utcnow() - t0).total_seconds()
                logger.info(f"[job:{job_name}] ✅ done in {elapsed:.1f}s")
                return result
            except asyncio.TimeoutError:
                elapsed = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    f"[job:{job_name}] ⏰ TIMEOUT after {elapsed:.0f}s "
                    f"(limit={timeout_sec}s) — skipped, next jobs unaffected"
                )
            except Exception as e:
                elapsed = (datetime.utcnow() - t0).total_seconds()
                logger.error(
                    f"[job:{job_name}] ❌ FAILED after {elapsed:.1f}s: {e}",
                    exc_info=True,
                )
        return wrapper
    return decorator


@with_timeout("market_data")
async def job_market_data():
    """抓取指数行情数据。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_market_data_crawl
    async with AsyncSessionLocal() as db:
        result = await run_market_data_crawl(db)
    logger.info(f"[scheduler] market_data: {result}")


@with_timeout("xueqiu")
async def job_xueqiu_crawl():
    """爬取博主帖子（微博+东财分析师）+ LLM 解析预测方向。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_xueqiu_crawl
    from app.analyzer.prediction_parser import parse_unparsed_predictions
    async with AsyncSessionLocal() as db:
        crawl_result = await run_xueqiu_crawl(db)
        parse_result = await parse_unparsed_predictions(db)
    logger.info(f"[scheduler] xueqiu: crawl={crawl_result} parse={parse_result}")


@with_timeout("weibo")
async def job_weibo_crawl():
    """爬取微博大V帖子 + LLM 解析预测方向。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_weibo_crawl
    from app.analyzer.prediction_parser import parse_unparsed_predictions
    async with AsyncSessionLocal() as db:
        crawl_result = await run_weibo_crawl(db)
        parse_result = await parse_unparsed_predictions(db)
    logger.info(f"[scheduler] weibo: crawl={crawl_result} parse={parse_result}")


@with_timeout("sentiment")
async def job_sentiment_crawl():
    """爬取散户情绪数据（akshare 微博NLP + 东财评论）。

    注意: akshare stock_js_weibo_report 底层调 jin10 API，
    在 WSL+Clash 环境下可能 SSL EOF。超时保护会跳过这一步。
    """
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_sentiment_crawl
    async with AsyncSessionLocal() as db:
        result = await run_sentiment_crawl(db)
    logger.info(f"[scheduler] sentiment: {result}")


@with_timeout("quant")
async def job_quant_crawl():
    """采集量化数据快照（北向资金/行业轮动/指数资金流/龙虎榜/估值）。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_quant_crawl
    async with AsyncSessionLocal() as db:
        result = await run_quant_crawl(db)
    logger.info(f"[scheduler] quant: {result}")


@with_timeout("news")
async def job_news_crawl():
    """抓取财经新闻 + LLM 情绪分析。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_news_crawl
    from app.analyzer.news_analyzer import analyze_unanalyzed_news
    async with AsyncSessionLocal() as db:
        crawl_result = await run_news_crawl(db)
        analyze_result = await analyze_unanalyzed_news(db)
    logger.info(f"[scheduler] news: crawl={crawl_result} analyze={analyze_result}")


@with_timeout("blogger_verify")
async def job_verify_blogger_predictions():
    """T+1 验证博主预测准确率。"""
    from app.core.database import AsyncSessionLocal
    from app.analyzer.blogger_scorer import verify_predictions
    async with AsyncSessionLocal() as db:
        result = await verify_predictions(db, datetime.utcnow())
    logger.info(f"[scheduler] blogger_verify: {result}")


@with_timeout("generate_signal")
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


@with_timeout("push_signal")
async def job_push_signal():
    """推送每日信号给所有绑定用户。"""
    from app.core.database import AsyncSessionLocal
    from app.services.signal_pusher import push_daily_signal
    async with AsyncSessionLocal() as db:
        result = await push_daily_signal(db)
    logger.info(f"[scheduler] push_signal: {result}")


@with_timeout("signal_feedback")
async def job_signal_feedback():
    """T+1 验证系统信号 + 触发复盘（如需要）。"""
    from app.core.database import AsyncSessionLocal
    from app.crawler.orchestrator import run_signal_feedback
    from app.services.signal_feedback import push_pending_reviews
    async with AsyncSessionLocal() as db:
        feedback_result = await run_signal_feedback(db)
        push_result = await push_pending_reviews(db)
    logger.info(f"[scheduler] signal_feedback: {feedback_result} push={push_result}")


@with_timeout("update_nav")
async def job_update_nav():
    """更新持仓净值（场外基金下午公布）。"""
    from app.core.database import AsyncSessionLocal
    from app.services.nav_updater import update_all_portfolio_nav
    async with AsyncSessionLocal() as db:
        result = await update_all_portfolio_nav(db)
    logger.info(f"[scheduler] nav_update: {result}")


@with_timeout("export_frontend")
async def job_export_frontend():
    """导出前端数据 → git push → Vercel 自动重建。

    在所有数据采集/信号生成/净值更新之后运行（17:05），
    确保前端看到的是当天最新数据。
    VPN 环境下内网穿透不可用，用静态 JSON 快照 + Vercel 自动重建替代。
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[3]  # backend/app/scheduler/ → project root
    script = project_root / "scripts" / "export_frontend.py"
    venv_python = project_root / "backend" / ".venv" / "bin" / "python3"

    if not script.exists():
        logger.error(f"[scheduler] export script not found: {script}")
        return

    proc = await asyncio.create_subprocess_exec(
        str(venv_python), str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(project_root),
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode() if stdout else ""
    if proc.returncode == 0:
        logger.info(f"[scheduler] frontend_export done:\n{output[-500:]}")
    else:
        logger.error(f"[scheduler] frontend_export FAILED (exit={proc.returncode}):\n{output[-500:]}")


@with_timeout("portfolio_advisor")
async def job_portfolio_advisor():
    """持仓顾问 — LLM分析持仓+新闻，生成操作建议+赛道提醒。

    输出 portfolio-advice.json（前端持仓页面数据源）。
    注意: 这个文件是 LLM 生成的，不是 DB 导出，不能在 export_frontend 中覆盖。
    """
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[3]
    script = project_root / "backend" / "portfolio_advisor.py"
    venv_python = project_root / "backend" / ".venv" / "bin" / "python3"

    if not script.exists():
        logger.error(f"[scheduler] portfolio_advisor script not found: {script}")
        return

    proc = await asyncio.create_subprocess_exec(
        str(venv_python), str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(project_root / "backend"),
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode() if stdout else ""
    if proc.returncode == 0:
        logger.info(f"[scheduler] portfolio_advisor done:\n{output[-500:]}")
    else:
        logger.error(f"[scheduler] portfolio_advisor FAILED (exit={proc.returncode}):\n{output[-500:]}")


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
