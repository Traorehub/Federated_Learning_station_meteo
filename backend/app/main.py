from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import connect, close, get_pool, record_to_dict
from .fl_auto import runner as auto_runner
from .fl_error import round_errors
from .fl_ingest import FlUpdatePayload, ingest_fl_update
from .fl_rounds import list_rounds, on_weight_update, pending_commands, start_round
from .ingest import IngestPayload, ingest_reading
from .network import link_history, response_latency
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
CREATE TABLE IF NOT EXISTS fl_updates (
    id              BIGSERIAL PRIMARY KEY,
    node_id         SMALLINT NOT NULL,
    seq             INTEGER NOT NULL DEFAULT 0,
    n_samples       INTEGER NOT NULL DEFAULT 0,
    round_id        INTEGER NOT NULL DEFAULT 0,
    w0              REAL,
    w1              REAL,
    w2              REAL,
    w3              REAL,
    rssi            SMALLINT,
    snr             REAL,
    checksum_ok     BOOLEAN NOT NULL DEFAULT TRUE,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fl_updates_node_time ON fl_updates (node_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_fl_updates_round ON fl_updates (round_id, node_id, received_at DESC);
CREATE TABLE IF NOT EXISTS fl_rounds (
    id              SERIAL PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'open',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    timeout_s       INTEGER NOT NULL DEFAULT 90,
    w0              REAL,
    w1              REAL,
    w2              REAL,
    w3              REAL,
    n_total         INTEGER,
    n_nodes         INTEGER
);
CREATE TABLE IF NOT EXISTS fl_commands (
    id              SERIAL PRIMARY KEY,
    cmd             TEXT NOT NULL,
    round_id        INTEGER NOT NULL,
    w0              REAL,
    w1              REAL,
    w2              REAL,
    w3              REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acked_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_fl_commands_open ON fl_commands (acked_at, created_at);
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
    auto_runner.start()
    yield
    await auto_runner.stop()
    await close()


app = FastAPI(
    title="Federated Learning IoT",
    description="LoRa v1, poids locaux v2, FedAvg v3.",
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
    return {"ok": True, "stage": "v1", "fl": True, "fl_agg": True}


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


@app.post("/api/fl/update")
async def fl_update(
    payload: FlUpdatePayload,
    _: None = Depends(require_ingest_token),
) -> dict:
    pool = get_pool()
    closed = None
    async with pool.acquire() as conn:
        async with conn.transaction():
            update = await ingest_fl_update(conn, payload)
            if payload.round_id > 0:
                closed = await on_weight_update(conn, payload.round_id)
    await hub.broadcast({"type": "fl_update", "data": update})
    if closed is not None:
        await hub.broadcast({"type": "fl_round", "data": closed})
    return update


@app.post("/api/fl/rounds")
async def api_start_round(
    timeout_s: int = Query(default=90, ge=30, le=300),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await start_round(conn, timeout_s)
    await hub.broadcast({"type": "fl_round", "data": row})
    return row


@app.get("/api/fl/rounds")
async def api_list_rounds(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        rounds = await list_rounds(conn, limit)
    return {"rounds": rounds}


@app.get("/api/fl/auto")
async def api_auto_state() -> dict:
    return auto_runner.state()


@app.post("/api/fl/auto")
async def api_auto_configure(
    enabled: bool = Query(...),
    interval_s: int | None = Query(default=None, ge=60, le=3600),
) -> dict:
    return auto_runner.configure(enabled, interval_s)


@app.get("/api/fl/errors")
async def api_round_errors(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await round_errors(conn, limit)


@app.get("/api/fl/commands")
async def api_commands(_: None = Depends(require_ingest_token)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        commands = await pending_commands(conn)
    return {"commands": commands}


@app.get("/api/network/history")
async def api_link_history(
    hours: int = Query(default=3, ge=1, le=72),
    bucket_min: int = Query(default=5, ge=1, le=60),
) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await link_history(conn, hours, bucket_min)


@app.get("/api/network/latency")
async def api_response_latency(limit: int = Query(default=40, ge=1, le=200)) -> dict:
    pool = get_pool()
    async with pool.acquire() as conn:
        return await response_latency(conn, limit)


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
