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

Deux mécanismes servent l'expérience de tolérance du timeout (v5).

Le premier est le **cycle de timeouts**. La v4 a montré qu'un nœud n'émet ses
poids qu'une fois par minute : la fenêtre de 90 s ne contient donc qu'une seule
occasion d'émettre, et une perte unique suffit à exclure le nœud. Pour tester
cela, il faut comparer plusieurs fenêtres — mais dans la *même* session, en
alternant round par round, sinon l'heure et le climat changent avec la fenêtre
et la comparaison ne vaut rien. D'où une liste de timeouts parcourue en boucle.

Le second est l'**arrêt automatique sur rounds vides**. Une série laissée
tourner après le débranchement du matériel a produit 188 rounds à vide en base.
Au-delà de quelques clôtures consécutives sans aucun participant, la boucle
s'arrête d'elle-même : il n'y a plus personne à interroger.
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

# Bornes reprises de POST /api/fl/rounds, pour que la série ne puisse pas
# demander un timeout que l'ouverture manuelle refuserait.
MIN_TIMEOUT_S = 30
MAX_TIMEOUT_S = 300
DEFAULT_TIMEOUTS = [90]

# Nombre de clôtures consécutives sans participant avant arrêt automatique.
# Trois suffisent : à 5 min d'intervalle cela laisse un quart d'heure de
# tolérance à une coupure passagère, sans laisser la série tourner la nuit.
STOP_AFTER_EMPTY = 3


class AutoRunner:
    def __init__(self) -> None:
        self.enabled = False
        self.interval_s = DEFAULT_INTERVAL_S
        self.timeouts = list(DEFAULT_TIMEOUTS)
        self.rounds_started = 0
        self.last_round_at: datetime | None = None
        self.last_timeout_s: int | None = None
        self.last_error: str | None = None
        self.stopped_reason: str | None = None
        self._cycle = 0
        self._task: asyncio.Task | None = None

    def _next_timeout(self) -> int:
        """Timeout du prochain round, en parcourant la liste en boucle."""
        return self.timeouts[self._cycle % len(self.timeouts)]

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
            "timeouts": list(self.timeouts),
            "next_timeout_s": self._next_timeout() if self.enabled else None,
            "last_timeout_s": self.last_timeout_s,
            "stop_after_empty": STOP_AFTER_EMPTY,
            "stopped_reason": self.stopped_reason,
            "rounds_started": self.rounds_started,
            "last_round_at": self.last_round_at.isoformat() if self.last_round_at else None,
            "next_in_s": next_in,
            "last_error": self.last_error,
        }

    def configure(
        self,
        enabled: bool,
        interval_s: int | None = None,
        timeouts: list[int] | None = None,
    ) -> dict:
        if interval_s is not None:
            self.interval_s = max(MIN_INTERVAL_S, min(MAX_INTERVAL_S, int(interval_s)))
        if timeouts:
            self.timeouts = [max(MIN_TIMEOUT_S, min(MAX_TIMEOUT_S, int(t))) for t in timeouts]
            self._cycle = 0
        # Un timeout plus long que l'intervalle ferait chevaucher deux rounds :
        # la garde « un round traîne encore » avalerait le suivant. On filtre à
        # chaque appel, l'intervalle ayant pu changer sans la liste.
        self.timeouts = [t for t in self.timeouts if t < self.interval_s] or list(DEFAULT_TIMEOUTS)
        if enabled and not self.enabled:
            # Reprise à zéro : le premier round part tout de suite.
            self.rounds_started = 0
            self.last_round_at = None
            self.last_error = None
            self.stopped_reason = None
            self._cycle = 0
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

            if await self._plus_personne(conn):
                self.enabled = False
                self.stopped_reason = (
                    f"{STOP_AFTER_EMPTY} rounds consécutifs sans participant : "
                    "série arrêtée pour ne pas remplir la base à vide."
                )
                log.warning("série auto arrêtée : %s", self.stopped_reason)
                return

            timeout_s = self._next_timeout()
            row = await start_round(conn, timeout_s)
            self._cycle += 1
            self.rounds_started += 1
            self.last_timeout_s = timeout_s
            # L'intervalle court depuis l'ouverture, pas la clôture : la
            # cadence reste régulière même si un round va au timeout. C'est ce
            # qui permet d'alterner les timeouts sans décaler la phase des
            # rounds par rapport à l'horloge interne des nœuds.
            self.last_round_at = now
            log.info(
                "round auto %s ouvert, timeout %s s (%s au total)",
                row.get("id"),
                timeout_s,
                self.rounds_started,
            )

    async def _plus_personne(self, conn) -> bool:
        """Vrai si les dernières clôtures sont toutes vides : plus de nœud en
        face, la série n'a plus d'objet."""
        recents = await conn.fetch(
            """
            SELECT n_nodes FROM fl_rounds
            WHERE status = 'closed'
            ORDER BY id DESC
            LIMIT $1
            """,
            STOP_AFTER_EMPTY,
        )
        if len(recents) < STOP_AFTER_EMPTY:
            return False
        return all((r["n_nodes"] or 0) == 0 for r in recents)

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
