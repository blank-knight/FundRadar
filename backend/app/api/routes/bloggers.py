"""Blogger management routes — 博主管理 API。"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import Blogger, User
from app.schemas.schemas import BloggerCreate, BloggerResponse, BloggerUpdate
from app.crawler.xueqiu import XueqiuCrawler

router = APIRouter(prefix="/bloggers", tags=["bloggers"])


@router.get("/search", response_model=List[dict])
async def search_bloggers(
    q: str = Query(..., min_length=1, description="博主名字或雪球用户ID"),
    _: User = Depends(get_current_user),
):
    """在雪球上搜索博主，返回候选列表供用户选择添加。"""
    async with XueqiuCrawler() as crawler:
        results = await crawler.search_users(q)
    return results


@router.get("", response_model=List[BloggerResponse])
async def list_bloggers(
    active_only: bool = Query(True, description="只返回启用的博主"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取已追踪的博主列表，按准确率降序排列。"""
    stmt = select(Blogger).where(Blogger.platform == "xueqiu")
    if active_only:
        stmt = stmt.where(Blogger.is_active == True)
    stmt = stmt.order_by(Blogger.accuracy_score.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=BloggerResponse, status_code=status.HTTP_201_CREATED)
async def add_blogger(
    data: BloggerCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """添加博主到追踪列表。"""
    stmt = select(Blogger).where(
        Blogger.platform == data.platform,
        Blogger.platform_user_id == data.platform_user_id,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            await db.commit()
            await db.refresh(existing)
            return existing
        raise HTTPException(status_code=409, detail="该博主已在追踪列表中")

    blogger = Blogger(**data.model_dump())
    db.add(blogger)
    await db.commit()
    await db.refresh(blogger)
    return blogger


@router.get("/{blogger_id}", response_model=BloggerResponse)
async def get_blogger(
    blogger_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取单个博主详情。"""
    blogger = await db.get(Blogger, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")
    return blogger


@router.patch("/{blogger_id}", response_model=BloggerResponse)
async def update_blogger(
    blogger_id: int,
    data: BloggerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """更新博主信息（启用/禁用等）。"""
    blogger = await db.get(Blogger, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(blogger, field, value)
    await db.commit()
    await db.refresh(blogger)
    return blogger


@router.delete("/{blogger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_blogger(
    blogger_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """从追踪列表移除博主（软删除，保留历史预测数据）。"""
    blogger = await db.get(Blogger, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")
    blogger.is_active = False
    await db.commit()


@router.post("/{blogger_id}/refresh", response_model=BloggerResponse)
async def refresh_blogger(
    blogger_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """从雪球重新拉取博主最新信息（粉丝数、头像等）。"""
    blogger = await db.get(Blogger, blogger_id)
    if not blogger:
        raise HTTPException(status_code=404, detail="博主不存在")
    async with XueqiuCrawler() as crawler:
        info = await crawler.get_user_info(blogger.platform_user_id)
    if info:
        blogger.username = info.get("username", blogger.username)
        blogger.avatar_url = info.get("avatar_url", blogger.avatar_url)
        blogger.follower_count = info.get("follower_count", blogger.follower_count)
        await db.commit()
        await db.refresh(blogger)
    return blogger
