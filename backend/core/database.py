"""
Oracle DB connection pool using python-oracledb (thin mode - no Oracle Client needed).
"""
import oracledb
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Global pool
_pool: oracledb.AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    try:
        # Use thin mode — no Oracle Instant Client required
        oracledb.defaults.fetch_lobs = False
        _pool = oracledb.create_pool_async(
            user=settings.ORACLE_USER,
            password=settings.ORACLE_PASSWORD,
            dsn=settings.ORACLE_DSN,
            min=settings.ORACLE_MIN_POOL,
            max=settings.ORACLE_MAX_POOL,
            increment=settings.ORACLE_INCREMENT,
            ping_interval=30,
        )
        logger.info("Oracle connection pool created.")
    except Exception as e:
        logger.error(f"Failed to create Oracle pool: {e}")
        raise


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        logger.info("Oracle pool closed.")


@asynccontextmanager
async def get_connection() -> AsyncGenerator[oracledb.AsyncConnection, None]:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    async with _pool.acquire() as conn:
        yield conn


async def get_db() -> AsyncGenerator[oracledb.AsyncConnection, None]:
    """FastAPI dependency."""
    async with get_connection() as conn:
        yield conn
