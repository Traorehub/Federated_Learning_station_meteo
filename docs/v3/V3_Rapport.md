# v3 : FedAvg sur LoRa

La v2 fait monter les vecteurs \(w^{(k)}\) jusqu’à Postgres. La v3 les **agrège** (FedAvg) et **renvoie** un modèle global aux nœuds, sur le même LoRa. Le dashboard radio v1 n’est pas fusionné avec cette vue.

Agrégation mesurée sur **19 rounds** (export `results/campagne-2026-09-04-v3/`). Placement identique à la v2 : nœud 1 témoin, nœud 2 autre pièce.

## Algorithme

Federated Averaging, McMahan, Moore, Ramage, Hampson et y Arcas (2017), *Communication-Efficient Learning of Deep Networks from Decentralized Data*, AISTATS, PMLR 54.

Les données brutes \(D_k\) (DHT) restent sur le client \(k\). Seuls les paramètres circulent. Après un round \(t\) :

$$
w_{t+1}
\leftarrow
\sum_{k=1}^{K} \frac{n_k}{n}\, w_{t+1}^{(k)}
\quad\text{avec}\quad
n = \sum_{k=1}^{K} n_k .
$$

Ici \(K = 2\), \(w \in \mathbb{R}^4\) (même modèle que la v2). \(n_k\) : `n_samples` / `n_trained` du firmware, borné par le tampon 32. Un nœud qui n’envoie pas à temps (perte LoRa, hors couverture) **n’entre pas** dans la somme. C’est le cas expérimental du client loin.

Implémentation : `backend/app/fedavg.py`, moyenne pondérée. Si `n_samples` vaut 0, on compte 1 pour ne pas écraser un vecteur reçu.

Mode retenu : **synchrone**. Le serveur enfile `start_round`. Les nœuds qui reçoivent le signal s’entraînent dans la même fenêtre puis montent \(w^{(k)}\). L’asynchrone (chaque nœud selon tampon / radio, sans barrière) reste prévu après.

## Cycle d’un round

1. Dashboard `#rounds` : `POST /api/fl/rounds` (public, labo, pas de token dans le navigateur). Timeout 90 s. Un seul round `open` à la fois.
2. L’API insère `fl_rounds` et une commande `start_round` dans `fl_commands`.
3. L’agent PC poll `GET /api/fl/commands` (token ingest) et écrit sur USB `{"cmd":"start_round","round":N}`. Retransmission toutes les **~2,5 s** (pas 400 ms : la gateway s’entendait elle-même, `bad_header`). Les nœuds **écoutent en continu** (`pollDownlink` dans `loop`), plus seulement 400 ms après un TX capteur.
4. La gateway émet un paquet LoRa type `0x10` (8 octets).
5. Le nœud qui entend le signal fixe `roundId`, entraîne, envoie les poids **27 octets** (type `0x20`) avec ce `round_id`.
6. Gateway JSON `type:weights` + `round_id` → agent → `POST /api/fl/update`. Les `round_id = 0` (poids périodiques v2) sont stockés mais **ignorés** pour l’agrégation.
7. Dès que **deux** `node_id` distincts ont un update checksum OK pour ce round, ou au timeout 90 s : FedAvg, persisté sur `fl_rounds` (`w0`…`w3`, `n_total`, `n_nodes`). Commande `global_model`.
8. Agent écrit `G <round> <i32> <i32> <i32> <i32>` (virgule fixe \(10^6\), pas de float : l’Uno n’a pas de `sscanf` float fiable). Gateway TX type `0x30` (25 octets). Même retransmission ~2,5 s, avec une durée de vie de 25 s pour ne pas déborder sur le round suivant.
9. Le nœud applique \(w_{\text{global}}\) (`fl_apply_w`). Le SGD local continue ensuite **à partir** de ce vecteur.

Pendant le burst downlink, la gateway est en émission : quelques paquets capteur peuvent manquer. C’est du half-duplex, pas un fade LoRa des deux nœuds.

## Paquets

Little-endian. Le capteur 14 octets **ne change pas**.

### Poids uplink (27 octets, v3)

Compatible : la gateway accepte encore 25 octets (v2, `round_id` forcé à 0).

