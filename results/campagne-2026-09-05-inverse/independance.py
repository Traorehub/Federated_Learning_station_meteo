"""Les mesures d'erreur sont-elles indépendantes les unes des autres ?

Les rounds tombent toutes les 5 min et l'erreur est évaluée sur les 15 min qui
suivent chaque clôture : deux rounds voisins partagent donc les deux tiers de
leurs températures. La pénalité annoncée s'appuie sur moins d'observations
distinctes qu'il n'y paraît.

Le test : refaire le calcul en raccourcissant l'horizon jusqu'à ce que les
fenêtres cessent de se chevaucher. Si la pénalité survit, elle ne doit rien au
recouvrement. On mesure aussi la dispersion, absente du premier calcul.
"""

from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ICI = Path(__file__).resolve().parent
HORIZONS = [15, 10, 5, 3]
MIN_SAMPLES = 5


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s + ":00" if s.endswith("+00") else s)


def lire(nom: str) -> list[dict]:
    with (ICI / nom).open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def triplets(serie: list[dict]) -> list[tuple]:
    out = []
    for i in range(2, len(serie)):
        a, b, c = serie[i - 2], serie[i - 1], serie[i]
        if b["seq"] != a["seq"] + 1 or c["seq"] != b["seq"] + 1:
            continue
        out.append((c["at"], a["t"], b["t"], b["h"], c["t"]))
    return out


def rmse(w: list[float], ech: list) -> float:
    s = sum((50.0 * (w[0] * t1 / 50 + w[1] * t2 / 50 + w[2] * h1 / 100 + w[3]) - cible) ** 2
            for _, t2, t1, h1, cible in ech)
    return math.sqrt(s / len(ech))


# --- chargement -------------------------------------------------------------

par_noeud: dict[int, list[dict]] = defaultdict(list)
for r in lire("readings.csv"):
    if r["checksum_ok"] != "t" or not r["temperature"] or int(r["node_id"]) == 0:
        continue
    par_noeud[int(r["node_id"])].append(
        {"seq": int(r["seq"]), "t": float(r["temperature"]),
         "h": float(r["humidity"]), "at": parse(r["received_at"])}
    )
for v in par_noeud.values():
    v.sort(key=lambda x: x["at"])
tri = {n: triplets(v) for n, v in par_noeud.items()}

rounds = [r for r in lire("fl_rounds.csv") if r["w0"] and r["closed_at"]]
updates = lire("fl_updates.csv")


# --- recouvrement des fenetres ---------------------------------------------

clotures = sorted(parse(r["closed_at"]) for r in rounds)
ecarts = [(b - a).total_seconds() / 60 for a, b in zip(clotures, clotures[1:])]
print(f"{len(rounds)} rounds evalues, ecart median entre clotures : {statistics.median(ecarts):.1f} min")
print()

print("horizon  fenetres disjointes  recouvrement moyen")
for h in HORIZONS:
    # Plus grand sous-ensemble de fenetres qui ne se chevauchent pas.
    dernier, disjointes = None, 0
    for t in clotures:
        if dernier is None or (t - dernier).total_seconds() / 60 >= h:
            disjointes += 1
            dernier = t
    recouvre = statistics.mean(max(0.0, 1 - e / h) for e in ecarts)
    print(f"{h:5} min  {disjointes:19}  {100 * recouvre:16.0f} %")

print()
print("=== Penalite recalculee selon l'horizon ===")
print()
print("horizon  noeud  n present  n absent  global present  global absent  penalite")

for h in HORIZONS:
    horizon = timedelta(minutes=h)
    present: dict[int, list[float]] = defaultdict(list)
    absent: dict[int, list[float]] = defaultdict(list)

    for row in rounds:
        rid = int(row["id"])
        wg = [float(row[f"w{i}"]) for i in range(4)]
        fin = parse(row["closed_at"])
        for nid in sorted(tri):
            ech = [x for x in tri[nid] if fin < x[0] <= fin + horizon]
            if len(ech) < MIN_SAMPLES:
                continue
            a_participe = any(
                int(u["round_id"] or 0) == rid and int(u["node_id"]) == nid
                and u["w0"] and parse(u["received_at"]) <= fin
                for u in updates
            )
            (present if a_participe else absent)[nid].append(rmse(wg, ech))

    for nid in sorted(present.keys() | absent.keys()):
        p, a = present[nid], absent[nid]
        mp = statistics.mean(p) if p else None
        ma = statistics.mean(a) if a else None
        sp = statistics.stdev(p) if len(p) > 1 else 0.0
        sa = statistics.stdev(a) if len(a) > 1 else 0.0
        pen = f"x{ma / mp:.2f}" if mp and ma else "-"
        fp = f"{mp:.3f} +-{sp:.3f}" if mp else "     -"
        fa = f"{ma:.3f} +-{sa:.3f}" if ma else "     -"
        print(f"{h:5} min  {nid:5} {len(p):10} {len(a):9}  {fp:>14}  {fa:>13}  {pen}")
    print()
