"""Envoie des lectures fictives nœuds 1 et 2, pour tester le dashboard sans hardware."""

from __future__ import annotations

import argparse
import math
import os
import random
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=os.getenv("INGEST_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.getenv("INGEST_TOKEN", "change-me"))
    parser.add_argument("--interval", type=float, default=8.0)
    args = parser.parse_args()

    seq = {1: 0, 2: 0}
    print(f"Simulateur → {args.url} (Ctrl+C pour arrêter)")

    while True:
        now = time.time()
        for node_id in (1, 2):
            seq[node_id] += 1
            # Trou de séquence occasionnel pour voir le taux de perte
            if random.random() < 0.08:
                seq[node_id] += random.randint(1, 2)
            t = 23.5 + node_id * 0.8 + 1.4 * math.sin(now / 40.0 + node_id)
            h = 48.0 + node_id * 3.0 + 4.0 * math.sin(now / 55.0 + node_id * 2)
            payload = {
                "node_id": node_id,
                "seq": seq[node_id] % 65536,
                "temp": round(t, 1),
                "hum": round(h, 1),
                "rssi": random.randint(-95, -70),
                "snr": round(random.uniform(4.0, 10.5), 2),
                "uptime_s": int(now) % 100000,
                "ok": random.random() > 0.02,
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                r = requests.post(
                    f"{args.url.rstrip('/')}/api/ingest",
                    json=payload,
                    headers={"X-Ingest-Token": args.token},
                    timeout=8,
                )
                r.raise_for_status()
                print(f"nœud {node_id} seq={payload['seq']} t={payload['temp']} rssi={payload['rssi']}")
            except requests.RequestException as exc:
                print(f"POST nœud {node_id} échoué : {exc}")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
