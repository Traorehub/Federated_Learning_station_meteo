from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
from pydantic import BaseModel, Field


class FlUpdatePayload(BaseModel):
    node_id: int = Field(ge=1, le=255)
    seq: int = Field(default=0, ge=0, le=65535)
    n_samples: int = Field(default=0, ge=0)
    round_id: int = Field(default=0, ge=0)
    w: list[float] = Field(min_length=4, max_length=4)
    rssi: int | None = None
    snr: float | None = None
    ok: bool = True
    received_at: datetime | None = None


async def ingest_fl_update(conn: asyncpg.Connection, payload: FlUpdatePayload) -> dict:
    received_at = payload.received_at or datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    w = payload.w
    row_id = await conn.fetchval(
        """
        INSERT INTO fl_updates (
            node_id, seq, n_samples, round_id,
            w0, w1, w2, w3, rssi, snr, checksum_ok, received_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING id
        """,
        payload.node_id,
        payload.seq,
        payload.n_samples,
        payload.round_id,
        w[0],
        w[1],
        w[2],
        w[3],
        payload.rssi,
        payload.snr,
        payload.ok,
        received_at,
    )
    return {
        "id": row_id,
        "node_id": payload.node_id,
        "seq": payload.seq,
        "n_samples": payload.n_samples,
        "round_id": payload.round_id,
        "w": w,
        "rssi": payload.rssi,
        "snr": payload.snr,
        "checksum_ok": payload.ok,
        "received_at": received_at.isoformat(),
    }
