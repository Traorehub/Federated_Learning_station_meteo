"""Erreur de prediction des modeles locaux et du modele global.

Rejoue chaque vecteur w sur les temperatures reellement mesurees apres la
cloture du round, et compare a la persistance (prediction = T[t-1]).

Le modele : T[t]/50 = w0*T[t-1]/50 + w1*T[t-2]/50 + w2*H[t-1]/100 + w3

Un triplet n'est retenu que si les trois lectures se suivent en `seq` :
un paquet perdu casse le triplet, il n'est pas evalue.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ICI = Path(__file__).resolve().parent
HORIZON = timedelta(minutes=15)


def parse(s: str) -> datetime:
    if s.endswith("+00"):
        s = s[:-3] + "+00:00"
    return datetime.fromisoformat(s)


def charger_lectures() -> dict[int, list[dict]]:
    par_noeud: dict[int, list[dict]] = defaultdict(list)
    with (ICI / "readings.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["checksum_ok"] != "t" or not r["temperature"]:
                continue
            nid = int(r["node_id"])
            if nid == 0:
                continue
            par_noeud[nid].append(
                {
                    "seq": int(r["seq"]),
                    "t": float(r["temperature"]),
                    "h": float(r["humidity"]),
                    "at": parse(r["received_at"]),
                }
            )
    for xs in par_noeud.values():
        xs.sort(key=lambda x: x["at"])
    return par_noeud


def triplets(serie: list[dict]) -> list[tuple[datetime, float, float, float, float]]:
    """(instant de la cible, T[t-2], T[t-1], H[t-1], T[t]) sur seq consecutifs."""
    out = []
    for i in range(2, len(serie)):
        a, b, c = serie[i - 2], serie[i - 1], serie[i]
        if b["seq"] != a["seq"] + 1 or c["seq"] != b["seq"] + 1:
            continue
        out.append((c["at"], a["t"], b["t"], b["h"], c["t"]))
    return out


def predire(w: list[float], t2: float, t1: float, h1: float) -> float:
    return 50.0 * (w[0] * t1 / 50.0 + w[1] * t2 / 50.0 + w[2] * h1 / 100.0 + w[3])


def rmse(w: list[float] | None, ech: list) -> float | None:
    if not ech:
        return None
    s = 0.0
    for _, t2, t1, h1, cible in ech:
        p = predire(w, t2, t1, h1) if w else t1  # w None => persistance
        s += (p - cible) ** 2
    return math.sqrt(s / len(ech))


def main() -> None:
    lectures = charger_lectures()
    tri = {nid: triplets(serie) for nid, serie in lectures.items()}

    with (ICI / "fl_rounds.csv").open(encoding="utf-8-sig") as f:
        rounds = list(csv.DictReader(f))
    with (ICI / "fl_updates.csv").open(encoding="utf-8-sig") as f:
        updates = list(csv.DictReader(f))

    print("lectures retenues :", {n: len(v) for n, v in lectures.items()})
    print("triplets seq consecutifs :", {n: len(v) for n, v in tri.items()})
    print()
    print(f"RMSE en degres C, sur les {int(HORIZON.total_seconds() / 60)} min qui suivent la cloture")
    print()
    print("round  noeud  n_ech  persistance  w local  w global  verdict")

    bilan = {"global_mieux": 0, "local_mieux": 0}
    glo_present: dict[int, list[float]] = defaultdict(list)
    glo_absent: dict[int, list[float]] = defaultdict(list)
    loc_tous: dict[int, list[float]] = defaultdict(list)
    pers_tous: dict[int, list[float]] = defaultdict(list)

    for row in rounds:
        rid = int(row["id"])
        if not row["w0"] or not row["closed_at"]:
            continue
        wg = [float(row[f"w{i}"]) for i in range(4)]
        fin = parse(row["closed_at"])

        for nid in sorted(tri):
            ech = [x for x in tri[nid] if fin < x[0] <= fin + HORIZON]
            if len(ech) < 5:
                continue

            locaux = [
                u
                for u in updates
                if int(u["round_id"] or 0) == rid
                and int(u["node_id"]) == nid
                and parse(u["received_at"]) <= fin
            ]
            wl = [float(locaux[-1][f"w{i}"]) for i in range(4)] if locaux else None

            e_pers = rmse(None, ech)
            e_loc = rmse(wl, ech) if wl else None
            e_glo = rmse(wg, ech)

            # le noeud a-t-il ete retenu dans la moyenne de ce round ?
            present = wl is not None
            (glo_present if present else glo_absent)[nid].append(e_glo)
            pers_tous[nid].append(e_pers)
            if e_loc is not None:
                loc_tous[nid].append(e_loc)

            verdict = "-"
            if e_loc is not None and e_glo is not None:
                if e_glo < e_loc:
                    verdict = "global mieux"
                    bilan["global_mieux"] += 1
                else:
                    verdict = "local mieux"
                    bilan["local_mieux"] += 1

            fmt = lambda v: f"{v:7.3f}" if v is not None else "      -"
            print(
                f"{rid:5} {nid:6} {len(ech):6}  {fmt(e_pers)}  {fmt(e_loc)}  {fmt(e_glo)}  {verdict}"
            )

    print()
    print("comparaisons local vs global :", bilan)
    print()
    print("=== RMSE moyen par noeud (degres C) ===")
    print()
    print("noeud  persistance  w local  w global si present  w global si absent  penalite")
    moy = lambda xs: sum(xs) / len(xs) if xs else None
    for nid in sorted(pers_tous):
        p, l = moy(pers_tous[nid]), moy(loc_tous[nid])
        gp, ga = moy(glo_present[nid]), moy(glo_absent[nid])
        pen = f"x{ga / gp:.1f}" if gp and ga else "-"
        f = lambda v: f"{v:11.3f}" if v is not None else "          -"
        print(
            f"{nid:5} {f(p)} {f(l)} {f(gp)}         {f(ga)}        {pen}"
        )
    print()
    print("`w global si absent` : modele que le noeud recoit quand il a rate le round.")


if __name__ == "__main__":
    main()
