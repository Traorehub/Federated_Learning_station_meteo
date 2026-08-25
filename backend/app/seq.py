SEQ_MODULUS = 65536


def missing_between(prev: int, curr: int) -> int:
    """Nombre de seq sautés entre prev et curr, wrap uint16.

    Un gros retour en arrière (reboot nœud, seq remis à 0) n'est pas
    compté comme des milliers de pertes.
    """
    if curr == prev:
        return 0
    if curr < prev and (prev - curr) > 1000:
        return 0
    return (curr - prev - 1) % SEQ_MODULUS


def loss_rate(received: int, missing: int) -> float | None:
    total = received + missing
    if total <= 0:
        return None
    return round(missing / total, 4)
