from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, DateTime, Text, Boolean, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    """User account and subscription information."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Subscription
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)  # free, monthly, yearly, lifetime
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Telegram
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, unique=True)
    telegram_bind_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="user")
    watchlist_items = relationship("Watchlist", back_populates="user")
    portfolio_items = relationship("Portfolio", back_populates="user")


class Order(Base):
    """Payment order records."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Order details
    order_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)  # monthly, yearly, lifetime
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Payment status
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, paid, cancelled, refunded
    payment_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # wechat, alipay
    payment_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Third-party data
    third_party_order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_callback_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="orders")


class Blogger(Base):
    """Financial blogger information and accuracy scores."""
    __tablename__ = "bloggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Basic info
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # xueqiu, xiaohongshu
    platform_user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Stats
    follower_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accuracy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0-100
    total_predictions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_predictions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    predictions = relationship("Prediction", back_populates="blogger")

    __table_args__ = (
        Index("idx_blogger_platform_user", "platform", "platform_user_id", unique=True),
    )


class Prediction(Base):
    """Blogger prediction records."""
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    blogger_id: Mapped[int] = mapped_column(Integer, ForeignKey("bloggers.id"), nullable=False, index=True)

    # Post details
    post_url: Mapped[str] = mapped_column(String(500), nullable=False)
    post_content: Mapped[str] = mapped_column(Text, nullable=False)
    post_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # LLM parsing result
    predicted_direction: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # bullish, bearish, neutral
    predicted_target: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # index code or fund code
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    llm_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 完整LLM返回，便于审计

    # Status
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_prediction: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # LLM判断是否为有效预测

    # Raw data
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    blogger = relationship("Blogger", back_populates="predictions")
    verification = relationship("PredictionVerification", back_populates="prediction", uselist=False)


class PredictionVerification(Base):
    """T+1 verification results for predictions."""
    __tablename__ = "prediction_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    prediction_id: Mapped[int] = mapped_column(Integer, ForeignKey("predictions.id"), nullable=False, unique=True, index=True)

    # Market data
    verification_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    actual_change_pct: Mapped[float] = mapped_column(Float, nullable=False)  # T+1 day change percentage

    # Result
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    prediction = relationship("Prediction", back_populates="verification")


class MarketData(Base):
    """Daily market index data."""
    __tablename__ = "market_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Index info
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 000300 for CSI300
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # OHLC data
    trade_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    open_price: Mapped[float] = mapped_column(Float, nullable=False)
    high_price: Mapped[float] = mapped_column(Float, nullable=False)
    low_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_market_symbol_date", "symbol", "trade_date", unique=True),
    )


class News(Base):
    """Financial news articles."""
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # News details
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # eastmoney, sina
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    publish_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Content
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LLM analysis
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # -1 to 1
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # negative, neutral, positive
    llm_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 完整LLM返回，便于审计

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class DailySignal(Base):
    """Daily comprehensive investment signals."""
    __tablename__ = "daily_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Signal date
    signal_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, unique=True, index=True)

    # Target
    target_symbol: Mapped[str] = mapped_column(String(20), nullable=False)  # Default: 000300
    target_name: Mapped[str] = mapped_column(String(50), nullable=False)

    # Signal components
    blogger_consensus_score: Mapped[float] = mapped_column(Float, nullable=False)  # -1 to 1
    news_sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)  # -1 to 1

    # Final signal
    final_signal: Mapped[str] = mapped_column(String(20), nullable=False)  # strong_buy, buy, hold, sell, strong_sell
    confidence: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100

    # Explanation
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)

    # Stats
    participating_bloggers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    analyzed_news_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Portfolio(Base):
    """用户持仓记录。"""
    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 标的信息
    fund_code: Mapped[str] = mapped_column(String(20), nullable=False)
    fund_name: Mapped[str] = mapped_column(String(100), nullable=False)
    fund_type: Mapped[str] = mapped_column(String(20), default="fund", nullable=False)  # fund / stock / etf

    # 持仓数据
    shares: Mapped[float] = mapped_column(Float, nullable=False)           # 持有份额/股数
    cost_price: Mapped[float] = mapped_column(Float, nullable=False)       # 成本价（每份/每股）
    cost_total: Mapped[float] = mapped_column(Float, nullable=False)       # 总成本

    # 最新行情（定期更新）
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 最新净值/价格
    current_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 当前市值
    profit_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)     # 盈亏金额
    profit_loss_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True) # 盈亏比例
    price_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 备注
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="portfolio_items")

    __table_args__ = (
        Index("idx_portfolio_user_fund", "user_id", "fund_code", unique=True),
    )


