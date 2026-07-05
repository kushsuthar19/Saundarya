"""
Saundarya Beauty Care & Academy — Production Backend
FastAPI + Oracle DB

Run:
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.core.config import settings
from backend.core.database import init_pool, close_pool
from backend.middleware.security import SecurityMiddleware
from backend.routers.auth import router as auth_router
from backend.routers.clients import router as clients_router
from backend.routers.entries import router as entries_router
from backend.routers.main_routers import (
    appt_router, staff_router, att_router, bridal_router,
    dash_router, revenue_router, reports_router, salary_router,
    svc_router, inquiry_router    # ← add inquiry_router here
)

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Saundarya backend...")
    await init_pool()
    # Create PDF temp dir
    os.makedirs(settings.PDF_DIR, exist_ok=True)
    logger.info("Ready.")
    yield
    await close_pool()
    logger.info("Shutdown complete.")


# ── App ───────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────
allowed_origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)

# ── Trusted Hosts (production) ────────────────────────────
if settings.ENV == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["yourdomain.com", "www.yourdomain.com"])

# ── Security Middleware ───────────────────────────────────
app.add_middleware(SecurityMiddleware)

# ── API Routers ───────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth_router,     prefix=API_PREFIX)
app.include_router(dash_router,     prefix=API_PREFIX)
app.include_router(clients_router,  prefix=API_PREFIX)
app.include_router(entries_router,  prefix=API_PREFIX)
app.include_router(appt_router,     prefix=API_PREFIX)
app.include_router(staff_router,    prefix=API_PREFIX)
app.include_router(att_router,      prefix=API_PREFIX)
app.include_router(bridal_router,   prefix=API_PREFIX)
app.include_router(revenue_router,  prefix=API_PREFIX)
app.include_router(reports_router,  prefix=API_PREFIX)
app.include_router(salary_router,   prefix=API_PREFIX)
app.include_router(svc_router,      prefix=API_PREFIX)
app.include_router(inquiry_router, prefix=API_PREFIX)

# ── Health check ──────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.ENV}


# ── Serve Frontend (SPA) ──────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str = "", request: Request = None):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        index_file = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend not found")


# ── Global error handlers ─────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"422 Validation error on {request.method} {request.url.path}: {exc.errors()}")
    # Try to log the request body
    try:
        body = await request.body()
        logger.error(f"Request body: {body.decode()[:500]}")
    except Exception:
        pass
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)[:200] if hasattr(exc, 'body') else None},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": exc.status_code},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
