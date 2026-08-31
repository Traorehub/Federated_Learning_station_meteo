"""Lit le JSON ligne à ligne de la gateway Arduino et POST /api/ingest ou /api/fl/update."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
import serial
from dotenv import load_dotenv
from serial.tools import list_ports

load_dotenv()


def detect_port(preferred: str | None) -> str:
    if preferred:
        return preferred
    ports = list(list_ports.comports())
    if not ports:
        raise SystemExit("Aucun port série trouvé. Branche la gateway ou passe --port COMx.")
    if len(ports) == 1:
        return ports[0].device
    print("Plusieurs ports :")
    for p in ports:
        print(f"  {p.device:8}  {p.description}")
    raise SystemExit("Précise --port COMx")


def post_json(url: str, token: str, path: str, payload: dict) -> None:
    r = requests.post(
        f"{url.rstrip('/')}{path}",
        json=payload,
        headers={"X-Ingest-Token": token},
        timeout=15,
    )
    r.raise_for_status()


def route_message(msg: dict) -> tuple[str, dict] | None:
    now = datetime.now(timezone.utc).isoformat()
    if msg.get("status") or msg.get("type") == "start_round_tx":
        return None
    if msg.get("type") == "weights":
        w = msg.get("w")
        if not isinstance(w, list) or len(w) != 4 or "node_id" not in msg:
            return None
        return (
            "/api/fl/update",
            {
                "node_id": int(msg["node_id"]),
                "seq": int(msg.get("seq") or 0),
                "n_samples": int(msg.get("n_samples") or 0),
                "round_id": int(msg.get("round_id") or 0),
                "w": [float(x) for x in w],
                "rssi": msg.get("rssi"),
                "snr": msg.get("snr"),
                "ok": bool(msg.get("ok", True)),
                "received_at": now,
            },
        )
    if msg.get("error") == "bad_header" or (
        msg.get("ok") is False and "node_id" not in msg
    ):
        return (
            "/api/ingest",
            {
                "node_id": 0,
                "seq": 0,
                "temp": None,
                "hum": None,
                "rssi": msg.get("rssi"),
                "snr": msg.get("snr"),
                "ok": False,
                "error": str(msg.get("error") or "bad_header"),
                "received_at": now,
            },
        )
    if "node_id" not in msg or "seq" not in msg:
        return None
    return (
        "/api/ingest",
        {
            "node_id": int(msg["node_id"]),
            "seq": int(msg["seq"]),
            "temp": float(msg["temp"]),
            "hum": float(msg["hum"]),
            "rssi": msg.get("rssi"),
            "snr": msg.get("snr"),
            "uptime_s": msg.get("uptime_s"),
            "ok": bool(msg.get("ok", True)),
            "error": msg.get("error"),
            "received_at": now,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Pont série gateway → VPS")
    parser.add_argument("--port", default=os.getenv("SERIAL_PORT") or None)
    parser.add_argument("--baud", type=int, default=int(os.getenv("SERIAL_BAUD", "115200")))
    parser.add_argument("--url", default=os.getenv("INGEST_URL", "https://federated.near-u-api.org"))
    parser.add_argument("--token", default=os.getenv("INGEST_TOKEN", "change-me"))
    args = parser.parse_args()

    port = detect_port(args.port)
    print(f"Série {port} @ {args.baud} → {args.url}")

    while True:
        try:
            with serial.Serial(port, args.baud, timeout=1) as ser:
                print("Gateway ouverte.")
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    print(line)
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    routed = route_message(msg)
                    if routed is None:
                        continue
                    path, payload = routed
                    try:
                        post_json(args.url, args.token, path, payload)
                    except requests.RequestException as exc:
                        print(f"POST échoué : {exc}", file=sys.stderr)
        except serial.SerialException as exc:
            print(f"Série perdue ({exc}), retry dans 2 s", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    main()
