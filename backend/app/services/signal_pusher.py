"""每日信号推送 — 格式化消息并推送给所有绑定用户。"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import DailySignal, User
from app.services.telegram_bot import bot

logger = logging.getLogger(__name__)

# 信号对应的 emoji 和中文
SIGNAL_META = {
    "strong_buy":  {"emoji": "🚀", "label": "强烈买入", "color": "📗"},
    "buy":         {"emoji": "📈", "label": "买入",     "color": "🟢"},
    "hold":        {"emoji": "⏸",  "label": "持有观望", "color": "🟡"},
    "sell":        {"emoji": "📉", "label": "减仓",     "color": "🔴"},
    "strong_sell": {"emoji": "⚠️", "label": "强烈减仓", "color": "📕"},
}


def format_signal_message(signal: DailySignal, is_premium: bool = True) -> str:
    """格式化每日信号为 Telegram HTML 消息。"""
    meta = SIGNAL_META.get(signal.final_signal, {"emoji": "❓", "label": "未知", "color": "⬜"})
    date_str = signal.signal_date.strftime("%Y年%m月%d日")

    # 博主共识方向文字
    bs = signal.blogger_consensus_score
    ns = signal.news_sentiment_score
    blogger_dir = "偏多 📈" if bs > 0.1 else "偏空 📉" if bs < -0.1 else "中性 ➡️"
    news_dir = "偏正面 😊" if ns > 0.1 else "偏负面 😟" if ns < -0.1 else "中性 😐"

    if is_premium:
        msg = (
            f"<b>📊 FundRadar 每日信号 · {date_str}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{meta['color']} <b>今日信号：{meta['emoji']} {meta['label']}</b>\n"
            f"🎯 标的：{signal.target_name}（{signal.target_symbol}）\n"
            f"📐 置信度：{signal.confidence:.1f}%\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<b>数据来源</b>\n"
            f"👥 博主共识：{blogger_dir}（{signal.participating_bloggers} 位博主）\n"
            f"📰 新闻情绪：{news_dir}（{signal.analyzed_news_count} 条新闻）\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<b>分析说明</b>\n"
            f"{signal.reasoning}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<i>⚠️ 本信号仅供参考，不构成投资建议。投资有风险，入市需谨慎。</i>"
        )
    else:
        # 免费版：隐藏详细分析，只显示信号方向
        msg = (
            f"<b>📊 FundRadar 每日信号 · {date_str}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"{meta['color']} <b>今日信号：{meta['emoji']} {meta['label']}</b>\n"
            f"🎯 标的：{signal.target_name}\n\n"
            f"🔒 <i>详细分析（博主共识、新闻情绪、置信度）需升级会员查看</i>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<i>⚠️ 本信号仅供参考，不构成投资建议。</i>"
        )
    return msg


async def push_daily_signal(db: AsyncSession) -> dict:
    """
    推送今日信号给所有绑定了 Telegram 的用户。
    付费用户推送完整版，免费用户推送简版。
    """
    # 找今日信号
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(DailySignal).where(DailySignal.signal_date == today)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        logger.warning("No daily signal found for today, skipping push")
        return {"pushed": 0, "reason": "no_signal"}

    # 找所有绑定了 Telegram 的用户
    result = await db.execute(
        select(User).where(User.telegram_chat_id.isnot(None))
    )
    users = result.scalars().all()

    pushed = 0
    failed = 0
    now = datetime.utcnow()

    for user in users:
        is_premium = (
            user.plan != "free"
            and (user.plan == "lifetime" or (user.plan_expires_at and user.plan_expires_at > now))
        )
        msg = format_signal_message(signal, is_premium=is_premium)
        ok = await bot.send_message(user.telegram_chat_id, msg)
        if ok:
            pushed += 1
        else:
            failed += 1

    logger.info(f"Signal push done: pushed={pushed} failed={failed}")
    return {"pushed": pushed, "failed": failed, "signal": signal.final_signal}
