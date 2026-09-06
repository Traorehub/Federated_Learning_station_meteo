"""Le lien radio explique-t-il l'exclusion d'un nœud ?

Pour chaque round, on regarde qui est entré dans la moyenne, et quelle était
la qualité de liaison du nœud pendant la fenêtre du round. Si l'exclusion est
bien causée par la radio, le RSSI doit être plus bas les fois où le nœud
manque à l'appel.
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ICI = Path(__file__).resolve().parent


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s + ":00" if s.endswith("+00") else s)


def lire(nom: str) -> list[dict]:
    with (ICI / nom).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


rounds = lire("fl_rounds.csv")
updates = lire("fl_updates.csv")
readings = [r for r in lire("readings.csv") if r["checksum_ok"] == "t" and int(r["node_id"]) > 0]

noeuds = sorted({int(r["node_id"]) for r in readings})
rssi_present: dict[int, list[float]] = defaultdict(list)
rssi_absent: dict[int, list[float]] = defaultdict(list)
recus_present: dict[int, list[float]] = defaultdict(list)
recus_absent: dict[int, list[float]] = defaultdict(list)
compte = {n: {"present": 0, "absent": 0} for n in noeuds}
duree_2, duree_1 = [], []

print("round  clos      n_nd  participants  RSSI n1  RSSI n2  duree")
for r in rounds:
    if r["status"] != "closed" or not r["closed_at"]:
        continue
    rid = int(r["id"])
    fin = parse(r["closed_at"])
    debut = parse(r["started_at"])
    duree = (fin - debut).total_seconds()

    presents = {
        int(u["node_id"])
        for u in updates
        if int(u["round_id"] or 0) == rid and parse(u["received_at"]) <= fin
    }

    # Liaison observee pendant le round (paquets capteur de la fenetre).
    # Le RSSI ne porte que sur les paquets *recus* : quand le lien lache, il
    # n'y a pas de paquet faible, il n'y a pas de paquet du tout. Le debit de
    # reception est donc le bon indicateur, pas le niveau moyen.
    rssi_round, recus_round = {}, {}
    for n in noeuds:
        fenetre = [
            x
            for x in readings
            if int(x["node_id"]) == n and debut - timedelta(seconds=30) <= parse(x["received_at"]) <= fin
        ]
        attendus = max(1, round(((fin - debut).total_seconds() + 30) / 15.0))
        recus_round[n] = len(fenetre) / attendus
        (recus_present if n in presents else recus_absent)[n].append(recus_round[n])
        if fenetre:
            rssi_round[n] = statistics.mean(float(x["rssi"]) for x in fenetre)
            (rssi_present if n in presents else rssi_absent)[n].append(rssi_round[n])
        compte[n]["present" if n in presents else "absent"] += 1

    (duree_2 if len(presents) >= 2 else duree_1).append(duree)
    fmt = lambda n: f"{rssi_round[n]:7.0f}" if n in rssi_round else "      -"
    print(
        f"{rid:5}  {fin:%H:%M:%S}  {len(presents):4}  {','.join(map(str, sorted(presents))) or '-':<12}"
        f"  {fmt(1)}  {fmt(2)}  {duree:5.0f} s"
    )

print()
print("=== Participation et liaison ===")
print()
print("noeud  rounds  present  absent  RSSI si present  RSSI si absent  recu si present  recu si absent")
moy = lambda xs: statistics.mean(xs) if xs else None
for n in noeuds:
    p, a = moy(rssi_present[n]), moy(rssi_absent[n])
    rp, ra = moy(recus_present[n]), moy(recus_absent[n])
    f = lambda v, w=15: f"{v:{w}.1f}" if v is not None else " " * (w - 1) + "-"
    pc = lambda v, w=15: f"{100 * v:{w}.0f} %" if v is not None else " " * (w - 1) + "-"
    print(
        f"{n:5} {compte[n]['present'] + compte[n]['absent']:7} {compte[n]['present']:8}"
        f" {compte[n]['absent']:7} {f(p)} {f(a)} {pc(rp)} {pc(ra)}"
    )

print()
print(f"Rounds clos avec 2 noeuds : {len(duree_2)}, duree mediane {statistics.median(duree_2):.0f} s")
print(f"Rounds clos avec 0 ou 1   : {len(duree_1)}, duree mediane {statistics.median(duree_1):.0f} s")
