"""Trade review routes — 用户复盘对话 CRUD + AI 对话 API。"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import TradeReview, TradeReviewMessage, User
from app.schemas.schemas import (
    TradeReviewCreate,
    TradeReviewResponse,
    TradeReviewDetailResponse,
    TradeReviewListResponse,
    TradeReviewChatRequest,
    TradeReviewChatResponse,
    TradeReviewMessageResponse,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────

@router.get("", response_model=TradeReviewListResponse)
async def list_reviews(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的复盘记录列表，按更新时间倒序。"""
    base_q = select(TradeReview).where(TradeReview.user_id == current_user.id)
    count_q = select(func.count()).select_from(TradeReview).where(
        TradeReview.user_id == current_user.id
    )

    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    result = await db.execute(
        base_q.order_by(desc(TradeReview.updated_at)).offset(offset).limit(limit)
    )
    items = result.scalars().all()

    return TradeReviewListResponse(total=total, items=items)


@router.post("", response_model=TradeReviewDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: TradeReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建一条新的复盘记录。"""
    now = datetime.utcnow()
    title = payload.title or f"{now.strftime('%m月%d日')}复盘"

    review = TradeReview(
        user_id=current_user.id,
        title=title,
        preview=None,
        message_count=0,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    return TradeReviewDetailResponse(
        id=review.id,
        title=review.title,
        preview=review.preview,
        message_count=review.message_count,
        created_at=review.created_at,
        updated_at=review.updated_at,
        messages=[],
    )


@router.get("/{review_id}", response_model=TradeReviewDetailResponse)
async def get_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取复盘详情，包含全部对话消息。"""
    result = await db.execute(
        select(TradeReview).where(
            TradeReview.id == review_id,
            TradeReview.user_id == current_user.id,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="复盘记录不存在")

    # 显式加载 messages
    msg_result = await db.execute(
        select(TradeReviewMessage)
        .where(TradeReviewMessage.review_id == review_id)
        .order_by(TradeReviewMessage.id)
    )
    messages = msg_result.scalars().all()

    return TradeReviewDetailResponse(
        id=review.id,
        title=review.title,
        preview=review.preview,
        message_count=review.message_count,
        created_at=review.created_at,
        updated_at=review.updated_at,
        messages=[
            TradeReviewMessageResponse(
                id=m.id, role=m.role, content=m.content, created_at=m.created_at
            )
            for m in messages
        ],
    )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除复盘记录（连同所有消息级联删除）。"""
    result = await db.execute(
        select(TradeReview).where(
            TradeReview.id == review_id,
            TradeReview.user_id == current_user.id,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="复盘记录不存在")

    await db.delete(review)
    await db.commit()


# ─────────────────────────────────────────────
# AI 对话
# ─────────────────────────────────────────────

@router.post("/{review_id}/chat", response_model=TradeReviewChatResponse)
async def chat(
    review_id: int,
    payload: TradeReviewChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在指定复盘记录中发送消息，获取 AI 回复。

    流程：
    1. 验证复盘记录属于当前用户
    2. 保存用户消息
    3. 调用 LLM（带持仓上下文 + 对话历史）
    4. 保存 AI 回复
    5. 更新复盘记录的 preview / message_count
    """
    # 1. 验证归属
    result = await db.execute(
        select(TradeReview).where(
            TradeReview.id == review_id,
            TradeReview.user_id == current_user.id,
        )
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=404, detail="复盘记录不存在")

    # 2. 保存用户消息
    user_msg = TradeReviewMessage(
        review_id=review_id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    await db.flush()  # 拿到 id

    # 3. 调用 LLM
    from app.services.review_chat import chat_with_review
    reply_text = await chat_with_review(db, review_id, payload.message, current_user.id)

    # 4. 保存 AI 回复
    ai_msg = TradeReviewMessage(
        review_id=review_id,
        role="assistant",
        content=reply_text,
    )
    db.add(ai_msg)
    await db.flush()

    # 5. 更新复盘记录元数据
    review.preview = payload.message[:50] + ("..." if len(payload.message) > 50 else "")
    review.message_count = review.message_count + 2
    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(ai_msg)

    return TradeReviewChatResponse(
        user_message=TradeReviewMessageResponse(
            id=user_msg.id, role="user",
            content=user_msg.content, created_at=user_msg.created_at,
        ),
        assistant_message=TradeReviewMessageResponse(
            id=ai_msg.id, role="assistant",
            content=ai_msg.content, created_at=ai_msg.created_at,
        ),
    )
