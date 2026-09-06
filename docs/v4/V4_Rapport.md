# v4 : historique de la liaison et latence de réponse

La v3 mesure l’erreur du modèle, mais ne dit rien de l’évolution du lien dans le temps : RSSI et SNR n’y sont que ceux du paquet de poids d’un round. La v4 historise la liaison — **taux de réception**, RSSI, SNR — et mesure la **latence de réponse** de chaque nœud à chaque round.

Le choix d’historiser la réception plutôt que le seul RSSI vient directement de la [session d’inversion](../v3/V3_Session_inversion.md) : le niveau de signal moyen s’y est révélé aveugle à la dégradation, par biais du survivant, là où le débit de réception séparait nettement participation et exclusion.

Session mesurée sur **35 rounds** (72 à 106), export `results/campagne-2026-09-05-reseau/`. Placement identique à la session d’inversion : nœud 1 (WROOM-32D) en pièce éloignée, nœud 2 (ESP32-S3) à ~2 m, les deux à 14 dBm.

## Ce que la v4 mesure

Le taux de réception est le rapport entre les paquets reçus et les paquets **attendus** sur un intervalle, l’attendu se déduisant de la période d’échantillonnage de 15 s. C’est la seule des trois grandeurs qui voit un paquet manquant : le RSSI et le SNR n’existent que pour les paquets arrivés.

La latence de réponse est le délai entre l’ouverture d’un round et l’arrivée du **premier** vecteur de poids d’un nœud. C’est la grandeur qui décide de la participation : au-delà du timeout, le nœud est hors moyenne même si ses poids finissent par arriver.

## API

| Route | Rôle |
|---|---|
| `GET /api/network/history?hours=&bucket_min=` | Réception, RSSI, SNR par nœud et par intervalle |
| `GET /api/network/latency?limit=` | Latence par round et par nœud, avec le drapeau « dans les temps » |

Deux précautions de conception, imposées par le biais du survivant. La grille temporelle est construite **en Python et complète**, puis remplie : un intervalle sans aucun paquet apparaît explicitement à zéro au lieu de disparaître de la série. De même, les nœuds sont énumérés depuis `node_stats` et non depuis les lectures de la fenêtre, sans quoi un nœud totalement muet serait absent de la réponse — c’est-à-dire invisible au moment précis où il faudrait le voir.

L’intervalle de départ est aligné sur une frontière de seau et seuls les seaux révolus sont renvoyés, pour qu’aucune barre tronquée ne se lise comme une dégradation.

## Frontend

Vue `#reseau` : une courbe du taux de réception, une courbe du RSSI, et un tableau des latences par round avec les dépassements marqués. La vue n’a **aucun bouton**, volontairement — elle ne pilote rien, elle relit ce que la collecte a produit. Le pilotage des rounds reste dans `#rounds`.

## Fichiers

```text
backend/app/network.py                    link_history, response_latency
backend/app/main.py                       les deux routes
frontend/src/components/NetworkView.tsx   courbes et tableau
frontend/src/nodeColor.ts                 couleurs partagées avec ErrorPanel
frontend/src/types.ts                     LinkBucket, LinkHistory, RoundLatency
frontend/src/api.ts                       fetchLinkHistory, fetchLatency
```

## Session expérimentale

Du 5 septembre 15:58 à 19:35 UTC, en série automatique à 5 min. 28 rounds sur 35 se sont clos avec les deux nœuds. Lectures exportées de 15:45 à 19:40 UTC, soit 1584 lectures et 374 paquets de poids.

### Qualité de liaison

Sur les seaux de 15 minutes complets :

| Nœud | Réception | RSSI moyen | SNR moyen | Paquets corrompus |
|---|---|---|---|---|
| 1 (éloigné) | 83 % | −94 dBm | +4,7 dB | **0** |
| 2 (proche) | 87 % | −61 dBm | +9,1 dB | **0** |

Aucun paquet corrompu sur toute la fenêtre. Quand un paquet arrive, il arrive intact : **la dégradation est binaire, jamais partielle**. C’est le pendant mécanique du biais du survivant — il n’existe pas de paquet à demi reçu dont le RSSI pourrait témoigner.

### La latence est verrouillée sur l’horloge des nœuds

| Nœud | Latence médiane | Écart-type | Étendue | Hors délai |
|---|---|---|---|---|
| 1 | 45,91 s | 0,66 s | 44,7 – 47,0 | 4 / 33 |
| 2 | 38,55 s | 0,89 s | 37,5 – 41,4 | 1 / 33 |

Moins d’une seconde de dispersion sur une trentaine de rounds. Ce n’est pas une variabilité de propagation, c’est une horloge. Les créneaux mesurés dans la minute le confirment :

