from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ============ User Schemas ============

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    plan: str
    plan_expires_at: Optional[datetime] = None
    telegram_chat_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    telegram_bind_code: Optional[str] = None
    telegram_chat_id: Optional[str] = None


# ============ Order Schemas ============

class OrderBase(BaseModel):
    plan_type: str  # monthly, yearly, lifetime


class OrderCreate(OrderBase):
    pass


class OrderResponse(OrderBase):
    id: int
    order_no: str
    amount: float
    status: str
    payment_method: Optional[str] = None
    payment_time: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Blogger Schemas ============

class BloggerBase(BaseModel):
    platform: str
    platform_user_id: str
    username: str
    avatar_url: Optional[str] = None


class BloggerCreate(BloggerBase):
    pass


class BloggerResponse(BloggerBase):
    id: int
    follower_count: int
    accuracy_score: float
    total_predictions: int
    correct_predictions: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BloggerUpdate(BaseModel):
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    follower_count: Optional[int] = None
    accuracy_score: Optional[float] = None
    total_predictions: Optional[int] = None
    correct_predictions: Optional[int] = None
    is_active: Optional[bool] = None


# ============ Prediction Schemas ============

class PredictionBase(BaseModel):
    post_url: str
    post_content: str
    post_time: datetime


class PredictionCreate(PredictionBase):
    blogger_id: int
    predicted_direction: Optional[str] = None
    predicted_target: Optional[str] = None
    confidence: float = 0.0
    llm_reasoning: Optional[str] = None
    raw_data: Optional[dict] = None


class PredictionResponse(PredictionBase):
    id: int
    blogger_id: int
    predicted_direction: Optional[str] = None
    predicted_target: Optional[str] = None
    confidence: float
    llm_reasoning: Optional[str] = None
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Prediction Verification Schemas ============

class VerificationBase(BaseModel):
    verification_date: datetime
    actual_change_pct: float
    is_correct: bool


class VerificationCreate(VerificationBase):
    prediction_id: int


class VerificationResponse(VerificationBase):
    id: int
    prediction_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Market Data Schemas ============

class MarketDataBase(BaseModel):
    symbol: str
    name: str
    trade_date: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    change_pct: float
    volume: Optional[float] = None


class MarketDataCreate(MarketDataBase):
    pass


class MarketDataResponse(MarketDataBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ News Schemas ============

class NewsBase(BaseModel):
    source: str
    title: str
    url: str
    publish_time: datetime


class NewsCreate(NewsBase):
    summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    llm_analysis: Optional[str] = None


class NewsResponse(NewsBase):
    id: int
    summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[str] = None
    llm_analysis: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Daily Signal Schemas ============

class DailySignalBase(BaseModel):
    signal_date: datetime
    target_symbol: str
    target_name: str


class DailySignalCreate(DailySignalBase):
    blogger_consensus_score: float
    news_sentiment_score: float
    final_signal: str
    confidence: float
    reasoning: str
    participating_bloggers: int = 0
    analyzed_news_count: int = 0


class DailySignalResponse(DailySignalCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Watchlist Schemas ============

class WatchlistBase(BaseModel):
    symbol: str
    name: str
    type: str  # index, fund


class WatchlistCreate(WatchlistBase):
    pass


class WatchlistResponse(WatchlistBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ Common Schemas ============

# ============ Portfolio Schemas ============

class PortfolioCreate(BaseModel):
    fund_code: str = Field(..., max_length=20)
    fund_name: str = Field(..., max_length=100)
    fund_type: str = Field(default="fund")  # fund / stock / etf
    shares: float = Field(..., gt=0)
    cost_price: float = Field(..., gt=0)
    note: Optional[str] = Field(None, max_length=200)


class PortfolioUpdate(BaseModel):
    shares: Optional[float] = Field(None, gt=0)
    cost_price: Optional[float] = Field(None, gt=0)
    note: Optional[str] = Field(None, max_length=200)


class PortfolioResponse(BaseModel):
    id: int
    fund_code: str
    fund_name: str
    fund_type: str
    shares: float
    cost_price: float
    cost_total: float
    current_price: Optional[float] = None
    current_value: Optional[float] = None
    profit_loss: Optional[float] = None
    profit_loss_pct: Optional[float] = None
    price_updated_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    """整体持仓汇总。"""
    total_cost: float
    total_value: float
    total_profit_loss: float
    total_profit_loss_pct: float
    items: list[PortfolioResponse]


class PortfolioAnalysisResponse(BaseModel):
    fund_code: str
    fund_name: str
    analyzed_at: datetime
    current_price: float
    profit_loss_pct: float
    action: str          # hold / buy_more / take_profit / stop_loss / watch
    action_label: str    # 持有 / 加仓 / 止盈 / 止损 / 观望
    reasoning: str       # LLM 给出的理由（含新手教学）

    class Config:
        from_attributes = True


class BatchAnalysisItem(BaseModel):
    fund_code: str
    fund_name: str
    action: str
    action_label: str
    reasoning: str
    profit_loss_pct: float
    error: str | None = None   # 单只失败时填错误信息，其余字段为空


class BatchAnalysisResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchAnalysisItem]


# ============ Signal Review Schemas ============

class SignalVerificationResponse(BaseModel):
    id: int
    signal_date: datetime
    target_symbol: str
    predicted_signal: str
    confidence: float
    actual_change_pct: float
    actual_direction: str
    is_correct: bool
    error_magnitude: float
    verified_at: datetime

    class Config:
        from_attributes = True


class SignalReviewResponse(BaseModel):
    id: int
    target_symbol: str
    review_start: datetime
    review_end: datetime
    reviewed_at: datetime
    total_signals: int
    correct_signals: int
    accuracy_rate: float
    trigger_reason: str
    problem_diagnosis: str
    suggested_adjustments: str
    learning_points: str
    is_pushed: bool

    class Config:
        from_attributes = True


class SignalReviewListResponse(BaseModel):
    total: int
    items: list[SignalReviewResponse]


# ============ Trade Review (用户复盘对话) Schemas ============

class TradeReviewCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=100, description="复盘标题，不填则自动生成")


class TradeReviewMessageResponse(BaseModel):
    id: int
    role: str   # "user" / "assistant"
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class TradeReviewResponse(BaseModel):
    id: int
    title: str
    preview: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradeReviewDetailResponse(TradeReviewResponse):
    """复盘详情 — 包含所有消息。"""
    messages: list[TradeReviewMessageResponse] = []


class TradeReviewListResponse(BaseModel):
    total: int
    items: list[TradeReviewResponse]


class TradeReviewChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class TradeReviewChatResponse(BaseModel):
    """AI 回复 — 同时返回 user_message_id 和 assistant_message_id 便于前端渲染。"""
    user_message: TradeReviewMessageResponse
    assistant_message: TradeReviewMessageResponse


# ============ Common Schemas ============

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: int  # user_id
    exp: datetime
