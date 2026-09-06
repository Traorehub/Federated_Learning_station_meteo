"""Découpe phase stable / phase dégradée + RMSE v5 seulement."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

TMP = Path.home() / "AppData" / "Local" / "Temp"
rounds = [
    r
    for r in json.loads((TMP / "v5_rounds.json").read_text(encoding="utf-8"))["rounds"]
    if r["id"] >= 295
]
rounds.sort(key=lambda r: r["id"])
lat = [
    r
    for r in json.loads((TMP / "v5_lat.json").read_text(encoding="utf-8"))["rounds"]
    if r["round_id"] >= 295
]
err = json.loads((TMP / "v5_err.json").read_text(encoding="utf-8"))

# Phase A : radio stable jusqu'au seau 17:15 (chute nœud 1).
# Dernier round encore à 2 nœuds avant la série de dégradations : 339 (17:17).
A = [r for r in rounds if 295 <= r["id"] <= 339]
B = [r for r in rounds if 340 <= r["id"] <= 356]


def resume(nom, rs):
    print(f"=== {nom} : {rs[0]['id']}-{rs[-1]['id']}  n={len(rs)} ===")
    by = defaultdict(list)
    for r in rs:
        by[r["timeout_s"]].append(r)
    for to in sorted(by):
        xs = by[to]
        n2 = sum(1 for x in xs if (x.get("n_nodes") or 0) == 2)
        miss = {1: 0, 2: 0}
        for x in xs:
            parts = {p["node_id"] for p in (x.get("participants") or [])}
            for nid in (1, 2):
                if nid not in parts:
                    miss[nid] += 1
        print(
            f"  {to}s  {len(xs)} rounds  complets={n2}/{len(xs)}={n2/len(xs):.0%}  "
            f"exclus n1={miss[1]} n2={miss[2]}"
        )


resume("Phase A (stable)", A)
resume("Phase B (nœud 1 qui lâche)", B)

# contre-factuel phase A
print()
print("--- contre-factuel PHASE A ---")
events = {}
for r in lat:
    if not (295 <= r["round_id"] <= 339):
        continue
    for n in r["nodes"]:
        events[(r["round_id"], n["node_id"])] = n["latence_s"]

ids = [r["id"] for r in A]
for T in (90, 120, 150, 180):
    ok = {1: 0, 2: 0}
    for rid in ids:
        for nid in (1, 2):
            lat_s = events.get((rid, nid))
            if lat_s is not None and lat_s <= T:
                ok[nid] += 1
    both = sum(
        1
        for rid in ids
        if (events.get((rid, 1) or 1e9) or 1e9) <= T
        and (events.get((rid, 2) or 1e9) or 1e9) <= T
    )
    print(
        f"  T={T:3}  n1 {ok[1]}/{len(ids)}={ok[1]/len(ids):.0%}  "
        f"n2 {ok[2]}/{len(ids)}={ok[2]/len(ids):.0%}  "
        f"les deux {both}/{len(ids)}={both/len(ids):.0%}"
    )

print()
print("--- RMSE v5 phase A (si présent dans /errors) ---")
v5e = [r for r in err.get("rounds") or [] if 295 <= r.get("round_id", 0) <= 339]
print(f"rounds erreur dans A : {len(v5e)}")
if v5e:
    print("sample keys", v5e[0].keys())
    print(json.dumps(v5e[0], ensure_ascii=False)[:500])

# qui manque en B
print()
print("--- Phase B détail ---")
for r in B:
    parts = {p["node_id"] for p in (r.get("participants") or [])}
    print(f"  r{r['id']} to={r['timeout_s']} n={r['n_nodes']} parts={sorted(parts)}")
