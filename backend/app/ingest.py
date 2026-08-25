from __future__ import annotations

from datetime import datetime, timezone

import asyncpg
from pydantic import BaseModel, Field, model_validator

from .seq import loss_rate, missing_between


class IngestPayload(BaseModel):
    node_id: int = Field(default=0, ge=0, le=255)
    seq: int = Field(default=0, ge=0, le=65535)
    temp: float | None = None
    hum: float | None = Field(default=None, ge=0, le=110)
    rssi: int | None = None
    snr: float | None = None
    uptime_s: int | None = Field(default=None, ge=0)
    ok: bool = True
    error: str | None = None
    received_at: datetime | None = None

    @model_validator(mode="after")
    def valid_ok_needs_sensor(self) -> IngestPayload:
        if self.error == "bad_header":
            self.ok = False
            self.node_id = 0
            self.seq = 0
            return self
        if self.ok:
            if self.node_id < 1 or self.temp is None or self.hum is None:
                raise ValueError("paquet OK : node_id, temp et hum requis")
        return self


async def ingest_reading(conn: asyncpg.Connection, payload: IngestPayload) -> dict:
    received_at = payload.received_at or datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)

    unknown = payload.node_id == 0 or payload.error == "bad_header"

    reading_id = await conn.fetchval(
        """
        INSERT INTO readings (
            node_id, seq, temperature, humidity, rssi, snr,
            uptime_s, checksum_ok, error, received_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING id
        """,
        payload.node_id,
        payload.seq,
        payload.temp,
        payload.hum,
        payload.rssi,
        payload.snr,
        payload.uptime_s,
        payload.ok,
        payload.error,
        received_at,
    )

    missing_add = 0
    if not unknown:
        stats = await conn.fetchrow(
            "SELECT last_seq FROM node_stats WHERE node_id = $1",
            payload.node_id,
        )
        if stats is not None and stats["last_seq"] is not None:
            missing_add = missing_between(int(stats["last_seq"]), payload.seq)

    corrupt_add = 0 if payload.ok else 1

    await conn.execute(
        """
        INSERT INTO node_stats (
            node_id, last_seq, last_seen_at, last_rssi, last_snr,
            last_temperature, last_humidity,
            packets_received, packets_missing, packets_corrupt
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, 1, $8, $9)
        ON CONFLICT (node_id) DO UPDATE SET
            last_seq = CASE
                WHEN EXCLUDED.node_id = 0 THEN node_stats.last_seq
                ELSE EXCLUDED.last_seq
            END,
            last_seen_at = EXCLUDED.last_seen_at,
            last_rssi = EXCLUDED.last_rssi,
            last_snr = COALESCE(EXCLUDED.last_snr, node_stats.last_snr),
            last_temperature = COALESCE(EXCLUDED.last_temperature, node_stats.last_temperature),
            last_humidity = COALESCE(EXCLUDED.last_humidity, node_stats.last_humidity),
            packets_received = node_stats.packets_received + 1,
            packets_missing = node_stats.packets_missing + EXCLUDED.packets_missing,
            packets_corrupt = node_stats.packets_corrupt + EXCLUDED.packets_corrupt
        """,
        payload.node_id,
        payload.seq,
        received_at,
        payload.rssi,
        payload.snr,
        payload.temp,
        payload.hum,
        missing_add,
        corrupt_add,
    )

    updated = await conn.fetchrow(
        "SELECT * FROM node_stats WHERE node_id = $1",
        payload.node_id,
    )
    received = int(updated["packets_received"])
    missing = int(updated["packets_missing"])

    return {
        "id": reading_id,
        "node_id": payload.node_id,
        "seq": payload.seq,
        "temperature": payload.temp,
        "humidity": payload.hum,
        "rssi": payload.rssi,
        "snr": payload.snr,
        "uptime_s": payload.uptime_s,
        "checksum_ok": payload.ok,
        "error": payload.error,
        "received_at": received_at.isoformat(),
        "packets_received": received,
        "packets_missing": missing,
        "packets_corrupt": int(updated["packets_corrupt"]),
        "loss_rate": None if unknown else loss_rate(received, missing),
    }
