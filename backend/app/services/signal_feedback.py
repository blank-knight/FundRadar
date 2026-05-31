"""信号反馈调节服务 — T+1 验证 + 自动复盘。

每日定时任务调用流程：
  1. verify_daily_signal()   — 验证昨天信号是否正确
  2. check_and_trigger_review() — 检查是否需要触发复盘
  3. （如触发）run_signal_review() — LLM 深度复盘，推送报告
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_json
from app.models.models import DailySignal, MarketData, SignalVerification, SignalReview

logger = logging.getLogger(__name__)

# 触发复盘的条件
REVIEW_WINDOW_DAYS = 7        # 观察最近N天
REVIEW_MIN_SAMPLES = 3        # 至少有N条验证记录才触发
REVIEW_ERROR_RATE = 0.6       # 错误率超过此值触发复盘（即准确率低于40%）
REVIEW_CONSECUTIVE_ERRORS = 3 # 或者连续N次错误也触发

# 信号方向映射（用于判断对错）
BULLISH_SIGNALS = {"strong_buy", "buy"}
BEARISH_SIGNALS = {"strong_sell", "sell"}


def _signal_to_direction(signal: str) -> str:
    """把信号名映射为方向。"""
    if signal in BULLISH_SIGNALS:
        return "up"
    if signal in BEARISH_SIGNALS:
        return "down"
    return "flat"


def _actual_direction(change_pct: float) -> str:
    if change_pct > 0.3:
        return "up"
    if change_pct < -0.3:
        return "down"
    return "flat"


def _is_correct(predicted_signal: str, actual_change_pct: float) -> bool:
    pred_dir = _signal_to_direction(predicted_signal)
    actual_dir = _actual_direction(actual_change_pct)
    # hold 信号不算对错，跳过
    if pred_dir == "flat":
        return True
    return pred_dir == actual_dir


def _error_magnitude(predicted_signal: str, actual_change_pct: float) -> float:
    """偏差幅度：预测强度（-1~1）与实际涨跌方向的差距。"""
    strength_map = {
        "strong_buy": 1.0, "buy": 0.5, "hold": 0.0,
        "sell": -0.5, "strong_sell": -1.0,
    }
    pred_strength = strength_map.get(predicted_signal, 0.0)
    actual_strength = max(-1.0, min(1.0, actual_change_pct / 3.0))  # 3%涨跌 = 满分
    return round(abs(pred_strength - actual_strength), 4)


async def verify_daily_signal(
    db: AsyncSession,
    trade_date: datetime,
    target_symbol: str = "000300",
) -> SignalVerification | None:
    """
    T+1 验证：拿 trade_date 前一天的 DailySignal，
    对比 trade_date 当天的实际涨跌，写入 SignalVerification。
    """
    prev_day = (trade_date - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # 找昨天的信号
    sig_result = await db.execute(
        select(DailySignal).where(
            DailySignal.signal_date == prev_day,
            DailySignal.target_symbol == target_symbol,
        )
    )
    signal = sig_result.scalar_one_or_none()
    if not signal:
        logger.info(f"No signal found for {prev_day.date()} {target_symbol}, skip verify")
        return None

    # 已验证过就跳过
    existing = await db.execute(
        select(SignalVerification).where(
            SignalVerification.signal_id == signal.id
        )
    )
    if existing.scalar_one_or_none():
        logger.info(f"Signal {signal.id} already verified, skip")
        return None

    # 找今天的行情
    today_start = trade_date.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = trade_date.replace(hour=23, minute=59, second=59)
    md_result = await db.execute(
        select(MarketData).where(
            MarketData.symbol == target_symbol,
            MarketData.trade_date >= today_start,
            MarketData.trade_date <= today_end,
        )
    )
    md = md_result.scalar_one_or_none()
    if not md:
        logger.warning(f"No market data for {trade_date.date()} {target_symbol}, skip verify")
        return None

    correct = _is_correct(signal.final_signal, md.change_pct)
    verification = SignalVerification(
        signal_id=signal.id,
        signal_date=prev_day,
        target_symbol=target_symbol,
        predicted_signal=signal.final_signal,
        blogger_consensus_score=signal.blogger_consensus_score,
        news_sentiment_score=signal.news_sentiment_score,
        confidence=signal.confidence,
        actual_change_pct=md.change_pct,
        actual_direction=_actual_direction(md.change_pct),
        is_correct=correct,
        error_magnitude=_error_magnitude(signal.final_signal, md.change_pct),
    )
    db.add(verification)
    await db.commit()
    await db.refresh(verification)

    logger.info(
        f"Signal verified: {target_symbol} {prev_day.date()} "
        f"predicted={signal.final_signal} actual={md.change_pct:+.2f}% correct={correct}"
    )
    return verification


async def check_and_trigger_review(
    db: AsyncSession,
    target_symbol: str = "000300",
) -> SignalReview | None:
    """
    检查最近 REVIEW_WINDOW_DAYS 天的验证记录，
    满足触发条件则调用 run_signal_review()。
    """
    since = datetime.utcnow() - timedelta(days=REVIEW_WINDOW_DAYS)
    result = await db.execute(
        select(SignalVerification)
        .where(
            SignalVerification.target_symbol == target_symbol,
            SignalVerification.verified_at >= since,
        )
        .order_by(desc(SignalVerification.verified_at))
    )
    records = result.scalars().all()

    if len(records) < REVIEW_MIN_SAMPLES:
        return None

    total = len(records)
    errors = sum(1 for r in records if not r.is_correct)
    error_rate = errors / total

    # 连续错误检测
    consecutive = 0
    for r in records:  # 已按时间倒序
        if not r.is_correct:
            consecutive += 1
        else:
            break

    trigger_reason = None
    if consecutive >= REVIEW_CONSECUTIVE_ERRORS:
        trigger_reason = f"连续 {consecutive} 次预测错误"
    elif error_rate >= REVIEW_ERROR_RATE:
        trigger_reason = f"近 {REVIEW_WINDOW_DAYS} 天错误率 {error_rate:.0%}（{errors}/{total}）"

    if not trigger_reason:
        return None

    logger.warning(f"Review triggered for {target_symbol}: {trigger_reason}")
    return await run_signal_review(db, target_symbol, records, trigger_reason)


async def run_signal_review(
    db: AsyncSession,
    target_symbol: str,
    records: list[SignalVerification],
    trigger_reason: str,
) -> SignalReview:
    """LLM 深度复盘，生成诊断报告。"""
    total = len(records)
    correct = sum(1 for r in records if r.is_correct)
    accuracy = correct / total

    # 构建复盘数据摘要
    detail_lines = []
    for r in sorted(records, key=lambda x: x.signal_date):
        result_tag = "✓" if r.is_correct else "✗"
        detail_lines.append(
            f"{result_tag} {r.signal_date.strftime('%m-%d')} "
            f"预测={r.predicted_signal} 实际={r.actual_change_pct:+.2f}% "
            f"博主共识={r.blogger_consensus_score:+.2f} 新闻情绪={r.news_sentiment_score:+.2f}"
        )
    detail_text = "\n".join(detail_lines)

    system_prompt = """你是一个量化投资系统的复盘分析师，同时也是耐心的投资教练。
