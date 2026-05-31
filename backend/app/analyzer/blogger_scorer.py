"""博主评分系统 — T+1 验证 + 综合评分计算。"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Blogger, Prediction, PredictionVerification, MarketData

logger = logging.getLogger(__name__)

# 评分权重
W_BASE_ACCURACY = 0.60    # 历史总准确率
W_RECENT_ACCURACY = 0.20  # 近30天准确率
W_SPECIFICITY = 0.10      # 预测具体程度
W_SAMPLE_CONF = 0.10      # 样本量置信度

MIN_PREDICTIONS = 10      # 最少需要多少条已验证预测才显示评分


async def verify_predictions(db: AsyncSession, trade_date: datetime) -> dict:
    """
    T+1 验证：对 trade_date 前一天发出的预测，用 trade_date 的实际涨跌来验证。
    """
    prev_day = trade_date - timedelta(days=1)
    day_start = prev_day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = prev_day.replace(hour=23, minute=59, second=59)

    # 找出前一天的有效预测（还没验证的）
    result = await db.execute(
        select(Prediction)
        .where(
            Prediction.post_time >= day_start,
            Prediction.post_time <= day_end,
            Prediction.is_prediction == True,
            Prediction.is_verified == False,
            Prediction.predicted_target.isnot(None),
        )
    )
    predictions = result.scalars().all()

    verified = 0
    for pred in predictions:
        # 找对应标的的当日行情
        symbol = _normalize_symbol(pred.predicted_target)
        if not symbol:
            continue

        market = await db.execute(
            select(MarketData).where(
                MarketData.symbol == symbol,
                MarketData.trade_date >= trade_date.replace(hour=0, minute=0, second=0),
                MarketData.trade_date < trade_date.replace(hour=23, minute=59, second=59),
            )
        )
        md = market.scalar_one_or_none()
        if not md:
            continue

        # 判断预测是否正确
        is_correct = _check_correct(pred.predicted_direction, md.change_pct)

        verification = PredictionVerification(
            prediction_id=pred.id,
            verification_date=trade_date,
            actual_change_pct=md.change_pct,
            is_correct=is_correct,
        )
        db.add(verification)
        pred.is_verified = True
        verified += 1

    await db.commit()

    # 更新所有涉及博主的评分
    if verified > 0:
        blogger_ids = list({p.blogger_id for p in predictions})
        for bid in blogger_ids:
            await update_blogger_score(db, bid)

    logger.info(f"Verified {verified} predictions for {trade_date.date()}")
    return {"verified": verified, "trade_date": str(trade_date.date())}


async def update_blogger_score(db: AsyncSession, blogger_id: int) -> float:
    """重新计算并保存博主的综合评分。"""
    result = await db.execute(select(Blogger).where(Blogger.id == blogger_id))
    blogger = result.scalar_one_or_none()
    if not blogger:
        return 0.0

    # 所有已验证预测
    all_result = await db.execute(
        select(PredictionVerification)
        .join(Prediction)
        .where(Prediction.blogger_id == blogger_id)
    )
    all_verifications = all_result.scalars().all()

    total = len(all_verifications)
    if total == 0:
        return 0.0

    correct = sum(1 for v in all_verifications if v.is_correct)

    # 近30天
    since_30d = datetime.utcnow() - timedelta(days=30)
    recent = [v for v in all_verifications if v.verification_date >= since_30d]
    recent_total = len(recent)
    recent_correct = sum(1 for v in recent if v.is_correct)

    # 各维度分数
    base_accuracy = correct / total if total > 0 else 0.0
    recent_accuracy = recent_correct / recent_total if recent_total > 0 else base_accuracy

    # 样本量置信度：10条=50%，30条=80%，50条+=100%
    sample_conf = min(1.0, total / 50)

    # 预测具体程度（暂时固定0.7，Phase 4后期可细化）
    specificity = 0.7

    # 综合评分 0-100
    score = (
        base_accuracy * W_BASE_ACCURACY
        + recent_accuracy * W_RECENT_ACCURACY
        + specificity * W_SPECIFICITY
        + sample_conf * W_SAMPLE_CONF
    ) * 100

    blogger.accuracy_score = round(score, 2)
    blogger.total_predictions = total
    blogger.correct_predictions = correct
    await db.commit()

    return blogger.accuracy_score


async def get_blogger_consensus(db: AsyncSession, hours: int = 72) -> float:
    """
    计算近N小时内博主的加权共识分。
    看涨=+1，看跌=-1，按博主准确率加权。
    返回 -1 到 1。
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(Prediction)
        .options(selectinload(Prediction.blogger))
        .where(
            Prediction.post_time >= since,
            Prediction.is_prediction == True,
            Prediction.predicted_direction.in_(["bullish", "bearish"]),
        )
    )
    predictions = result.scalars().all()

    if not predictions:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for pred in predictions:
        blogger = pred.blogger
        # 样本不足的博主权重降低
        if blogger.total_predictions < MIN_PREDICTIONS:
            weight = 0.3
        else:
            weight = max(0.1, blogger.accuracy_score / 100)

        direction_val = 1.0 if pred.predicted_direction == "bullish" else -1.0
        weighted_sum += direction_val * weight * pred.confidence
        total_weight += weight

    return round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0


def _normalize_symbol(target: str | None) -> str | None:
    """把博主写的标的名称/代码标准化为我们 DB 里的 symbol。"""
    if not target:
        return None
    mapping = {
        "沪深300": "000300", "000300": "000300", "hs300": "000300",
        "创业板": "399006", "399006": "399006", "创业板指": "399006",
        "上证50": "000016", "000016": "000016",
        "纳指": "NDX", "纳斯达克": "NDX", "ndx": "NDX",
    }
    return mapping.get(target.strip().lower()) or mapping.get(target.strip())


def _check_correct(direction: str | None, change_pct: float) -> bool:
    """判断预测方向是否与实际涨跌一致。"""
    if direction == "bullish":
        return change_pct > 0
    elif direction == "bearish":
        return change_pct < 0
    return False
