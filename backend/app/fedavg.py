from __future__ import annotations


def average(rows: list[dict]) -> dict | None:
    """FedAvg : moyenne pondérée par n_samples (McMahan et al., 2017).

    Un nœud absent n'est pas dans rows : il n'entre pas dans la somme.
    """
    total = 0
    acc = [0.0, 0.0, 0.0, 0.0]
    for row in rows:
        n_k = int(row.get("n_samples") or 0)
        if n_k < 1:
            n_k = 1
        total += n_k
        acc[0] += n_k * float(row["w0"])
        acc[1] += n_k * float(row["w1"])
        acc[2] += n_k * float(row["w2"])
        acc[3] += n_k * float(row["w3"])
    if total <= 0:
        return None
    return {
        "w": [acc[i] / total for i in range(4)],
        "n_total": total,
        "n_nodes": len(rows),
    }