| Offset | Taille | Champ |
|--------|--------|--------|
| 0 | 1 | MAGIC `0xA5` |
| 1 | 1 | `PKT_VERSION_FL` `0x02` |
| 2 | 1 | `PKT_TYPE_WEIGHTS` `0x20` |
| 3 | 1 | `node_id` |
| 4 | 2 | `seq` uint16 |
| 6 | 2 | `n_samples` |
| 8 | 4 | \(w_0\) int32 = round(\(w \times 10^6\)) |
| 12 | 4 | \(w_1\) |
| 16 | 4 | \(w_2\) |
| 20 | 4 | \(w_3\) |
| 24 | 2 | `round_id` uint16 (absent en v2) |
| 26 | 1 | XOR des octets 0-25 (en v2 : XOR 0-23 à l’offset 24) |

### Start round (8 octets, inchangé)

Type `0x10`. `round_id` aux offsets 4-5. XOR à l’octet 7.

### Modèle global downlink (25 octets)

| Offset | Taille | Champ |
|--------|--------|--------|
| 0 | 1 | MAGIC `0xA5` |
| 1 | 1 | `0x02` |
| 2 | 1 | `PKT_TYPE_GLOBAL` `0x30` |
| 3 | 1 | `0` (broadcast) |
| 4 | 2 | `round_id` |
| 6 | 2 | `0` |
| 8-23 | 16 | \(w_0\)…\(w_3\) int32 |
| 24 | 1 | XOR 0-23 |

## API

| Méthode | Chemin | Auth | Rôle |
|---------|--------|------|------|
| POST | `/api/fl/rounds` | non (labo) | Ouvre un round, file `start_round` |
| GET | `/api/fl/rounds` | non | Liste + participants |
| GET | `/api/fl/commands` | `X-Ingest-Token` | File d’attente agent |
| POST | `/api/fl/update` | token | Ingest poids ; peut clore le round |
| GET | `/api/fl/errors` | non | RMSE par round et par nœud |
| GET · POST | `/api/fl/auto` | non (labo) | Série automatique de rounds |
| GET | `/health` | non | `fl_agg: true` |

`/api/fl/errors` calcule à la demande, sans nouvelle table : le RMSE d’un round a besoin des températures **postérieures** à sa clôture, qui n’existent pas encore au moment où il se ferme. La requête couvre la fenêtre des rounds demandés, élargie de 5 min en amont — une cible juste après `closed_at` a besoin de ses \(T_{t-1}\) et \(T_{t-2}\).

### Série automatique

Constituer un échantillon de plusieurs dizaines de rounds à la main n’est pas tenable. `/api/fl/auto` fait tourner une boucle côté serveur qui ouvre un round à intervalle fixe, navigateur fermé. Elle n’ouvre jamais un round si un autre est encore ouvert, et l’intervalle court depuis l’**ouverture** du précédent, pour que la cadence reste régulière même quand un round va au timeout. L’état vit en mémoire du processus (un seul worker uvicorn) : un redéploiement remet la série à l’arrêt, ce qui évite qu’un lanceur survive en silence.

Le choix de l’intervalle n’est pas cosmétique, et un plancher de 60 s est imposé. Le tampon d’un nœud fait 32 échantillons à 15 s, soit **8 min pour se renouveler** : plus les rounds se rapprochent, plus ils réapprennent les mêmes données et produisent des \(w\) redondants. Surtout, chaque clôture déclenche un downlink pendant lequel la gateway émet et perd des paquets capteur — ceux-là mêmes qui servent ensuite à mesurer l’erreur. Enchaîner les rounds dégrade donc les données qui les évaluent. La fenêtre d’évaluation de 15 min ajoute un recouvrement entre rounds voisins. Un gros échantillon s’obtient par une **session longue**, pas par une cadence rapide.

Dernière mise à jour par nœud : `DISTINCT ON (node_id) … ORDER BY received_at DESC`. Après clôture, les participants affichés sont ceux reçus **avant** `closed_at`.

Tables : `fl_rounds`, `fl_commands` (en plus de `fl_updates`). Le volume Docker `fl_postgres_data` n’est pas recréé : `CREATE TABLE IF NOT EXISTS` au démarrage de l’API suffit. Ne pas faire `down -v`.

## Frontend

Hash `#rounds` : bouton start, barre de série automatique (marche/arrêt, intervalle, prochain round), cartes d’attente nœud 1 / nœud 2, historique (`w` global, qui a participé), puis le panneau **Erreur du modèle**. Hash `#radio` (défaut) : cartes T/H/RSSI/SNR inchangées. Pas de token ingest dans le navigateur.

