from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

p = Path(__file__).resolve().parent
updates = list(csv.DictReader((p / "fl_updates.csv").open(encoding="utf-8")))
rounds = list(csv.DictReader((p / "fl_rounds.csv").open(encoding="utf-8")))

by_round: dict[int, dict[int, list]] = defaultdict(lambda: defaultdict(list))
n0 = 0
for r in updates:
    rid = int(r["round_id"] or 0)
    if rid == 0:
        n0 += 1
        continue
    by_round[rid][int(r["node_id"])].append(r)

print(f"updates total={len(updates)}  periodiques round_id=0 : {n0}")
print()
print("round n_nodes n_total  n1 n2  rssi1 snr1  rssi2 snr2  w_global")
for row in rounds:
    rid = int(row["id"])
    nodes = by_round.get(rid, {})
    def last(nid: int):
        xs = nodes.get(nid, [])
        return xs[-1] if xs else None
    a, b = last(1), last(2)
    def rs(u):
        if not u:
            return "   -     -"
        return f"{u['rssi']:>5} {float(u['snr']):>6.2f}"
    wg = "-"
    if row["w0"]:
        wg = " ".join(f"{float(row[k]):.4f}" for k in ("w0", "w1", "w2", "w3"))
    print(
        f"{rid:5} {row['n_nodes'] or 0:>7} {row['n_total'] or 0:>7}  "
        f"{len(nodes.get(1, [])):>2} {len(nodes.get(2, [])):>2}  "
        f"{rs(a)}  {rs(b)}  {wg}"
    )

two = sum(1 for r in rounds if (r.get("n_nodes") or "0") == "2")
one = sum(1 for r in rounds if (r.get("n_nodes") or "0") == "1")
zero = sum(1 for r in rounds if (r.get("n_nodes") or "0") in ("0", ""))
print()
print(f"clos 2 nœuds={two}  1 nœud={one}  0 nœud={zero}  total={len(rounds)}")