| Nœud | Lectures capteur | Envoi des poids |
|---|---|---|
| 1 | :06, :21, :36, :51 | ~:07 |
| 2 | :14, :29, :44, :59 | ~:00 |

Les poids partent juste après une lecture capteur, décalés de 200 ms par nœud — c’est le `delay(200U * NODE_ID)` du firmware, prévu pour éviter que les deux nœuds parlent ensemble.

Un round se ferme à l’arrivée du **second** nœud, donc au créneau du nœud 1, donc vers :07-:08 de la minute — quelle que soit l’heure d’ouverture. Observé sur toute la session : 17:15:07,8 puis 18:45:08,0 puis 19:35:08,1.

**La démonstration** tient à une interruption fortuite. La série s’est arrêtée 51 minutes pendant le déploiement de la v4 (round 74 à 16:08, round 75 à 16:59) et a repris à une phase différente : les rounds s’ouvraient à :12 avant, à :22 après.

| Rounds | Ouverture | Attente prédite jusqu’au créneau | Latence mesurée (nœud 1) |
|---|---|---|---|
| 72 à 74 | :12 | :12 → :07 = **55 s** | 54,1 s |
| 75 à 106 | :22 | :22 → :07 = **45 s** | 45,9 s |

La prédiction tombe juste dans les deux configurations. La latence n’est rien d’autre que l’attente jusqu’au prochain créneau du nœud. Le serveur ouvre le round ; les nœuds décident quand il se ferme.

Le round 74, resté le round courant pendant les 51 minutes de l’interruption, a reçu **43 et 40** paquets de poids — ce qui confirme indépendamment la cadence d’une émission par minute et par nœud.

### Le signal `start_round` ne déclenche aucune réponse

C’est le constat le plus inattendu de la session. Voici l’espacement réel des paquets de poids dans un round, en secondes après l’ouverture :

| Nœud | Arrivées (round 95) | Écarts |
|---|---|---|
| 1 | 45,4 · 105,2 · 165,4 · 225,3 · 285,4 | 59,9 · 60,1 · 59,9 · 60,1 |
| 2 | 38,3 · 98,6 · 158,0 · 218,4 · 278,2 | 60,4 · 59,3 · 60,4 · 59,8 |

Exactement 60 secondes, cinq paquets par round — un round durant 5 minutes, le nœud garde le `round_id` courant et émet cinq fois. Et **jamais rien dans les premières secondes**, sur 33 rounds et deux nœuds. Les écarts de 119,8 s observés ailleurs sont des pertes unitaires : une émission ratée vaut deux cycles.

Or le firmware appelle bien `fl_train()` puis `sendWeights()` dès la réception de `start_round`, et le `round_id` des poids est correct — donc les nœuds **entendent** le signal, le serveur ne les re-tague pas (`POST /api/fl/update` reprend le `round_id` du paquet). La réponse immédiate est donc émise et n’arrive jamais.

La cause n’est pas établie. La piste la plus plausible est que la voie immédiate de `pollDownlink()` n’a pas le décalage par nœud que possède la voie périodique : les deux nœuds, entendant la même diffusion au même instant, répondent ensemble. Le journal série d’un nœud tranchera. En attendant, le fait est acquis et suffit aux conclusions ci-dessous.

### Une seule occasion d’émettre par fenêtre de timeout

C’est la conséquence structurelle, et elle explique un chiffre qui paraissait contradictoire.

Un round ouvert à :22 avec un timeout de 90 s expire à :52 de la minute suivante. Les créneaux du nœud 1 dans cet intervalle sont à +45 s… et le suivant à +105 s. **Il n’y en a qu’un.**

La fenêtre ne contient donc aucune seconde chance : un paquet de poids perdu vaut exclusion garantie, pour les deux nœuds (38 + 60 = 98 s dépasse aussi 90 s). Les dépassements observés le confirment sans exception — 105,1, 107,3, 108,9 et 114,2 s pour le nœud 1, 99,1 s pour le nœud 2 : toujours la latence normale plus un cycle de 60 s, jamais autre chose.

C’est ce qui réconcilie les 17 % de perte paquet du nœud 1 avec ses 37 % d’exclusions dans la session d’inversion. La radio n’est pas deux fois plus mauvaise que mesurée : **le protocole convertit chaque perte unitaire en exclusion totale, sans amortissement**. Pour tolérer une perte, le timeout devrait dépasser 105 s.

### Le modèle global n’a pas convergé

Sur la fenêtre exportée, l’agrégat dérive de façon monotone :

| Round | $w_0$ | $w_1$ | $w_2$ | $w_3$ |
|---|---|---|---|---|
| 72 | 0,4814 | 0,2541 | 0,0766 | 0,1159 |
| 88 | 0,4259 | 0,2196 | 0,0815 | 0,1387 |
| 106 | 0,3991 | 0,2078 | 0,0830 | 0,1591 |

