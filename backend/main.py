from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, orders, telegram, portfolio, bloggers, signals
from app.scheduler.scheduler import setup_scheduler

# Create FastAPI app
app = FastAPI(
    title="FundRadar API",
    description="AI-driven fund investment signal platform",
    version="0.1.0",
    docs_url=f"{settings.API_PREFIX}/docs",
    redoc_url=f"{settings.API_PREFIX}/redoc",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(orders.router, prefix=settings.API_PREFIX)
app.include_router(telegram.router, prefix=settings.API_PREFIX)
app.include_router(portfolio.router, prefix=settings.API_PREFIX)
app.include_router(bloggers.router, prefix=settings.API_PREFIX)
app.include_router(signals.router, prefix=settings.API_PREFIX)


@app.on_event("startup")
async def startup():
    import asyncio
    from app.scheduler.jobs import start_polling
    scheduler = setup_scheduler()
    scheduler.start()
    # 后台启动 Telegram 长轮询
    asyncio.create_task(start_polling())


@app.on_event("shutdown")
async def shutdown():
    from app.scheduler.scheduler import scheduler
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "fund-radar", "version": "0.1.0"}


@app.get(f"{settings.API_PREFIX}/health")
async def api_health_check():
    return {"status": "ok", "service": "fund-radar-api", "version": "0.1.0"}

