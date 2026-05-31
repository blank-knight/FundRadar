"""Telegram 相关 API 路由。"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import User
from app.services.bot_handler import handle_update, generate_bind_code

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/bind-code")
async def get_bind_code(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成 Telegram 绑定码（登录后调用）。"""
    code = generate_bind_code()
    current_user.telegram_bind_code = code
    await db.commit()
    return {
        "bind_code": code,
        "instruction": f"在 Telegram 中发送：/bind {code}",
        "expires_in": "10分钟内有效（重新获取会刷新）",
    }


@router.delete("/unbind")
async def unbind_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """解除 Telegram 绑定（网页端操作）。"""
    if not current_user.telegram_chat_id:
        raise HTTPException(status_code=400, detail="未绑定 Telegram")
    current_user.telegram_chat_id = None
    current_user.telegram_bind_code = None
    await db.commit()
    return {"message": "已解除绑定"}


@router.get("/status")
async def telegram_status(
    current_user: User = Depends(get_current_user),
):
    """查询当前用户的 Telegram 绑定状态。"""
    return {
        "bound": current_user.telegram_chat_id is not None,
        "chat_id": current_user.telegram_chat_id,
    }


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """接收 Telegram Webhook 推送（生产环境用）。"""
    try:
        update = await request.json()
        await handle_update(update, db)
    except Exception as e:
        # Webhook 必须返回 200，否则 Telegram 会重试
        pass
    return {"ok": True}
