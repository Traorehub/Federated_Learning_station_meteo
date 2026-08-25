from __future__ import annotations

import asyncpg

from .config import settings

pool: asyncpg.Pool | None = None


async def connect() -> asyncpg.Pool:
    global pool
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=8)
    return pool


async def close() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("database pool not initialised")
    return pool


def record_to_dict(row: asyncpg.Record) -> dict:
    out = dict(row)
    if out.get("received_at") is not None:
        out["received_at"] = out["received_at"].isoformat()
    if out.get("last_seen_at") is not None:
        out["last_seen_at"] = out["last_seen_at"].isoformat()
    return out
