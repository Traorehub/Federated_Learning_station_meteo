"""Historique de la liaison : réception, RSSI, SNR, latence de réponse.

La session d'inversion a montré que le **RSSI moyen ne prédit pas** l'exclusion
d'un nœud d'un round, alors que son **taux de réception** la prédit d'un facteur
deux. La raison est un biais du survivant : le RSSI n'est enregistré que sur les
paquets reçus, si bien que la disparition d'un lien ne fait pas baisser le
niveau moyen — elle fait disparaître les mesures.

D'où l'ordre des choses ici : le taux de réception est la grandeur principale,
le RSSI l'accompagne pour montrer qu'il ne la suit pas.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import asyncpg

# Période d'émission des nœuds, fixée dans le firmware (SEND_INTERVAL_MS).
SAMPLE_PERIOD_S = 15


def _iso(v: datetime) -> str:
    return v.isoformat()


async def link_history(
    conn: asyncpg.Connection,
    hours: int = 3,
    bucket_min: int = 5,
) -> dict:
    bucket_s = bucket_min * 60

    # On s'arrête au début de la tranche en cours : une tranche à moitié
    # écoulée afficherait une réception effondrée alors que rien ne va mal.
    # Même raison pour caler le début sur une frontière de tranche.
    fin = await conn.fetchval(
        "SELECT to_timestamp(floor(extract(epoch FROM now()) / $1::bigint) * $1::bigint)",
        bucket_s,
    )
    n_tranches = max(1, hours * 3600 // bucket_s)
    debut = fin - timedelta(seconds=n_tranches * bucket_s)

    rows = await conn.fetch(
        """
        SELECT node_id,
               to_timestamp(
                   (floor(extract(epoch FROM received_at) / $3::bigint) * $3::bigint)::bigint
               ) AS t,
               count(*) FILTER (WHERE checksum_ok)          AS recus,
               count(*) FILTER (WHERE NOT checksum_ok)      AS corrompus,
               avg(rssi) FILTER (WHERE checksum_ok)         AS rssi_avg,
               min(rssi) FILTER (WHERE checksum_ok)         AS rssi_min,
               avg(snr)  FILTER (WHERE checksum_ok)         AS snr_avg
        FROM readings
        WHERE node_id > 0
          AND received_at >= $1
          AND received_at <  $2
        GROUP BY node_id, t
        ORDER BY node_id, t
        """,
        debut,
        fin,
        bucket_s,
    )

    attendus = max(1, bucket_s // SAMPLE_PERIOD_S)

    def vide(t: datetime) -> dict:
        return {
            "t": _iso(t),
            "recus": 0,
            "attendus": attendus,
            "reception": 0.0,
            "corrompus": 0,
            "rssi_avg": None,
            "rssi_min": None,
            "snr_avg": None,
        }

    mesures: dict[int, dict[datetime, dict]] = {}
    for r in rows:
        recus = int(r["recus"])
        mesures.setdefault(int(r["node_id"]), {})[r["t"]] = {
            "t": _iso(r["t"]),
            "recus": recus,
            "attendus": attendus,
            # Peut dépasser 1 sur un intervalle : un paquet à cheval sur
            # deux tranches, ou une dérive d'horloge du nœud.
            "reception": min(1.0, recus / attendus),
            "corrompus": int(r["corrompus"]),
            "rssi_avg": float(r["rssi_avg"]) if r["rssi_avg"] is not None else None,
            "rssi_min": float(r["rssi_min"]) if r["rssi_min"] is not None else None,
            "snr_avg": float(r["snr_avg"]) if r["snr_avg"] is not None else None,
        }

    # Une tranche totalement muette ne ressort pas du GROUP BY : elle doit
    # apparaître comme une réception nulle, sinon la courbe saute par-dessus
    # le silence — exactement l'angle mort qu'on veut supprimer.
    instants = [debut + timedelta(seconds=i * bucket_s) for i in range(n_tranches)]

    # Même raisonnement pour un nœud resté muet sur toute la fenêtre : il doit
    # tracer une ligne à zéro, pas disparaître du graphique.
    connus = await conn.fetch("SELECT node_id FROM node_stats WHERE node_id > 0")
    for row in connus:
        mesures.setdefault(int(row["node_id"]), {})

    par_noeud = {
        nid: [par_instant.get(t) or vide(t) for t in instants]
        for nid, par_instant in mesures.items()
    }

    return {
        "hours": hours,
        "bucket_min": bucket_min,
        "sample_period_s": SAMPLE_PERIOD_S,
        "nodes": [
            {"node_id": nid, "buckets": buckets} for nid, buckets in sorted(par_noeud.items())
        ],
    }


async def response_latency(conn: asyncpg.Connection, limit: int = 40) -> dict:
    """Délai entre l'ouverture d'un round et l'arrivée des poids d'un nœud.

    C'est la latence qui compte pour FedAvg synchrone : au-delà du timeout, le
    nœud est hors moyenne même si ses poids finissent par arriver.
    """
    rows = await conn.fetch(
        """
        WITH derniers AS (
            SELECT id, started_at, closed_at, timeout_s
            FROM fl_rounds
            WHERE status = 'closed' AND closed_at IS NOT NULL
            ORDER BY id DESC
            LIMIT $1
        )
        SELECT d.id AS round_id,
               d.timeout_s,
               u.node_id,
               min(extract(epoch FROM (u.received_at - d.started_at))) AS latence_s,
               bool_or(u.received_at <= d.closed_at)                   AS dans_les_temps
        FROM derniers d
        JOIN fl_updates u ON u.round_id = d.id AND u.checksum_ok IS TRUE
        GROUP BY d.id, d.timeout_s, u.node_id
        ORDER BY d.id, u.node_id
        """,
        limit,
    )

    par_round: dict[int, dict] = {}
    for r in rows:
        entry = par_round.setdefault(
            int(r["round_id"]),
            {"round_id": int(r["round_id"]), "timeout_s": int(r["timeout_s"] or 90), "nodes": []},
        )
        entry["nodes"].append(
            {
                "node_id": int(r["node_id"]),
                "latence_s": float(r["latence_s"]),
                "dans_les_temps": bool(r["dans_les_temps"]),
            }
        )

    return {"rounds": [par_round[k] for k in sorted(par_round)]}