Le panneau d’erreur tient en deux blocs. Un tableau donne, par nœud, le RMSE de la persistance, celui de son modèle local, et celui du modèle global selon qu’il a participé au round ou non — la dernière colonne chiffre la pénalité d’un timeout. En dessous, une courbe SVG (aucune dépendance ajoutée) suit le RMSE du modèle global round par round : marqueur plein quand le nœud a été agrégé, marqueur creux quand il était absent. Les creux hauts sont exactement le résultat central de la v3.

Un round filmé de bout en bout (agent + vue `#rounds`, accéléré 3×) : `docs/media/demo-round-fedavg.mp4`, inséré dans le README. On y suit l’émission du `start_round`, l’état « en attente » du nœud qui n’a pas encore répondu, puis la clôture **à l’arrivée du second update**, sans attendre le timeout.

## Fichiers

```text
firmware/common/fl_pkt.h          0x30, 27 octets, 25 octets v2
firmware/common/fl_model.h        fl_from_fixed, fl_apply_w
firmware/node_esp32/              copies + sendWeights 27 o + RX global
firmware/node_esp32_s3/
firmware/gateway_uno/             25/27 o, TX G, tampon USB 96
agent/serial_bridge.py            poll commandes, retransmit 2,5 s
backend/app/fedavg.py
backend/app/fl_rounds.py
backend/app/fl_error.py           RMSE par round, persistance de référence
backend/app/fl_auto.py            série automatique, plancher 60 s
database/schema.sql               fl_rounds, fl_commands
frontend/src/components/RoundsView.tsx
frontend/src/components/ErrorPanel.tsx  tableau + courbe d'erreur
frontend/src/components/ViewNav.tsx     bascule Liaison / Rounds
results/.../erreur.py             même calcul, hors ligne sur les CSV
```

Flasher **les deux nœuds et la gateway**. Relancer l’agent. Reconstruire l’API + le frontend sur le VPS (`docker compose up -d --build` dans `docker/`).

## Session expérimentale

Relevé du 4 septembre 2026, conservé pour la traçabilité des exports. Même placement que la v2. Gateway + PC fixes. Nœud 1 (WROOM-32D, 5 dBm) ~2 m = témoin. Nœud 2 (ESP32-S3, 14 dBm) autre pièce ~30-40 m = dégradé. Radio : 433 MHz, SF7, BW 125 kHz, CR 4/5.

Export Postgres : `results/campagne-2026-09-04-v3/` (`fl_rounds.csv`, `fl_updates.csv`, `node_stats.csv`, `readings.csv`). 749 lignes `fl_updates`, dont 677 périodiques (`round_id = 0`, hors agrégation) et le reste tagué d’un round.

Fenêtre des 19 rounds : 21:03 → 22:37 UTC. Timeout serveur : 90 s. Un round se clôt **dès deux nœuds distincts** ou à ce timeout.

### Dépouillement

| Clos avec | Nombre | Durée typique |
|-----------|--------|----------------|
| 2 nœuds | 12 | ~42 à 77 s (souvent ~50 s) |
| 1 nœud | 6 | 90 s (timeout) |
| 0 nœud | 1 (round 3, mise au point) | 90 s |

Les rounds **1 à 5** sont de la mise au point (écoute downlink, S3 encore proche sur le round 4 : RSSI nœud 2 ~ −55 dBm). La comparaison témoin / dégradé se lit à partir du **round 6**.

### Les deux nœuds dans la moyenne (ex. rounds 6-9, 12-13, 15-19)

Le S3 est au loin : RSSI **−105 à −109 dBm**, SNR **négatif** (−3,5 à −9 dB). Le WROOM reste sain : RSSI **−80 à −93 dBm**, SNR **~ +10 dB**.

\(w_1\) local (dernier update **avant** `closed_at`) :

| Round | \(w_1\) nœud 1 | \(w_1\) nœud 2 | \(w_1\) global | Écart n2−n1 |
|-------|----------------|----------------|----------------|-------------|
| 6 | 0,0537 | 0,0642 | 0,0584 | 0,0105 |
| 7 | 0,0540 | 0,0614 | 0,0584 | 0,0074 |
| 8 | 0,0540 | 0,0610 | 0,0575 | 0,0070 |
| 9 | 0,0536 | 0,0607 | 0,0571 | 0,0071 |
| 16 | 0,0552 | 0,0647 | 0,0599 | 0,0095 |
| 19 | 0,0575 | 0,0660 | 0,0613 | 0,0085 |