En remontant au round 45, $w_0$ valait 0,5401 : le poids sur la température précédente a perdu un quart de sa valeur en cinq heures, sans plateau. C’est un candidat sérieux pour expliquer la dérive de l’erreur globale du nœud 1 (0,37 → 0,79) relevée comme inexpliquée dans la session d’inversion : ce n’est pas l’erreur qui dérive, c’est le modèle qui n’a pas fini de bouger.

### La cadence du serveur dérive

La période réelle de la série automatique est de **300,07 s**, non 300. Les deux nœuds voient donc leur latence décroître d’environ 1,7 s sur 31 rounds — et du **même montant**. Comme leurs quartz sont indépendants, une dérive identique ne peut venir que de l’ordonnanceur du serveur, qui dort un intervalle puis travaille. C’est sans conséquence pratique, mais cela confirme une dernière fois que la latence mesure un décalage de phase entre deux horloges et rien d’autre.

### Artefacts à ne pas confondre avec la radio

| Observation | Interprétation |
|---|---|
| Chute simultanée des deux nœuds à 16:45 (53 % et 58 %) | Redémarrage de l’API pendant le build de la v4. Une coupure simultanée n’est jamais la radio. |
| Trou de 51 min entre les rounds 74 et 75 | Même cause. La série a repris à une phase différente, d’où le changement de durée des rounds. |
| Seaux de 19:15 et 19:30 quasi vides | Extinction du banc, pas dégradation de fin de session. |
| `node_stats.packets_missing` ~ 392 000 et 262 000 | Wrap de `seq` après reflashes, déjà documenté en v1 et v3. Inexploitable. |
| 188 rounds à `n_nodes = 0` après 19:35 | La série automatique n’avait pas été arrêtée. Supprimés en base, avec leurs commandes orphelines. **Les lectures capteur n’ont pas été polluées** : agent fermé, donc aucune ingestion. |

Six rounds vides **antérieurs** (ids 3, 27, 28, 29, 103, 104) ont été conservés : ce sont de vrais timeouts, matériel branché.

## Ce que la v4 a montré

La v4 devait historiser un lien. Elle a surtout montré que **la participation à un round ne se joue pas au niveau de la radio mais du protocole**.

Le taux de réception est le bon indicateur, et il est le seul des trois à voir ce qui manque. Le RSSI et le SNR décrivent les survivants ; l’absence de tout paquet corrompu sur 3 h 40 montre qu’il n’existe pas d’état intermédiaire dont ils pourraient témoigner.

La latence de réponse n’a presque aucune variance parce qu’elle ne mesure pas la radio : elle mesure l’écart de phase entre l’ordonnancement du serveur et la cadence d’émission des nœuds. La prédiction des durées de rounds avant et après le changement de phase l’établit.

Il en découle que la fenêtre de timeout ne contient qu’une seule occasion d’émettre, et donc qu’une perte de paquet unique suffit à exclure un client d’un round. Le lien entre dégradation radio et dégradation du modèle, établi en v3, passe donc par un intermédiaire qui n’avait pas été identifié : ce n’est pas la qualité du canal qui exclut le nœud, c’est le canal qui perd un paquet et le protocole qui n’en tolère aucun.

Enfin, l’agrégat n’a pas convergé sur cinq heures, ce qui invite à la prudence sur toute lecture d’un $w_{\text{global}}$ comme d’un état stable.

## Limites

Trente-trois rounds avec participants et quatorze seaux complets : l’échantillon est modeste, et les statistiques de latence portent sur deux nœuds seulement. Les créneaux mesurés sont ceux de **ce** démarrage des cartes ; ils changeraient à la prochaine mise sous tension, même si le mécanisme resterait identique. Et la cause de l’échec de la voie immédiate reste une hypothèse.

## Suite : v5, tolérance du timeout

La v4 produit une prédiction chiffrée, donc testable : si la fenêtre ne contient qu’une occasion d’émettre, la porter à deux doit faire chuter le taux d’exclusion **sans que la radio change**. Avec un timeout de 150 s, le nœud disposerait de sa réponse normale à 45 s et d’une seconde chance à 105 s ; seules deux pertes consécutives excluraient encore.

C’est ce que la [v5](../v5/V5_Rapport.md) a mesuré, par alternance 90 / 120 / 150 s dans une même session : sur la phase radio stable, les rounds complets passent de 84 % (si tout était resté à 90 s) à 98 % dès 120 s. 150 s n’ajoute rien de plus ici, tous les seconds créneaux étant tombés sous 120 s. Le firmware n’a pas été touché.
