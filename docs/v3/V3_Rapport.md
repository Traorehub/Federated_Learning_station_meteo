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
| GET | `/health` | non | `fl_agg: true` |

Dernière mise à jour par nœud : `DISTINCT ON (node_id) … ORDER BY received_at DESC`. Après clôture, les participants affichés sont ceux reçus **avant** `closed_at`.

Tables : `fl_rounds`, `fl_commands` (en plus de `fl_updates`). Le volume Docker `fl_postgres_data` n’est pas recréé : `CREATE TABLE IF NOT EXISTS` au démarrage de l’API suffit. Ne pas faire `down -v`.

## Frontend

Hash `#rounds` : bouton start, cartes d’attente nœud 1 / nœud 2, historique (`w` global, qui a participé). Hash `#radio` (défaut) : cartes T/H/RSSI/SNR inchangées. Pas de token ingest dans le navigateur.

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
database/schema.sql               fl_rounds, fl_commands
frontend/src/components/RoundsView.tsx
frontend/src/components/ViewNav.tsx     bascule Liaison / Rounds
```

Flasher **les deux nœuds et la gateway**. Relancer l’agent. Reconstruire l’API + le frontend sur le VPS (`docker compose up -d --build` dans `docker/`).

## Session expérimentale

Relevé du 4 septembre 2026, conservé pour la traçabilité des exports. Même placement que la v2. Gateway + PC fixes. Nœud 1 (WROOM-32D, 5 dBm) ~2 m = témoin. Nœud 2 (ESP32-S3, 14 dBm) autre pièce ~30-40 m = dégradé. Radio : 433 MHz, SF7, BW 125 kHz, CR 4/5.

Export Postgres : `results/campagne-2026-09-04-v3/` (`fl_rounds.csv`, `fl_updates.csv`, `node_stats.csv`). 749 lignes `fl_updates`, dont 677 périodiques (`round_id = 0`, hors agrégation) et le reste tagué d’un round.

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

Le global **s’intercale** entre les deux locaux (écart \(w_1\) ~ 0,007 à 0,011). Ce n’est pas le vecteur du témoin seul. Les deux climats (pièces distinctes) restent visibles dans les \(w^{(k)}\) ; FedAvg les mélange, pondéré par \(n_k\) (ici souvent 32 + 32).

### Timeout : le nœud 2 n’entre pas dans la somme (rounds 10, 11, 14)

| Round | \(n_{\mathrm{nodes}}\) | \(w_1\) global | RSSI nœud 2 pendant le round |
|-------|------------------------|----------------|------------------------------|
| 10 | 1 | 0,0532 (= nœud 1) | paquets nœud 2 **après** `closed_at` (−108 dBm) |
| 11 | 1 | 0,0532 (= nœud 1) | aucun update nœud 2 |
| 14 | 1 | 0,0541 (= nœud 1) | aucun update nœud 2 |

Le modèle global **reste défini** : c’est le seul vecteur reçu à temps (le témoin). Le client loin n’est pas interpolé. Des updates du nœud 2 peuvent encore arriver **après** la clôture (round 10) : ils sont stockés dans `fl_updates` avec ce `round_id`, mais **hors** moyenne. C’est le cas expérimental prévu : perte / retard LoRa ⇒ nœud absent de FedAvg.

Le round 5 illustre le même mécanisme en mise au point : un seul vecteur avant timeout, puis des paquets nœud 2 en retard (S3 encore proche, RSSI ~ −56 dBm).

### Ce qui n’est pas mesuré ici

- **Perte / précision du régresseur** (MSE sur \(T\)) : le dashboard rounds affiche \(w\) et les participants, pas encore une courbe d’erreur.
- **Taux de perte radio** : `node_stats.packets_missing` ~ 130 000 est un **wrap de `seq`** après reflashes, pas le canal. Les pertes LoRa (hors trou PC) restent celles des campagnes v2 : ~1 % près, ~12 % loin (`results/campagne-2026-08-31/`).
- **Latence et RSSI dans le temps** : prévu en v4. Ici, RSSI/SNR sont ceux du paquet poids du round.

Pendant le burst downlink (`start_round` / modèle global), la gateway est en émission : quelques paquets capteur peuvent manquer (half-duplex), ce n’est pas un fade des deux nœuds.

## Hors v3

Historique RSSI fin, latence, 15-20 nœuds : **v4**. MQTT : hors périmètre tant que le PC relais USB existe. FedAvg asynchrone : après le sync.

## Ce que la v3 a montré

Deux régimes sur le **même** banc, dans la même session.

1. Lien dégradé mais encore décodable (−105 à −109 dBm, SNR négatif) : les deux \(w^{(k)}\) arrivent, et \(w_{\mathrm{global}}\) est une moyenne réelle entre deux climats, chaque composante tombant entre les deux vecteurs locaux. Le client faible **pèse** sur le modèle.
2. Nœud 2 hors fenêtre 90 s : FedAvg se réduit au témoin ; le global ne s’effondre pas, il **ignore** le client absent, sans interpolation. Le round 10 distingue « injoignable » de « trop lent » : les updates existent en base, après `closed_at`.

Un round à deux participants se clôt avant le timeout (~42 à 77 s), donc la barrière synchrone n’est pas le facteur limitant tant que les deux clients répondent. Le coût du mode synchrone est ailleurs : pendant le downlink la gateway émet, et quelques paquets capteur tombent par half-duplex.

La participation, elle, est bien corrélée au lien : c’est ce que la v2 ne pouvait pas montrer, faute d’agrégation. La suite (courbe d’erreur, historique RSSI, variation du SF, asynchrone) est en [v4](../ARCHITECTURE.md).

## Référence

McMahan et al. (2017), PMLR 54, 1273-1282. [http://proceedings.mlr.press/v54/mcmahan17a.html](http://proceedings.mlr.press/v54/mcmahan17a.html)
