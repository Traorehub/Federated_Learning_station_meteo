"""Erreur de prédiction des modèles, mesurée après coup sur les vraies lectures.

Un round ne peut pas être évalué à l'instant de sa clôture : les températures
qui serviraient de vérité terrain n'existent pas encore. Le RMSE est donc
calculé à la demande, sur les lectures postérieures à `closed_at`.

Modèle embarqué :  T[t]/50 = w0·T[t-1]/50 + w1·T[t-2]/50 + w2·H[t-1]/100 + w3

Référence de comparaison : la persistance, prédire T[t] = T[t-1]. Sans elle,
un RMSE seul ne dit pas si le modèle appris sert à quelque chose.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta

import asyncpg

from .fl_rounds import latest_updates_for_round

HORIZON = timedelta(minutes=15)
MIN_SAMPLES = 5

# Une cible juste après `closed_at` a besoin de T[t-1] et T[t-2], donc de
# lectures antérieures à la clôture : sans cette marge, le round le plus
# ancien perdrait ses premiers triplets.
LOOKBACK = timedelta(minutes=5)

# (instant de la cible, T[t-2], T[t-1], H[t-1], T[t])
Triplet = tuple[datetime, float, float, float, float]


def predict(w: list[float], t2: float, t1: float, h1: float) -> float:
    return 50.0 * (w[0] * t1 / 50.0 + w[1] * t2 / 50.0 + w[2] * h1 / 100.0 + w[3])


def rmse(w: list[float] | None, sample: list[Triplet]) -> float | None:
    """RMSE en °C. `w` à None évalue la persistance."""
    if not sample:
        return None
    total = 0.0
    for _, t2, t1, h1, target in sample:
        pred = predict(w, t2, t1, h1) if w else t1
        total += (pred - target) ** 2
    return math.sqrt(total / len(sample))


def build_triplets(rows: list[dict]) -> dict[int, list[Triplet]]:
    """Triplets à `seq` consécutifs, par nœud.

    Un paquet perdu casse le triplet et l'écarte : on ne veut pas d'un T[t-1]
    qui date en réalité de deux pas de temps.
    """
    by_node: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        if r["temperature"] is None or r["humidity"] is None:
            continue
        by_node[int(r["node_id"])].append(r)

    out: dict[int, list[Triplet]] = {}
    for node_id, series in by_node.items():
        series.sort(key=lambda x: x["received_at"])
        triplets: list[Triplet] = []
        for i in range(2, len(series)):
            a, b, c = series[i - 2], series[i - 1], series[i]
            if b["seq"] != a["seq"] + 1 or c["seq"] != b["seq"] + 1:
                continue
            triplets.append(
                (
                    c["received_at"],
                    float(a["temperature"]),
                    float(b["temperature"]),
                    float(b["humidity"]),
                    float(c["temperature"]),
                )
            )
        out[node_id] = triplets
    return out


async def round_errors(conn: asyncpg.Connection, limit: int = 20) -> dict:
    rounds = await conn.fetch(
        """
        SELECT id, closed_at, n_nodes, w0, w1, w2, w3
        FROM fl_rounds
        WHERE status = 'closed' AND closed_at IS NOT NULL AND w0 IS NOT NULL
        ORDER BY id DESC
        LIMIT $1
        """,
        limit,
    )
    if not rounds:
        return {"horizon_min": int(HORIZON.total_seconds() // 60), "rounds": [], "nodes": []}

    span_start = min(r["closed_at"] for r in rounds) - LOOKBACK
    span_end = max(r["closed_at"] for r in rounds) + HORIZON
    readings = await conn.fetch(
        """
        SELECT node_id, seq, temperature, humidity, received_at
        FROM readings
        WHERE checksum_ok IS TRUE
          AND node_id > 0
          AND received_at >= $1
          AND received_at <= $2
        ORDER BY received_at
        """,
        span_start,
        span_end,
    )
    triplets = build_triplets([dict(r) for r in readings])

    per_round: list[dict] = []
    present: dict[int, list[float]] = defaultdict(list)
    absent: dict[int, list[float]] = defaultdict(list)
    local_all: dict[int, list[float]] = defaultdict(list)
    pers_all: dict[int, list[float]] = defaultdict(list)

    for r in reversed(rounds):  # chronologique, pour la courbe
        closed = r["closed_at"]
        w_global = [float(r[f"w{i}"]) for i in range(4)]
        updates = await latest_updates_for_round(conn, int(r["id"]), before=closed)
        w_local = {
            int(u["node_id"]): [float(u[f"w{i}"]) for i in range(4)]
            for u in updates
            if u["w0"] is not None
        }

        entries = []
        for node_id, tri in sorted(triplets.items()):
            sample = [x for x in tri if closed < x[0] <= closed + HORIZON]
            if len(sample) < MIN_SAMPLES:
                continue
            wl = w_local.get(node_id)
            e_pers = rmse(None, sample)
            e_loc = rmse(wl, sample) if wl else None
            e_glo = rmse(w_global, sample)

            entries.append(
                {
                    "node_id": node_id,
                    "n_eval": len(sample),
                    "participated": wl is not None,
                    "rmse_persistence": e_pers,
                    "rmse_local": e_loc,
                    "rmse_global": e_glo,
                }
            )
            (present if wl is not None else absent)[node_id].append(e_glo)
            pers_all[node_id].append(e_pers)
            if e_loc is not None:
                local_all[node_id].append(e_loc)

        if entries:
            per_round.append(
                {
                    "round_id": int(r["id"]),
                    "closed_at": closed.isoformat(),
                    "n_nodes": r["n_nodes"],
                    "nodes": entries,
                }
            )

    def mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    summary = []
    for node_id in sorted(set(pers_all) | set(present) | set(absent)):
        gp, ga = mean(present[node_id]), mean(absent[node_id])
        summary.append(
            {
                "node_id": node_id,
                "rmse_persistence": mean(pers_all[node_id]),
                "rmse_local": mean(local_all[node_id]),
                "rmse_global_present": gp,
                "rmse_global_absent": ga,
                "penalty": (ga / gp) if gp and ga else None,
                "rounds_present": len(present[node_id]),
                "rounds_absent": len(absent[node_id]),
            }
        )

    return {
        "horizon_min": int(HORIZON.total_seconds() // 60),
        "rounds": per_round,
        "nodes": summary,
    }
