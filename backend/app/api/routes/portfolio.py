"""Portfolio management routes — 持仓管理 API。"""

import asyncio
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.models import Portfolio, PortfolioAnalysis

from app.schemas.schemas import (
    PortfolioCreate,
    PortfolioUpdate,
    PortfolioResponse,
    PortfolioSummary,
    PortfolioAnalysisResponse,
    BatchAnalysisItem,
    BatchAnalysisResponse,
)
from app.models.models import User

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


# ─────────────────────────────────────────────
# 内部工具
# ─────────────────────────────────────────────

def _calc_cost_total(shares: float, cost_price: float) -> float:
    return round(shares * cost_price, 4)


def _refresh_pnl(item: Portfolio) -> None:
    """用 current_price 刷新盈亏字段（原地修改）。"""
    if item.current_price is None:
        return
    item.current_value = round(item.shares * item.current_price, 4)
    item.profit_loss = round(item.current_value - item.cost_total, 4)
    if item.cost_total > 0:
        item.profit_loss_pct = round(item.profit_loss / item.cost_total * 100, 4)


# ─────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────

@router.get("", response_model=PortfolioSummary)
async def list_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户全部持仓及汇总。"""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    items = result.scalars().all()

    total_cost = sum(i.cost_total for i in items)
    total_value = sum(i.current_value or i.cost_total for i in items)
    total_pnl = total_value - total_cost
    total_pnl_pct = round(total_pnl / total_cost * 100, 4) if total_cost > 0 else 0.0

    return PortfolioSummary(
        total_cost=total_cost,
        total_value=total_value,
        total_profit_loss=total_pnl,
        total_profit_loss_pct=total_pnl_pct,
        items=items,
    )


@router.post("", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
async def add_position(
    payload: PortfolioCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """新增一条持仓记录。同一用户同一基金代码只能有一条（重复则报错）。"""
    existing = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == current_user.id,
            Portfolio.fund_code == payload.fund_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"已存在 {payload.fund_code} 的持仓，请用 PATCH 更新",
        )

    item = Portfolio(
        user_id=current_user.id,
        fund_code=payload.fund_code,
        fund_name=payload.fund_name,
        fund_type=payload.fund_type,
        shares=payload.shares,
        cost_price=payload.cost_price,
        cost_total=_calc_cost_total(payload.shares, payload.cost_price),
        note=payload.note,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{fund_code}", response_model=PortfolioResponse)
async def update_position(
    fund_code: str,
    payload: PortfolioUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新持仓份额/成本价/备注。"""
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == current_user.id,
            Portfolio.fund_code == fund_code,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="持仓不存在")

    if payload.shares is not None:
        item.shares = payload.shares
    if payload.cost_price is not None:
        item.cost_price = payload.cost_price
    if payload.note is not None:
        item.note = payload.note

    item.cost_total = _calc_cost_total(item.shares, item.cost_price)
    _refresh_pnl(item)

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{fund_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    fund_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除一条持仓记录。"""
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == current_user.id,
            Portfolio.fund_code == fund_code,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="持仓不存在")
    await db.delete(item)
    await db.commit()


@router.get("/{fund_code}/analyze", response_model=PortfolioAnalysisResponse)
async def analyze_position(
    fund_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对单只持仓做 LLM 分析，返回操作建议 + 新手教学解释。"""
    result = await db.execute(
        select(Portfolio).where(
            Portfolio.user_id == current_user.id,
            Portfolio.fund_code == fund_code,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="持仓不存在")

    from app.services.portfolio_analyzer import analyze_portfolio_item
    analysis = await analyze_portfolio_item(item, db)

    record = PortfolioAnalysis(
        user_id=current_user.id,
        fund_code=fund_code,
        current_price=item.current_price or item.cost_price,
        profit_loss_pct=item.profit_loss_pct or 0.0,
        action=analysis["action"],
        action_label=analysis["action_label"],
        reasoning=analysis["reasoning"],
        llm_raw_response=analysis.get("raw"),
    )
    db.add(record)
    await db.commit()

    return PortfolioAnalysisResponse(
        fund_code=fund_code,
        fund_name=item.fund_name,
        analyzed_at=record.analyzed_at,
        current_price=record.current_price,
        profit_loss_pct=record.profit_loss_pct,
        action=record.action,
        action_label=record.action_label,
        reasoning=record.reasoning,
    )


# ─────────────────────────────────────────────
# 批量分析
# ─────────────────────────────────────────────

async def _analyze_one(item: Portfolio, db: AsyncSession) -> BatchAnalysisItem:
    """对单只持仓跑分析，失败时返回 error 字段而不抛异常。"""
    from app.services.portfolio_analyzer import analyze_portfolio_item
    try:
        analysis = await analyze_portfolio_item(item, db)
        record = PortfolioAnalysis(
            user_id=item.user_id,
            fund_code=item.fund_code,
            current_price=item.current_price or item.cost_price,
            profit_loss_pct=item.profit_loss_pct or 0.0,
            action=analysis["action"],
            action_label=analysis["action_label"],
            reasoning=analysis["reasoning"],
            llm_raw_response=analysis.get("raw"),
        )
        db.add(record)
        await db.commit()
        return BatchAnalysisItem(
            fund_code=item.fund_code,
            fund_name=item.fund_name,
            action=analysis["action"],
            action_label=analysis["action_label"],
            reasoning=analysis["reasoning"],
            profit_loss_pct=item.profit_loss_pct or 0.0,
        )
    except Exception as e:
        return BatchAnalysisItem(
            fund_code=item.fund_code,
            fund_name=item.fund_name,
            action="watch",
            action_label="观望",
            reasoning="",
            profit_loss_pct=item.profit_loss_pct or 0.0,
            error=str(e),
        )


@router.post("/analyze/batch", response_model=BatchAnalysisResponse)
async def batch_analyze(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对当前用户所有持仓并发做 LLM 分析，返回每只的操作建议。"""
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == current_user.id)
    )
    items = result.scalars().all()

    if not items:
        return BatchAnalysisResponse(total=0, succeeded=0, failed=0, results=[])

    # 并发跑，最多 5 个同时进行，避免 LLM 限速
    semaphore = asyncio.Semaphore(5)

    async def _with_sem(item: Portfolio) -> BatchAnalysisItem:
        async with semaphore:
            return await _analyze_one(item, db)

    results = await asyncio.gather(*[_with_sem(i) for i in items])

    succeeded = sum(1 for r in results if r.error is None)
    failed = len(results) - succeeded

    return BatchAnalysisResponse(
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=list(results),
    )

