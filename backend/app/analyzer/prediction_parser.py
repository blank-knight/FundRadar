"""博主帖子解析 — 用 LLM 判断是否为有效预测并提取结构化信息。

优化: 批量解析（BATCH_SIZE条/次），减少 LLM 调用次数，避免 429。
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyzer.llm_client import llm_json
from app.models.models import Prediction

logger = logging.getLogger(__name__)

BATCH_SIZE = 5  # 每次给 LLM 5条帖子
BATCH_DELAY = 1.0  # 批间延时（秒），避免 429

SYSTEM_PROMPT = """你是一个专业的金融分析助手，擅长识别A股市场的投资预测。
你的任务是分析财经博主的帖子，判断是否包含明确的市场方向性预测。

判断标准：
- 必须有明确的看涨或看跌判断，模糊表态不算（如"注意风险"、"保持谨慎"、"市场有机会"）
- 必须针对具体标的（指数、基金、板块），泛泛而谈不算
- 时间窗口要相对明确（短期/本周/近期均可，但"长期看好"这种太模糊不算）

请严格按JSON格式返回，不要有任何额外文字。"""

BATCH_SYSTEM_PROMPT = """你是一个专业的金融分析助手，擅长识别A股市场的投资预测。
你将收到多条博主的帖子（用 [0] [1] [2] 编号标注），需要逐条分析。

判断标准：
- 必须有明确的看涨或看跌判断，模糊表态不算
- 必须针对具体标的（指数、基金、板块），泛泛而谈不算
- 时间窗口要相对明确

请返回JSON数组，每个元素对应一条帖子，按编号顺序：
```json
[
  {
    "is_prediction": true或false,
    "direction": "bullish/bearish/neutral/null",
    "target": "标的名称，无则null",
    "time_horizon": "short/medium/long/null",
    "confidence": 0.0到1.0,
    "reasoning": "一句话判断依据"
  }
]
```
数组长度必须和输入帖子数量一致。"""

USER_TEMPLATE = """分析以下帖子，判断是否包含明确的市场预测：

帖子内容：
{items}

请返回JSON数组，每条帖子一个元素。"""

# 单条解析用的模板（降级时使用）
SINGLE_USER_TEMPLATE = """分析以下帖子，判断是否包含明确的市场预测：

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
        user=SINGLE_USER_TEMPLATE.format(content=pred.post_content[:2000]),
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
    """批量解析还没有 LLM 分析的帖子。

    优化: 按 BATCH_SIZE 分批，每批一次 LLM 调用，
    批间延时 BATCH_DELAY 秒，避免 API 429。
    """
    result = await db.execute(
        select(Prediction)
        .where(Prediction.llm_raw_response.is_(None))
        .order_by(Prediction.post_time.desc())
        .limit(limit)
    )
    predictions = result.scalars().all()

    total = len(predictions)
    if total == 0:
        return {"total": 0, "valid_predictions": 0, "skipped": 0}

    valid = 0
    # 分批处理
    for i in range(0, total, BATCH_SIZE):
        batch = predictions[i:i + BATCH_SIZE]
        batch_valid = await _parse_batch(db, batch)
        valid += batch_valid

        if i + BATCH_SIZE < total:
            await asyncio.sleep(BATCH_DELAY)

    logger.info(f"Parsed {total} posts in {(total + BATCH_SIZE - 1) // BATCH_SIZE} batches, {valid} valid predictions")
    return {"total": total, "valid_predictions": valid, "skipped": total - valid}


async def _parse_batch(db: AsyncSession, predictions: list[Prediction]) -> int:
    """一次解析多条帖子（单次 LLM 调用）。

    Returns: 本批中有效预测的数量。
    """
    # 构造批量 prompt
    items = []
    for idx, pred in enumerate(predictions):
        content = (pred.post_content or "")[:500]
        items.append(f"[{idx}] {content}")

    batch_prompt = USER_TEMPLATE.format(items="\n\n".join(items))

    raw = await llm_json(
        system=BATCH_SYSTEM_PROMPT,
        user=batch_prompt,
    )

    if raw is None:
        # 批量失败，降级为逐条解析
        logger.warning(f"Batch parse failed ({len(predictions)} items), falling back to single")
        valid = 0
        for pred in predictions:
            if await parse_prediction(db, pred.id):
                valid += 1
            await asyncio.sleep(0.5)
        return valid

    # 解析批量结果
    results_list = raw if isinstance(raw, list) else raw.get("results", [])
    valid = 0

    for idx, pred in enumerate(predictions):
        if idx >= len(results_list):
            pred.is_prediction = False
            pred.llm_raw_response = {"skipped": True, "reason": "batch_overflow"}
            continue

        item = results_list[idx]
        is_pred = bool(item.get("is_prediction", False))
        confidence = float(item.get("confidence") or 0.0)

        if is_pred and confidence < 0.6:
            is_pred = False

        pred.is_prediction = is_pred
        pred.predicted_direction = item.get("direction") if is_pred else None
        pred.predicted_target = item.get("target") if is_pred else None
        pred.confidence = confidence
        pred.llm_reasoning = item.get("reasoning")
        pred.llm_raw_response = item

        if is_pred:
            valid += 1

    await db.commit()
    return valid
