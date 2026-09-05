"""Lancement automatique des rounds, pour constituer un échantillon sans
appuyer sur le bouton toutes les trois minutes.

Le rythme n'est pas neutre. Le tampon d'un nœud contient 32 échantillons pris
toutes les 15 s : il met 8 min à se renouveler. Plus l'intervalle est court,
plus deux rounds consécutifs s'entraînent sur les mêmes données. Et chaque
clôture déclenche un downlink pendant lequel la gateway émet, donc perd des
paquets capteur — ceux-là mêmes qui servent ensuite à mesurer l'erreur.
D'où un plancher volontaire sur l'intervalle.

L'état vit en mémoire du processus : redémarrer l'API remet à l'arrêt. C'est
voulu, on ne veut pas d'un lanceur qui survive silencieusement à un déploiement.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .db import get_pool
from .fl_rounds import maybe_close_open, start_round

log = logging.getLogger("fl_auto")

DEFAULT_INTERVAL_S = 180
MIN_INTERVAL_S = 60
MAX_INTERVAL_S = 3600
TICK_S = 5


class AutoRunner:
    def __init__(self) -> None:
        self.enabled = False
        self.interval_s = DEFAULT_INTERVAL_S
        self.rounds_started = 0
        self.last_round_at: datetime | None = None
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None

    # -- état exposé à l'interface ---------------------------------------

    def state(self) -> dict:
        next_in = None
        if self.enabled:
            if self.last_round_at is None:
                next_in = 0
            else:
                elapsed = (datetime.now(timezone.utc) - self.last_round_at).total_seconds()
                next_in = max(0, round(self.interval_s - elapsed))
        return {
            "enabled": self.enabled,
            "interval_s": self.interval_s,
            "min_interval_s": MIN_INTERVAL_S,
            "rounds_started": self.rounds_started,
            "last_round_at": self.last_round_at.isoformat() if self.last_round_at else None,
            "next_in_s": next_in,
            "last_error": self.last_error,
        }

    def configure(self, enabled: bool, interval_s: int | None = None) -> dict:
        if interval_s is not None:
            self.interval_s = max(MIN_INTERVAL_S, min(MAX_INTERVAL_S, int(interval_s)))
        if enabled and not self.enabled:
            # Reprise à zéro : le premier round part tout de suite.
            self.rounds_started = 0
            self.last_round_at = None
            self.last_error = None
        self.enabled = enabled
        return self.state()

    # -- boucle ------------------------------------------------------------

    async def _tick(self) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Sans navigateur ouvert, personne d'autre ne vient clore les
            # rounds expirés : la boucle s'en charge, allumée ou non.
            await maybe_close_open(conn)
            if not self.enabled:
                return

            now = datetime.now(timezone.utc)
            if self.last_round_at is not None:
                if (now - self.last_round_at).total_seconds() < self.interval_s:
                    return

            open_id = await conn.fetchval(
                "SELECT id FROM fl_rounds WHERE status = 'open' ORDER BY id DESC LIMIT 1"
            )
            if open_id is not None:
                return  # un round traîne encore, on ne se marche pas dessus

            row = await start_round(conn)
            self.rounds_started += 1
            # L'intervalle court depuis l'ouverture, pas la clôture : la
            # cadence reste régulière même si un round va au timeout.
            self.last_round_at = now
            log.info("round auto %s ouvert (%s au total)", row.get("id"), self.rounds_started)

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
                self.last_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # une panne ponctuelle ne tue pas la boucle
                self.last_error = str(exc)
                log.warning("tick auto en échec : %s", exc)
            await asyncio.sleep(TICK_S)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None


runner = AutoRunner()
