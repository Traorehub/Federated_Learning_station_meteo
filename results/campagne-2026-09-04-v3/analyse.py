from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

p = Path(__file__).resolve().parent
updates = list(csv.DictReader((p / "fl_updates.csv").open(encoding="utf-8")))
rounds = list(csv.DictReader((p / "fl_rounds.csv").open(encoding="utf-8")))

by: dict[int, dict[int, list]] = defaultdict(lambda: defaultdict(list))
for r in updates:
    rid = int(r["round_id"] or 0)
    if rid == 0:
        continue
    by[rid][int(r["node_id"])].append(r)


def last(rid: int, nid: int):
    xs = by[rid].get(nid, [])
    return xs[-1] if xs else None


def wf(u, i):
    if not u:
        return None
    return float(u[f"w{i}"])


print("rid n | w1_n1   w1_n2   w1_g    dw1     | rssi1 rssi2 snr2")
w1s_both = []
for row in rounds:
    rid = int(row["id"])
    a, b = last(rid, 1), last(rid, 2)
    g1 = float(row["w1"]) if row["w1"] else None
    d = None
    if wf(a, 1) is not None and wf(b, 1) is not None:
        d = wf(b, 1) - wf(a, 1)
        w1s_both.append((wf(a, 1), wf(b, 1), g1, d, a["rssi"], b["rssi"]))
    snr2 = f"{float(b['snr']):6.2f}" if b else "     -"
    print(
        f"{rid:2} {row['n_nodes'] or 0} | "
        f"{wf(a,1) or 0:7.4f} {wf(b,1) or 0:7.4f} {g1 or 0:7.4f} {d or 0:7.4f} | "
        f"{(a or {}).get('rssi','-'):>5} {(b or {}).get('rssi','-'):>5} {snr2}"
    )


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("+00", "+00:00"))


print("\nduree")
for row in rounds:
    if row["closed_at"]:
        dt = (parse(row["closed_at"]) - parse(row["started_at"])).total_seconds()
        print(f"  r{row['id']}: {dt:.0f}s n={row['n_nodes']}")
