from __future__ import annotations

from datetime import datetime, timezone

import asyncpg

from .fedavg import average


EXPECTED_NODES = 2
COMMAND_TTL_S = 80
GLOBAL_TTL_S = 25


def _now() -> datetime:
    return datetime.now(timezone.utc)


def round_to_dict(row) -> dict:
    d = dict(row)
    for key in ("started_at", "closed_at"):
        val = d.get(key)
        if val is not None:
            d[key] = val.isoformat()
    if d.get("w0") is not None:
        d["w"] = [d["w0"], d["w1"], d["w2"], d["w3"]]
    else:
        d["w"] = None
    d.setdefault("participants", [])
    return d


async def expire_commands(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        UPDATE fl_commands
        SET acked_at = NOW()
        WHERE acked_at IS NULL
          AND cmd = 'start_round'
          AND created_at < NOW() - make_interval(secs => $1::int)
        """,
        COMMAND_TTL_S,
    )
    await conn.execute(
        """
        UPDATE fl_commands
        SET acked_at = NOW()
        WHERE acked_at IS NULL
          AND cmd = 'global_model'
          AND created_at < NOW() - make_interval(secs => $1::int)
        """,
        GLOBAL_TTL_S,
    )


async def enqueue_command(
    conn: asyncpg.Connection,
    cmd: str,
    round_id: int,
    w: list[float] | None = None,
) -> None:
    w = w or [None, None, None, None]
    await conn.execute(
        """
        INSERT INTO fl_commands (cmd, round_id, w0, w1, w2, w3)
        VALUES ($1, $2, $3, $4, $5, $6)
        """,
        cmd,
        round_id,
        w[0],
        w[1],
        w[2],
        w[3],
    )


async def start_round(conn: asyncpg.Connection, timeout_s: int = 90) -> dict:
    open_row = await conn.fetchrow(
        "SELECT * FROM fl_rounds WHERE status = 'open' ORDER BY id DESC LIMIT 1"
    )
    if open_row is not None:
        return round_to_dict(open_row)
    row = await conn.fetchrow(
        """
        INSERT INTO fl_rounds (status, timeout_s)
        VALUES ('open', $1)
        RETURNING *
        """,
        timeout_s,
    )
    await conn.execute(
        "UPDATE fl_commands SET acked_at = NOW() WHERE acked_at IS NULL"
    )
    await enqueue_command(conn, "start_round", int(row["id"]))
    return round_to_dict(row)


async def latest_updates_for_round(
    conn: asyncpg.Connection,
    round_id: int,
    before: datetime | None = None,
) -> list:
    if before is None:
        return await conn.fetch(
            """
            SELECT DISTINCT ON (node_id)
                node_id, n_samples, w0, w1, w2, w3, rssi, snr, received_at
            FROM fl_updates
            WHERE round_id = $1 AND checksum_ok IS TRUE
            ORDER BY node_id, received_at DESC
            """,
            round_id,
        )
    return await conn.fetch(
        """
        SELECT DISTINCT ON (node_id)
            node_id, n_samples, w0, w1, w2, w3, rssi, snr, received_at
        FROM fl_updates
        WHERE round_id = $1
          AND checksum_ok IS TRUE
          AND received_at <= $2
        ORDER BY node_id, received_at DESC
        """,
        round_id,
        before,
    )


async def close_round(conn: asyncpg.Connection, round_id: int) -> dict | None:
    current = await conn.fetchrow("SELECT * FROM fl_rounds WHERE id = $1", round_id)
    if current is None:
        return None
    if current["status"] == "closed":
        return round_to_dict(current)

    updates = await latest_updates_for_round(conn, round_id)
    rows = [dict(u) for u in updates]
    agg = average(rows)
    w = agg["w"] if agg else [None, None, None, None]
    n_total = agg["n_total"] if agg else 0
    n_nodes = agg["n_nodes"] if agg else 0

    row = await conn.fetchrow(
        """
        UPDATE fl_rounds
        SET status = 'closed',
            closed_at = NOW(),
            w0 = $2, w1 = $3, w2 = $4, w3 = $5,
            n_total = $6, n_nodes = $7
        WHERE id = $1
        RETURNING *
        """,
        round_id,
        w[0],
        w[1],
        w[2],
        w[3],
        n_total,
        n_nodes,
    )
    await conn.execute(
        """
        UPDATE fl_commands
        SET acked_at = NOW()
        WHERE round_id = $1 AND cmd = 'start_round' AND acked_at IS NULL
        """,
        round_id,
    )
    if agg is not None:
        await enqueue_command(conn, "global_model", round_id, agg["w"])
    return round_to_dict(row)


async def backfill_empty(conn: asyncpg.Connection, round_id: int) -> dict | None:
    """Round déjà clos sans w : recolle les poids arrivés après le timeout."""
    current = await conn.fetchrow("SELECT * FROM fl_rounds WHERE id = $1", round_id)
    if current is None:
        return None
    if current["status"] != "closed" or current["w0"] is not None:
        return round_to_dict(current)
    updates = await latest_updates_for_round(conn, round_id)
    rows = [dict(u) for u in updates]
    agg = average(rows)
    if agg is None:
        return round_to_dict(current)
    row = await conn.fetchrow(
        """
        UPDATE fl_rounds
        SET w0 = $2, w1 = $3, w2 = $4, w3 = $5,
            n_total = $6, n_nodes = $7
        WHERE id = $1 AND w0 IS NULL
        RETURNING *
        """,
        round_id,
        agg["w"][0],
        agg["w"][1],
        agg["w"][2],
        agg["w"][3],
        agg["n_total"],
        agg["n_nodes"],
    )
    if row is None:
        current = await conn.fetchrow("SELECT * FROM fl_rounds WHERE id = $1", round_id)
        return round_to_dict(current) if current else None
    await enqueue_command(conn, "global_model", round_id, agg["w"])
    return round_to_dict(row)


async def on_weight_update(conn: asyncpg.Connection, round_id: int) -> dict | None:
    row = await maybe_close(conn, round_id)
    if row is not None and row.get("status") == "closed" and row.get("w") is None:
        row = await backfill_empty(conn, round_id)
    return row


async def maybe_close(conn: asyncpg.Connection, round_id: int) -> dict | None:
    current = await conn.fetchrow("SELECT * FROM fl_rounds WHERE id = $1", round_id)
    if current is None or current["status"] != "open":
        if current is not None and current["w0"] is None:
            return await backfill_empty(conn, round_id)
        return round_to_dict(current) if current else None
    updates = await latest_updates_for_round(conn, round_id)
    timeout_s = int(current["timeout_s"] or 90)
    started = current["started_at"]
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    expired = (_now() - started).total_seconds() >= timeout_s
    if len(updates) >= EXPECTED_NODES or expired:
        return await close_round(conn, round_id)
    return round_to_dict(current)


async def maybe_close_open(conn: asyncpg.Connection) -> None:
    rows = await conn.fetch("SELECT id FROM fl_rounds WHERE status = 'open'")
    for row in rows:
        await maybe_close(conn, int(row["id"]))


async def list_rounds(conn: asyncpg.Connection, limit: int = 20) -> list[dict]:
    await maybe_close_open(conn)
    rows = await conn.fetch(
        "SELECT * FROM fl_rounds ORDER BY id DESC LIMIT $1",
        limit,
    )
    out = []
    for row in rows:
        if row["status"] == "closed" and row["w0"] is None:
            filled = await backfill_empty(conn, int(row["id"]))
            if filled is not None:
                item = filled
                row = await conn.fetchrow("SELECT * FROM fl_rounds WHERE id = $1", row["id"])
            else:
                item = round_to_dict(row)
        else:
            item = round_to_dict(row)
        if row is None:
            out.append(item)
            continue
        cutoff = row["closed_at"] if row["w0"] is not None else None
        updates = await latest_updates_for_round(
            conn, int(row["id"]), before=cutoff
        )
        item["participants"] = [
            {
                "node_id": int(u["node_id"]),
                "n_samples": int(u["n_samples"]),
                "w": [u["w0"], u["w1"], u["w2"], u["w3"]],
                "rssi": u["rssi"],
                "snr": u["snr"],
            }
            for u in updates
        ]
        out.append(item)
    return out


async def pending_commands(conn: asyncpg.Connection) -> list[dict]:
    await expire_commands(conn)
    await maybe_close_open(conn)
    open_id = await conn.fetchval(
        "SELECT id FROM fl_rounds WHERE status = 'open' ORDER BY id DESC LIMIT 1"
    )
    if open_id is not None:
        rows = await conn.fetch(
            """
            SELECT * FROM fl_commands
            WHERE acked_at IS NULL AND cmd = 'start_round' AND round_id = $1
            ORDER BY id ASC
            LIMIT 1
            """,
            int(open_id),
        )
    else:
        rows = await conn.fetch(
            """
            SELECT * FROM fl_commands
            WHERE acked_at IS NULL AND cmd = 'global_model'
            ORDER BY id DESC
            LIMIT 1
            """
        )
    result = []
    for row in rows:
        item = {
            "id": int(row["id"]),
            "cmd": row["cmd"],
            "round_id": int(row["round_id"]),
        }
        if row["w0"] is not None:
            item["w"] = [row["w0"], row["w1"], row["w2"], row["w3"]]
        result.append(item)
    return result
