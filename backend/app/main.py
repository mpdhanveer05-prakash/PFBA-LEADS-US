import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.api import health, leads, counties, dashboard, appeals, auth, operations, sync, ai, outreach, appeal_packets
from app.scheduler import lifespan

if settings.sentry_dsn:
    sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.2)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

app = FastAPI(
    title="Pathfinder",
    description="AI-powered property tax appeal lead management system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:13000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(leads.router, prefix="/api", tags=["leads"])
app.include_router(counties.router, prefix="/api", tags=["counties"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(appeals.router, prefix="/api", tags=["appeals"])
app.include_router(operations.router, prefix="/api", tags=["operations"])
app.include_router(sync.router, prefix="/api", tags=["sync"])
app.include_router(ai.router, prefix="/api", tags=["ai"])
app.include_router(outreach.router, prefix="/api", tags=["outreach"])
app.include_router(appeal_packets.router, prefix="/api", tags=["appeal_packets"])