Le global **s’intercale** entre les deux locaux (écart \(w_1\) ~ 0,007 à 0,011). Ce n’est pas le vecteur du témoin seul. Les deux distributions locales restent visibles dans les \(w^{(k)}\) ; FedAvg les mélange, pondéré par \(n_k\) (ici souvent 32 + 32).

### Timeout : le nœud 2 n’entre pas dans la somme (rounds 10, 11, 14)

| Round | \(n_{\mathrm{nodes}}\) | \(w_1\) global | RSSI nœud 2 pendant le round |
|-------|------------------------|----------------|------------------------------|
| 10 | 1 | 0,0532 (= nœud 1) | paquets nœud 2 **après** `closed_at` (−108 dBm) |
| 11 | 1 | 0,0532 (= nœud 1) | aucun update nœud 2 |
| 14 | 1 | 0,0541 (= nœud 1) | aucun update nœud 2 |

Le modèle global **reste défini** : c’est le seul vecteur reçu à temps (le témoin). Le client loin n’est pas interpolé. Des updates du nœud 2 peuvent encore arriver **après** la clôture (round 10) : ils sont stockés dans `fl_updates` avec ce `round_id`, mais **hors** moyenne. C’est le cas expérimental prévu : perte / retard LoRa ⇒ nœud absent de FedAvg.

Le round 5 illustre le même mécanisme en mise au point : un seul vecteur avant timeout, puis des paquets nœud 2 en retard (S3 encore proche, RSSI ~ −56 dBm).

### Erreur de prédiction

Les vecteurs seuls ne disent pas si le modèle est **bon**. Chaque \(w\) a donc été rejoué hors ligne sur les températures réellement mesurées **après** la clôture du round (horizon 15 min), et comparé à la **persistance** (prédire \(T_t = T_{t-1}\)). Script : `results/campagne-2026-09-04-v3/erreur.py`, sur `readings.csv` exporté du serveur.

Un triplet n’est évalué que si ses trois lectures se suivent en `seq` : un paquet perdu casse le triplet et l’écarte. Sur 394 lectures valides, 319 triplets exploitables.

RMSE moyen, en degrés Celsius :

| Nœud | Persistance | Son modèle local | Global **s’il a participé** | Global **s’il était absent** |
|------|-------------|------------------|------------------------------|-------------------------------|
| 1 (témoin) | 0,028 | 0,034 | 0,750 | 2,296 |
| 2 (distant) | 0,380 | 0,353 | 0,865 | 1,467 |

Trois lectures, dans l’ordre d’importance.

**1. Le nœud exclu reçoit un modèle qui lui va mal.** C’est le résultat central. Quand le nœud 2 rate le round, le modèle qu’on lui renvoie est **1,7 fois** moins précis que lorsqu’il participe (1,467 contre 0,865 °C). Le lien est direct entre un timeout radio et la qualité du modèle redescendu. La situation est symétrique : au round 2, seul le nœud 2 avait répondu, et le global qui en découle donne 2,296 °C d’erreur **pour le nœud 1**. Un client absent n’est pas seulement « hors de la somme » : il repart avec le modèle de l’autre pièce.

Réserve de méthode : le chiffre du nœud 2 s’appuie sur quatre rounds (5, 10, 11, 14), celui du nœud 1 sur **un seul** (round 2). L’ordre de grandeur est cohérent, la valeur exacte du nœud 1 demande confirmation.

**2. Le modèle global est moins bon que chaque modèle local, sur 27 comparaisons sur 28.** Ce n’est pas un défaut d’implémentation : c’est l’effet attendu de l’hétérogénéité. Les deux clients ne relèvent ni la même température (~25,8 °C contre ~30 °C) ni la même humidité (~88 % contre ~72 %). La moyenne pondérée produit un compromis biaisé pour chacun : pour le nœud 1, le global surestime d’environ 0,85 °C de façon systématique. C'est le *client drift* documenté en FL non-i.i.d., ici mesuré sur du matériel réel plutôt que simulé.

Cet écart entre clients était attribué ici à deux microclimats. L’expérience d’échange de pièces l’a démenti : il provient de la **calibration des capteurs** (voir [Session d’inversion](V3_Session_inversion.md)). L’hétérogénéité et le *client drift* restent réels, seule leur cause change.

**3. Sur ces séries, la persistance bat le modèle appris.** Prédire « la même température qu’il y a 15 s » donne 0,028 °C d’erreur sur le nœud 1, là où son propre régresseur donne 0,034. La température varie alors moins que la résolution du DHT11 sur un pas de 15 s, et un modèle à quatre poids n’apporte rien en précision brute.

