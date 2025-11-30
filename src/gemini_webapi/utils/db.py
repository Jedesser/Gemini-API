import os
import asyncio
import asyncpg
from loguru import logger

POOL: asyncpg.Pool | None = None

async def get_db_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.
    """
    global POOL
    if POOL is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise ValueError("DATABASE_URL environment variable is not set")
        
        try:
            POOL = await asyncpg.create_pool(dsn)
            logger.info("Connected to PostgreSQL database.")
            
            # Ensure table exists
            async with POOL.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS gemini_sessions (
                        secure_1psid TEXT PRIMARY KEY,
                        secure_1psidts TEXT NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE
                    );
                """)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    return POOL

async def upsert_cookie(secure_1psid: str, secure_1psidts: str):
    """
    Insert or update the cookie session in the database.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO gemini_sessions (secure_1psid, secure_1psidts, updated_at, is_active)
            VALUES ($1, $2, NOW(), TRUE)
            ON CONFLICT (secure_1psid) 
            DO UPDATE SET 
                secure_1psidts = EXCLUDED.secure_1psidts,
                updated_at = NOW(),
                is_active = TRUE;
        """, secure_1psid, secure_1psidts)
        logger.debug(f"Updated cookie in DB: {secure_1psid[:10]}...")

async def get_cookie(secure_1psid: str) -> str | None:
    """
    Get the latest secure_1psidts for a given secure_1psid.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT secure_1psidts FROM gemini_sessions 
            WHERE secure_1psid = $1 AND is_active = TRUE
        """, secure_1psid)
        return row["secure_1psidts"] if row else None

async def get_all_active_cookies() -> list[dict]:
    """
    Get all active cookie sessions.
    """
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT secure_1psid, secure_1psidts FROM gemini_sessions 
            WHERE is_active = TRUE
        """)
        return [
            {"__Secure-1PSID": r["secure_1psid"], "__Secure-1PSIDTS": r["secure_1psidts"]} 
            for r in rows
        ]

async def close_db():
    """
    Close the database pool.
    """
    global POOL
    if POOL:
        await POOL.close()
        POOL = None
