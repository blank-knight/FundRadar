"""Signal routes — 信号复盘报告 API。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.models import SignalReview, SignalVerification
from app.schemas.schemas import (
    SignalReviewResponse,
    SignalReviewListResponse,
    SignalVerificationResponse,
)

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/reviews", response_model=SignalReviewListResponse)
async def list_reviews(
    symbol: Optional[str] = Query(None, description="按标的筛选，如 000300"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取历史复盘报告列表，按时间倒序。支持按标的筛选和分页。"""
    q = select(SignalReview).order_by(desc(SignalReview.reviewed_at))
    count_q = select(func.count()).select_from(SignalReview)

    if symbol:
        q = q.where(SignalReview.target_symbol == symbol)
        count_q = count_q.where(SignalReview.target_symbol == symbol)

    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    result = await db.execute(q.offset(offset).limit(limit))
    items = result.scalars().all()

    return SignalReviewListResponse(total=total, items=items)


@router.get("/reviews/{review_id}", response_model=SignalReviewResponse)
async def get_review(
    review_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单条复盘报告详情。"""
    from fastapi import HTTPException
    result = await db.execute(
        select(SignalReview).where(SignalReview.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="复盘报告不存在")
    return review