class PortfolioAnalysis(Base):
    """持仓分析记录 — 每次 LLM 分析结果存档。"""
    __tablename__ = "portfolio_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    fund_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # 分析时的快照
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    profit_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)

    # LLM 建议
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # hold / buy_more / take_profit / stop_loss / watch
    action_label: Mapped[str] = mapped_column(String(20), nullable=False)  # 中文标签
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    llm_raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class Watchlist(Base):
    """User watchlist for specific funds/indices."""
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Target
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # index, fund

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="watchlist_items")

    __table_args__ = (
        Index("idx_watchlist_user_symbol", "user_id", "symbol", unique=True),
    )


class CrawlLog(Base):
    """每次爬虫运行的完整日志，便于审计和排查问题。"""
    __tablename__ = "crawl_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # 爬虫标识
    crawler_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # xueqiu / news / market_data
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # 结果统计
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success / partial / failed
    items_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # 抓到多少条
    items_saved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)     # 新存多少条（去重后）
    items_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)   # 重复跳过多少条

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 完整原始数据快照（JSON），方便回溯
    raw_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 耗时（秒）
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class SignalVerification(Base):
    """DailySignal T+1 验证记录 — 信号发出后，次日对比实际涨跌。"""
    __tablename__ = "signal_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("daily_signals.id"), nullable=False, index=True)

    # 信号快照（冗余存储，方便复盘时不用 join）
    signal_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    target_symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    predicted_signal: Mapped[str] = mapped_column(String(20), nullable=False)   # strong_buy/buy/hold/sell/strong_sell
    blogger_consensus_score: Mapped[float] = mapped_column(Float, nullable=False)
    news_sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # 实际结果
    actual_change_pct: Mapped[float] = mapped_column(Float, nullable=False)     # 次日实际涨跌幅
    actual_direction: Mapped[str] = mapped_column(String(10), nullable=False)   # up / down / flat
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)           # 方向是否预测正确
    error_magnitude: Mapped[float] = mapped_column(Float, nullable=False)       # 偏差幅度（预测强度 vs 实际）

    # 验证时间
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    signal = relationship("DailySignal", backref="verification")

    __table_args__ = (
        Index("idx_sigverify_symbol_date", "target_symbol", "signal_date", unique=True),
    )


class SignalReview(Base):
    """信号复盘报告 — 连续出错时触发 LLM 深度复盘，存档供人工参考。"""
    __tablename__ = "signal_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    target_symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # 复盘覆盖的时间窗口
    review_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # 统计摘要
    total_signals: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_signals: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy_rate: Mapped[float] = mapped_column(Float, nullable=False)         # 准确率 0-1
    trigger_reason: Mapped[str] = mapped_column(String(100), nullable=False)    # 触发原因描述

    # LLM 复盘内容
    problem_diagnosis: Mapped[str] = mapped_column(Text, nullable=False)        # 问题诊断
    suggested_adjustments: Mapped[str] = mapped_column(Text, nullable=False)    # 建议调整方向
    learning_points: Mapped[str] = mapped_column(Text, nullable=False)          # 新手学习要点
    llm_raw_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 是否已推送给用户
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
