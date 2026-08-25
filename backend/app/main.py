from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import connect, close, get_pool, record_to_dict
from .ingest import IngestPayload, ingest_reading
from .seq import loss_rate
from .ws import hub

SCHEMA_FALLBACK = """
CREATE TABLE IF NOT EXISTS readings (
    id              BIGSERIAL PRIMARY KEY,
    node_id         SMALLINT NOT NULL,
    seq             INTEGER NOT NULL DEFAULT 0,
    temperature     REAL,
    humidity        REAL,
    rssi            SMALLINT,
    snr             REAL,
    uptime_s        BIGINT,
    checksum_ok     BOOLEAN NOT NULL DEFAULT TRUE,
    error           TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_readings_node_time ON readings (node_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_readings_received ON readings (received_at DESC);
CREATE TABLE IF NOT EXISTS node_stats (
    node_id             SMALLINT PRIMARY KEY,
    last_seq            INTEGER,
    last_seen_at        TIMESTAMPTZ,
    last_rssi           SMALLINT,
    last_snr            REAL,
    last_temperature    REAL,
    last_humidity       REAL,
    packets_received    BIGINT NOT NULL DEFAULT 0,
    packets_missing     BIGINT NOT NULL DEFAULT 0,
    packets_corrupt     BIGINT NOT NULL DEFAULT 0
);
ALTER TABLE readings ALTER COLUMN temperature DROP NOT NULL;
ALTER TABLE readings ALTER COLUMN humidity DROP NOT NULL;
ALTER TABLE readings ADD COLUMN IF NOT EXISTS error TEXT;
"""


def _load_schema() -> str:
    candidates = [
        Path(__file__).resolve().parents[2] / "database" / "schema.sql",
        Path("/app/database/schema.sql"),
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return SCHEMA_FALLBACK


@asynccontextmanager
async def lifespan(_app: FastAPI):
    pool = await connect()
    async with pool.acquire() as conn:
        for stmt in _load_schema().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(stmt)
    yield
    await close()


app = FastAPI(
    title="Federated Learning IoT v1",
    description="Réception LoRa brute. Pas d'entraînement ni d'agrégation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_ingest_token(x_ingest_token: str | None = Header(default=None)) -> None:
    if not x_ingest_token or x_ingest_token != settings.ingest_token:
        raise HTTPException(status_code=401, detail="invalid ingest token")


def enrich_stats(row: dict) -> dict:
    received = int(row.get("packets_received") or 0)
    missing = int(row.get("packets_missing") or 0)
    row["loss_rate"] = loss_rate(received, missing)
    return row


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "stage": "v1", "fl": False}


@app.post("/api/ingest")
async def ingest(
    payload: IngestPayload,
    _: None = Depends(require_ingest_token),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            reading = await ingest_reading(conn, payload)
    await hub.broadcast({"type": "reading", "data": reading})
    return reading


@app.get("/api/overview")
async def overview(limit: int = Query(default=80, ge=1, le=500)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        stats = await conn.fetch("SELECT * FROM node_stats ORDER BY node_id")
        readings = await conn.fetch(
            """
            SELECT * FROM readings
            ORDER BY received_at DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "stage": "v1",
        "nodes": [enrich_stats(record_to_dict(s)) for s in stats],
        "readings": [record_to_dict(r) for r in readings],
    }


@app.get("/api/nodes/{node_id}/readings")
async def node_readings(
    node_id: int,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM readings
            WHERE node_id = $1
            ORDER BY received_at DESC
            LIMIT $2
            """,
            node_id,
            limit,
        )
    return {"node_id": node_id, "readings": [record_to_dict(r) for r in rows]}


@app.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
    except Exception:
        hub.disconnect(ws)
