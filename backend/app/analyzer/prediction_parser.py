"""博主帖子解析 — 用 LLM 判断是否为有效预测并提取结构化信息。"""
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_json
from app.models.models import Prediction

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的金融分析助手，擅长识别A股市场的投资预测。
你的任务是分析财经博主的帖子，判断是否包含明确的市场方向性预测。

判断标准：
- 必须有明确的看涨或看跌判断，模糊表态不算（如"注意风险"、"保持谨慎"、"市场有机会"）
- 必须针对具体标的（指数、基金、板块），泛泛而谈不算
- 时间窗口要相对明确（短期/本周/近期均可，但"长期看好"这种太模糊不算）

请严格按JSON格式返回，不要有任何额外文字。"""

USER_TEMPLATE = """分析以下帖子，判断是否包含明确的市场预测：

帖子内容：
{content}

请返回JSON：
{{
  "is_prediction": true或false,
  "direction": "bullish（看涨）/ bearish（看跌）/ neutral（中性）/ null（无法判断）",
  "target": "标的名称或代码，如'沪深300'或'000300'，无则null",
  "time_horizon": "short（数日内）/ medium（数周）/ long（数月以上）/ null",
  "confidence": 0.0到1.0之间的数字（你对这条预测明确程度的判断）,
  "reasoning": "你的判断依据，一句话"
}}"""


async def parse_prediction(db: AsyncSession, prediction_id: int) -> bool:
    """解析单条帖子，更新 Prediction 记录。返回是否为有效预测。"""
    result = await db.execute(select(Prediction).where(Prediction.id == prediction_id))
    pred = result.scalar_one_or_none()
    if not pred:
        return False

    raw = await llm_json(
        system=SYSTEM_PROMPT,
        user=USER_TEMPLATE.format(content=pred.post_content[:2000]),
    )

    if raw is None:
        logger.warning(f"LLM parse failed for prediction {prediction_id}")
        return False

    is_pred = bool(raw.get("is_prediction", False))
    confidence = float(raw.get("confidence", 0.0))

    # 置信度低于 0.6 的预测不采纳
    if is_pred and confidence < 0.6:
        is_pred = False

    pred.is_prediction = is_pred
    pred.predicted_direction = raw.get("direction") if is_pred else None
    pred.predicted_target = raw.get("target") if is_pred else None
    pred.confidence = confidence
    pred.llm_reasoning = raw.get("reasoning")
    pred.llm_raw_response = raw

    await db.commit()
    return is_pred


async def parse_unparsed_predictions(db: AsyncSession, limit: int = 50) -> dict:
    """批量解析还没有 LLM 分析的帖子。"""
    result = await db.execute(
        select(Prediction)
        .where(Prediction.llm_raw_response.is_(None))
        .order_by(Prediction.post_time.desc())
        .limit(limit)
    )
    predictions = result.scalars().all()

    total = len(predictions)
    valid = 0
    for pred in predictions:
        is_valid = await parse_prediction(db, pred.id)
        if is_valid:
            valid += 1

    logger.info(f"Parsed {total} posts, {valid} valid predictions")
    return {"total": total, "valid_predictions": valid, "skipped": total - valid}
