"""Analyse de la session v5 : timeout 90 / 120 / 150 alternés."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

TMP = Path.home() / "AppData" / "Local" / "Temp"
ICI = Path(__file__).resolve().parent
V5 = 295


def load(name: str):
    return json.loads((TMP / name).read_text(encoding="utf-8"))


def slot(lat: float) -> int:
    """1 = créneau nominal (~50 s), 2 = +60 s, 3 = +120 s."""
    if lat < 90:
        return 1
    if lat < 150:
        return 2
    return 3


rounds = [r for r in load("v5_rounds.json")["rounds"] if r["id"] >= V5]
rounds.sort(key=lambda r: r["id"])
lat_raw = [r for r in load("v5_lat.json")["rounds"] if r["round_id"] >= V5]
hist = load("v5_hist.json")
err = load("v5_err.json")

# --- export CSV locaux -------------------------------------------------
with (ICI / "fl_rounds.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(
        [
            "id",
            "status",
            "started_at",
            "closed_at",
            "timeout_s",
            "n_nodes",
            "n_total",
            "participants",
        ]
    )
    for r in rounds:
        parts = ",".join(str(p["node_id"]) for p in (r.get("participants") or []))
        w.writerow(
            [
                r["id"],
                r["status"],
                r.get("started_at"),
                r.get("closed_at"),
                r.get("timeout_s"),
                r.get("n_nodes"),
                r.get("n_total"),
                parts,
            ]
        )

with (ICI / "latence.csv").open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["round_id", "node_id", "timeout_s", "latence_s", "dans_les_temps"])
    for r in sorted(lat_raw, key=lambda x: x["round_id"]):
        for n in r.get("nodes") or []:
            w.writerow(
                [
                    r["round_id"],
                    n["node_id"],
                    r["timeout_s"],
                    f"{n['latence_s']:.6f}",
                    "t" if n["dans_les_temps"] else "f",
                ]
            )

print(f"rounds v5: {len(rounds)}  ids {rounds[0]['id']} -> {rounds[-1]['id']}")
print(f"premier {rounds[0]['started_at']}")
print(f"dernier {rounds[-1]['started_at']}")
print()

# tail vide
print("--- n_nodes par round ---")
for r in rounds:
    print(
        f"r{r['id']:3}  to={r['timeout_s']:3}  n={r.get('n_nodes')}  "
        f"{(r.get('started_at') or '')[:19]}"
    )

utiles = [r for r in rounds if (r.get("n_nodes") or 0) > 0]
vides = [r for r in rounds if (r.get("n_nodes") or 0) == 0]
print()
print(f"utiles={len(utiles)}  vides={len(vides)}")
if vides:
    print("vides:", [r["id"] for r in vides])

print()
print("--- participation par timeout (rounds utiles + vides de queue exclus) ---")
# On garde les vides du milieu s'il y en a ; on écarte seulement la queue
# après le dernier round non vide.
dernier_utile = max(r["id"] for r in utiles) if utiles else 0
session = [r for r in rounds if r["id"] <= dernier_utile]

by_to: dict[int, list] = defaultdict(list)
for r in session:
    by_to[r["timeout_s"]].append(r)

for to in sorted(by_to):
    rs = by_to[to]
    n0 = sum(1 for x in rs if (x.get("n_nodes") or 0) == 0)
    n1 = sum(1 for x in rs if (x.get("n_nodes") or 0) == 1)
    n2 = sum(1 for x in rs if (x.get("n_nodes") or 0) == 2)
    miss1 = miss2 = 0
    for x in rs:
        parts = {p["node_id"] for p in (x.get("participants") or [])}
        if 1 not in parts:
            miss1 += 1
        if 2 not in parts:
            miss2 += 1
    print(
        f"  {to}s : {len(rs)} rounds  "
        f"2 nœuds={n2}  1 nœud={n1}  vide={n0}  "
        f"exclus n1={miss1} n2={miss2}  "
        f"complets={n2 / len(rs):.0%}"
    )

print()
print("--- latences : créneau et sort ---")
events = []
for r in lat_raw:
    if r["round_id"] > dernier_utile:
        continue
    for n in r.get("nodes") or []:
        events.append(
            {
                "rid": r["round_id"],
                "to": r["timeout_s"],
                "nid": n["node_id"],
                "lat": n["latence_s"],
                "ok": n["dans_les_temps"],
                "slot": slot(n["latence_s"]),
            }
        )

sauve = []
manque = []
for e in events:
    if e["slot"] >= 2:
        ligne = (
            f"  r{e['rid']}  n{e['nid']}  to={e['to']}  "
            f"{e['lat']:.1f}s  slot={e['slot']}  "
            f"{'SAUVÉ' if e['ok'] else 'EXCLU'}"
        )
        print(ligne)
        (sauve if e["ok"] else manque).append(e)

print()
print(f"seconds+ essais : {len(sauve) + len(manque)}")
print(f"  sauvés par la fenêtre : {len(sauve)}")
print(f"  exclus malgré tout    : {len(manque)}")

print()
print("--- contre-factuel : même latences, autre timeout ---")
# Pour chaque (round, noeud) observé, aurait-il été à temps si timeout = T ?
# Les absents totaux (pas de paquet du tout dans le round) restent absents.
presents = {(e["rid"], e["nid"]): e for e in events}
ids_session = [r["id"] for r in session]
for T in (90, 120, 150, 180):
    ok1 = ok2 = 0
    tot = 0
    for rid in ids_session:
        for nid in (1, 2):
            tot += 1
            e = presents.get((rid, nid))
            if e and e["lat"] <= T:
                if nid == 1:
                    ok1 += 1
                else:
                    ok2 += 1
    print(
        f"  si timeout={T:3}s : n1 {ok1}/{len(ids_session)} ({ok1/len(ids_session):.0%})  "
        f"n2 {ok2}/{len(ids_session)} ({ok2/len(ids_session):.0%})  "
        f"les deux {(min(ok1, ok2))}"
    )

print()
print("--- latence nominale (slot 1 seulement) ---")
for nid in (1, 2):
    xs = [e["lat"] for e in events if e["nid"] == nid and e["slot"] == 1]
    if xs:
        print(
            f"  n{nid}: n={len(xs)}  med={median(xs):.1f}  "
            f"min={min(xs):.1f}  max={max(xs):.1f}"
        )

print()
print("--- réception (seaux 15 min, session) ---")
# seaux qui chevauchent 13:30-19:00 UTC
for node in hist.get("nodes") or []:
    nid = node["node_id"]
    rec = att = corr = 0
    rssis, snrs = [], []
    print(f"  nœud {nid}")
    for b in node.get("buckets") or []:
        t = b["t"][:16]
        if t < "2026-09-06T13:30" or t >= "2026-09-06T19:15":
            continue
        rec += b["recus"]
        att += b["attendus"]
        corr += b["corrompus"]
        if b.get("rssi_avg") is not None:
            rssis.append(b["rssi_avg"])
        if b.get("snr_avg") is not None:
            snrs.append(b["snr_avg"])
        print(
            f"    {t}  rec={b['recus']:2}/{b['attendus']}  "
            f"rx={b['reception']:.0%}  rssi={b.get('rssi_avg')}  "
            f"snr={b.get('snr_avg')}  bad={b['corrompus']}"
        )
    if att:
        print(
            f"    TOTAL rec={rec}/{att} = {rec/att:.0%}  "
            f"corrompus={corr}  rssi~{median(rssis) if rssis else '-'}  "
            f"snr~{median(snrs) if snrs else '-'}"
        )

print()
print("--- RMSE agrégé (nodes) ---")
for n in err.get("nodes") or []:
    print(
        f"  n{n['node_id']}: present={n.get('rounds_present')}  "
        f"absent={n.get('rounds_absent')}  "
        f"pen={n.get('penalty')}  "
        f"loc={n.get('rmse_local')}  "
        f"g_ok={n.get('rmse_global_present')}  "
        f"g_abs={n.get('rmse_global_absent')}"
    )
