"""Order and payment routes."""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.plans import PLANS, get_plan_info, is_valid_plan
from app.models.models import Order, User
from app.schemas.schemas import OrderCreate, OrderResponse


router = APIRouter(prefix="/orders", tags=["orders"])


def generate_order_no() -> str:
    """Generate unique order number.

    Returns:
        Order number string (timestamp + random)
    """
    timestamp = str(int(time.time()))
    random_part = secrets.token_hex(4)
    return f"FR{timestamp}{random_part}"


def generate_xunhupay_hash(params: Dict[str, str]) -> str:
    """Generate Xunhupay payment hash signature.

    Args:
        params: Payment parameters dict

    Returns:
        MD5 hash string
    """
    # Sort parameters by key alphabetically
    sorted_params = sorted(params.items())
    # Build query string
    param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
    # Append appsecret
    sign_str = f"{param_str}&appsecret={settings.XUNHUPAY_APPSECRET}"
    # Calculate MD5 hash
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()


@router.get("/plans", response_model=List[Dict])
async def get_plans():
    """Get all available subscription plans.

    Returns:
        List of plan configurations
    """
    plans_list = []
    for plan_type, config in PLANS.items():
        plans_list.append({
            "type": plan_type,
            "name": config["name"],
            "price_cents": config["price_cents"],
            "price_yuan": config["price_cents"] / 100,
            "days": config["days"]
        })
    return plans_list


@router.post("/", response_model=Dict, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new payment order.

    Args:
        order_data: Order creation data (plan_type)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Order info with payment URL

    Raises:
        HTTPException: 400 if plan type is invalid
    """
    # Validate plan type
    if not is_valid_plan(order_data.plan_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan type: {order_data.plan_type}"
        )

    # Get plan info
    plan_info = get_plan_info(order_data.plan_type)
    order_no = generate_order_no()

    # Create order record
    new_order = Order(
        user_id=current_user.id,
        order_no=order_no,
        plan_type=order_data.plan_type,
        amount=plan_info["price_cents"] / 100,
        status="pending"
    )

    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    # Generate payment URL (if Xunhupay is configured)
    payment_url = None
    if settings.XUNHUPAY_APPID and settings.XUNHUPAY_APPSECRET:
        # Build payment parameters
        params = {
            "appid": settings.XUNHUPAY_APPID,
            "trade_order_id": order_no,
            "total_fee": str(plan_info["price_cents"] / 100),
            "title": plan_info["name"],
            "time": str(int(time.time())),
            "nonce_str": secrets.token_hex(8)
        }
        # Generate hash signature
        params["hash"] = generate_xunhupay_hash(params)
        # Build payment URL
        base_url = "https://api.xunhupay.com/payment/do.html"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        payment_url = f"{base_url}?{query_string}"

    return {
        "order": OrderResponse.model_validate(new_order),
        "payment_url": payment_url
    }


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get order details by ID.

    Args:
        order_id: Order ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Order details

    Raises:
        HTTPException: 404 if order not found or not owned by user
    """
    result = await db.execute(
        select(Order).where(
            Order.id == order_id,
            Order.user_id == current_user.id
        )
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    return OrderResponse.model_validate(order)


@router.post("/notify")
async def payment_notify(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle payment callback from Xunhupay.

    Args:
        request: FastAPI request object
        db: Database session

    Returns:
        Success response for payment gateway

    Raises:
        HTTPException: 400 if signature verification fails
    """
    # Parse form data
    form_data = await request.form()
    callback_data = dict(form_data)

    # Verify signature
    received_hash = callback_data.pop("hash", None)
    if not received_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing hash signature"
        )

    # Calculate expected hash
    expected_hash = generate_xunhupay_hash(callback_data)
    if received_hash != expected_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    # Extract order info
    order_no = callback_data.get("trade_order_id")
    trade_status = callback_data.get("status")  # OD = paid

    if not order_no:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing order number"
        )

    # Find order
    result = await db.execute(
        select(Order).where(Order.order_no == order_no)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    # Update order status if paid
    if trade_status == "OD" and order.status == "pending":
        order.status = "paid"
        order.payment_time = datetime.utcnow()
        order.payment_method = callback_data.get("type", "unknown")
        order.third_party_order_no = callback_data.get("transaction_id")
        order.raw_callback_data = callback_data

        # Update user subscription
        user_result = await db.execute(
            select(User).where(User.id == order.user_id)
        )
        user = user_result.scalar_one_or_none()

        if user:
            plan_info = get_plan_info(order.plan_type)
            user.plan = order.plan_type

            # Calculate expiration date
            if order.plan_type == "lifetime":
                user.plan_expires_at = None  # Never expires
            else:
                # Extend from current expiry or now
                if user.plan_expires_at and user.plan_expires_at > datetime.utcnow():
                    user.plan_expires_at += timedelta(days=plan_info["days"])
                else:
                    user.plan_expires_at = datetime.utcnow() + timedelta(days=plan_info["days"])

        await db.commit()

    return {"success": True}