你的任务是分析预测信号的失误原因，给出改进建议，并用通俗语言帮助新手理解。

输出严格 JSON（不要 markdown 包裹）：
{
  "problem_diagnosis": "失误原因分析，200字以内",
  "suggested_adjustments": "具体改进建议，包括权重/阈值/数据源等，150字以内",
  "learning_points": "给投资新手的学习要点，解释为什么市场预测很难、如何正确看待信号，150字以内"
}"""

    user_msg = f"""复盘标的：{target_symbol}
触发原因：{trigger_reason}
统计准确率：{accuracy:.0%}（{correct}/{total}）

近期信号验证明细：
{detail_text}

请分析失误原因，给出改进建议，并提炼新手学习要点。"""

    raw = await llm_json(system_prompt, user_msg, retries=2)

    if raw and isinstance(raw, dict):
        diagnosis = raw.get("problem_diagnosis", "LLM 未返回诊断。")
        adjustments = raw.get("suggested_adjustments", "暂无建议。")
        learning = raw.get("learning_points", "投资有风险，信号仅供参考。")
    else:
        diagnosis = f"自动检测到预测准确率偏低（{accuracy:.0%}），建议人工复查博主数据质量和新闻来源。"
        adjustments = "可考虑提高博主最低样本量要求，或调整新闻情绪权重。"
        learning = "市场预测本质上是概率游戏，没有系统能做到100%准确。信号是参考，不是指令。"

    review_start = min(r.signal_date for r in records)
    review_end = max(r.signal_date for r in records)

    review = SignalReview(
        target_symbol=target_symbol,
        review_start=review_start,
        review_end=review_end,
        total_signals=total,
        correct_signals=correct,
        accuracy_rate=accuracy,
        trigger_reason=trigger_reason,
        problem_diagnosis=diagnosis,
        suggested_adjustments=adjustments,
        learning_points=learning,
        llm_raw_response=raw,
        is_pushed=False,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    logger.info(f"Signal review saved: id={review.id} accuracy={accuracy:.0%}")
    return review


async def push_pending_reviews(db: AsyncSession) -> dict:
    """把还没推送的复盘报告发给 owner（TELEGRAM_CHAT_ID）。"""
    from app.services.telegram_bot import bot
    from app.core.config import settings

    # owner chat_id 优先；没配则回退到 lifetime 用户
    owner_ids: list[str] = []
    if settings.TELEGRAM_CHAT_ID:
        owner_ids.append(settings.TELEGRAM_CHAT_ID)
    else:
        from app.models.models import User
        users_result = await db.execute(
            select(User).where(
                User.telegram_chat_id.isnot(None),
                User.plan == "lifetime",
            )
        )
        owner_ids = [u.telegram_chat_id for u in users_result.scalars().all()]

    if not owner_ids:
        logger.warning("No owner chat_id configured, review push skipped")
        return {"pushed": 0}

    result = await db.execute(
        select(SignalReview).where(SignalReview.is_pushed == False)  # noqa: E712
    )
    reviews = result.scalars().all()
    if not reviews:
        return {"pushed": 0}

    pushed = 0
    for review in reviews:
        # 分两段发，防止超长
        part1 = (
            f"<b>🔍 FundRadar 信号复盘报告</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"📌 标的：{review.target_symbol}\n"
            f"⚠️ 触发原因：{review.trigger_reason}\n"
            f"📊 准确率：{review.accuracy_rate:.0%}"
            f"（{review.correct_signals}/{review.total_signals}）\n"
            f"🗓 复盘区间：{review.review_start.strftime('%m-%d')} ~ "
            f"{review.review_end.strftime('%m-%d')}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<b>🔎 问题诊断</b>\n{review.problem_diagnosis}\n\n"
            f"<b>🛠 改进建议</b>\n{review.suggested_adjustments}"
        )
        part2 = (
            f"<b>📚 新手学习要点</b>\n{review.learning_points}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"<i>复盘时间：{review.reviewed_at.strftime('%Y-%m-%d %H:%M')}</i>"
        )
        for chat_id in owner_ids:
            ok1 = await bot.send_message(chat_id, part1)
            ok2 = await bot.send_message(chat_id, part2)
            if ok1 and ok2:
                pushed += 1

        review.is_pushed = True

    await db.commit()
    logger.info(f"Review push done: {pushed} sent for {len(reviews)} reviews")
    return {"pushed": pushed, "reviews": len(reviews)}
