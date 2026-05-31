import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# 把 backend 目录加入 path，让 app.* 可以 import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置必要的环境变量（Alembic 运行时不读 .env，手动设置默认值）
os.environ.setdefault("LLM_API_KEY", "placeholder")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "placeholder")
os.environ.setdefault("JWT_SECRET", "placeholder")

from app.core.database import Base
from app.models.models import (  # noqa: F401 — 确保所有模型被注册
    User, Order, Blogger, Prediction, PredictionVerification,
    MarketData, News, DailySignal, Watchlist, CrawlLog,
    Portfolio, PortfolioAnalysis, SignalVerification, SignalReview,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