Cette lecture est propre aux conditions de la session : 319 triplets relevés de nuit, sur un signal quasi immobile. Sur 1200 triplets de milieu de journée, la [session d’inversion](V3_Session_inversion.md) mesure l’inverse — le régresseur y gagne 14 % sur le nœud bruité. La conclusion à retenir est donc conditionnelle : **le régresseur n’apporte quelque chose que si le signal bouge**, et sur ces séries-ci il ne bougeait pas assez.

### Ce qui n’est pas mesuré ici

- **Taux de perte radio** : `node_stats.packets_missing` ~ 130 000 est un **wrap de `seq`** après reflashes, pas le canal. Les pertes LoRa (hors trou PC) restent celles des campagnes v2 : ~1 % près, ~12 % loin (`results/campagne-2026-08-31/`).
- **Latence et RSSI dans le temps** : réalisé depuis en v4, vue `#reseau`. Ici, RSSI/SNR sont ceux du paquet poids du round.

Pendant le burst downlink (`start_round` / modèle global), la gateway est en émission : quelques paquets capteur peuvent manquer (half-duplex), ce n’est pas un fade des deux nœuds.

## Hors v3

Historique RSSI fin, latence, 15-20 nœuds : **v4**. MQTT : hors périmètre tant que le PC relais USB existe. FedAvg asynchrone : après le sync.

## Ce que la v3 a montré

Deux régimes sur le **même** banc, dans la même session.

1. Lien dégradé mais encore décodable (−105 à −109 dBm, SNR négatif) : les deux \(w^{(k)}\) arrivent, et \(w_{\mathrm{global}}\) est une moyenne réelle entre deux distributions, chaque composante tombant entre les deux vecteurs locaux. Le client faible **pèse** sur le modèle.
2. Nœud 2 hors fenêtre 90 s : FedAvg se réduit au témoin. Le global **reste défini** — il ignore le client absent sans l’interpoler — mais l’erreur mesurée montre qu’il n’est pas pour autant *utilisable* par ce client : il devient 1,7 fois moins précis pour lui. Le round 10 distingue « injoignable » de « trop lent » : les updates existent en base, après `closed_at`.

Un round à deux participants se clôt avant le timeout (~42 à 77 s), donc la barrière synchrone n’est pas le facteur limitant tant que les deux clients répondent. Le coût du mode synchrone est ailleurs : pendant le downlink la gateway émet, et quelques paquets capteur tombent par half-duplex.

Le point qui répond à la question de départ : **la qualité radio se propage jusqu’au modèle**. Un timeout ne dégrade pas seulement une statistique de participation, il renvoie au client concerné un modèle calibré sur les données de l’autre. C’est ce que la v2 ne pouvait pas montrer, faute d’agrégation.

En contrepartie, le banc montre aussi sa limite : le modèle global est moins bon que chaque modèle local, et sur ces séries nocturnes la persistance bat le régresseur. La démonstration porte sur le **mécanisme** fédéré sous contrainte radio, pas sur un gain de précision. La suite (historique RSSI, variation du SF, asynchrone, signal plus dynamique) est en [v4](../ARCHITECTURE.md).

## Suite : contrôle par échange des rôles

Cette session laissait ouverte une objection : le modèle du nœud éloigné pouvait être mauvais en soi, indépendamment de la radio. La [session d’inversion](V3_Session_inversion.md) y répond en échangeant les deux nœuds de pièce, avec des puissances d’émission égalisées, sur 40 rounds et 1200 triplets. Elle confirme la pénalité (×1,8 à 1,9, sur le nouveau nœud éloigné) et révise trois points de ce rapport :

| Point de ce rapport | Ce que l’échange établit |
|---|---|
| Deux microclimats distincts | Écart d’origine **capteur** : 4,2 °C de calibration contre 0,1 °C entre les pièces |
| La persistance bat le régresseur | Vrai ici seulement ; faux dès que le signal varie |
| Pénalité ×1,7 attribuable au lien | Confirmé — le phénomène suit la pièce, non le matériel |

Les conditions décrites ci-dessus (placement, 5 dBm sur le nœud 1) sont conservées telles quelles : c’est un relevé daté, pas une description de la configuration courante.

## Référence

McMahan et al. (2017), PMLR 54, 1273-1282. [http://proceedings.mlr.press/v54/mcmahan17a.html](http://proceedings.mlr.press/v54/mcmahan17a.html)
