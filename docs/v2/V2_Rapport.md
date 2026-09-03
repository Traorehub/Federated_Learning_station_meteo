# v2 : entraînement local et poids sur LoRa

La v1 a montré que capteurs et RSSI arrivent jusqu’au site. La v2 ajoute un modèle **sur l’ESP32** et fait circuler **quatre coefficients** en LoRa. Les séries DHT restent sur la carte. Le serveur stocke les poids (`fl_updates`) et ne les moyenne pas : FedAvg est la v3.

## Cycle capture / entraînement

Ce n’est ni « capter et entraîner en même temps », ni « tout stocker puis un seul fit ».

1. Le nœud capte en continu, toutes les 15 s, tampon circulaire de 32 échantillons (`FL_BUF`). Indépendant de tout round serveur.
2. À chaque nouvelle mesure : une passe SGD locale sur le tampon (`fl_train`).
3. Toutes les `WEIGHT_EVERY` (4) mesures, si au moins 3 échantillons : envoi du paquet poids (25 octets).
4. L’agrégation fédérée n’a lieu que lorsqu’un round est **clos côté serveur**. Ce n’est pas encore le cas.

POC prévu : FedAvg **synchrone** (signal `start_round`). L’asynchrone (chaque nœud selon sa radio) est plus réaliste en LoRa ; il vient après la v3 sync. Les nœuds écoutent déjà 400 ms après chaque TX capteur. La gateway accepte une ligne USB `{"cmd":"start_round","round":1}` et émet un paquet type `0x10`. Personne ne clôt encore un round ni ne calcule \(w_{\text{global}}\).

## Modèle embarqué

Fichier : `firmware/common/fl_model.h` (copié dans chaque sketch Arduino).

On prédit la température au pas \(t\) à partir de \(T_{t-1}\), \(T_{t-2}\), \(H_{t-1}\). Normalisation \(T/50\), \(H/100\) pour garder des coefficients stables en float ESP32.

$$
\frac{\hat{T}_t}{50}
=
w_0\,\frac{T_{t-1}}{50}
+ w_1\,\frac{T_{t-2}}{50}
+ w_2\,\frac{H_{t-1}}{100}
+ w_3 .
$$

| Constante | Valeur |
|-----------|--------|
| `FL_N_W` | 4 |
| `FL_BUF` | 32 |
| `FL_EPOCHS` | 8 |
| `FL_LR` | 0,05 |
| `FL_FIXED` | 1 000 000 (envoi LoRa en virgule fixe int32) |

Initialisation : \(w = (0{,}6,\ 0{,}3,\ 0,\ 0)\). SGD : pour chaque époque, pour chaque triplet du tampon, erreur \( \hat{y} - y \), mise à jour des quatre poids. `n_trained` = nombre d’échantillons dans le tampon au moment de l’envoi.

Ce n’est pas un réseau profond. Quatre scalaires tiennent dans un paquet LoRa SF7.

## Paquet poids (25 octets)

Little-endian. Version `0x02`, type `0x20`. Le paquet capteur 14 octets **ne change pas**.

| Offset | Taille | Champ |
|--------|--------|--------|
| 0 | 1 | MAGIC `0xA5` |
| 1 | 1 | `PKT_VERSION_FL` `0x02` |
| 2 | 1 | `PKT_TYPE_WEIGHTS` `0x20` |
| 3 | 1 | `node_id` |
| 4 | 2 | `seq` uint16 |
| 6 | 2 | `n_samples` (`n_trained`) |
| 8 | 4 | \(w_0\) int32 = round(\(w_0 \times 10^6\)) |
| 12 | 4 | \(w_1\) |
| 16 | 4 | \(w_2\) |
| 20 | 4 | \(w_3\) |
| 24 | 1 | XOR des octets 0-23 |

La gateway parse ce paquet comme le capteur, ajoute RSSI/SNR, JSON USB `{"type":"weights",...}`. L’agent poste `POST /api/fl/update`. Table `fl_updates` : `w0`…`w3`, `rssi`, `snr`, `seq`, `n_samples`, `round_id`.

Décalage d’émission : `delay(200 * NODE_ID)` avant les poids, pour limiter les collisions ALOHA.

### Compteur `seq` partagé

Firmware :

```text
sendSensor(seq courant)
seq++
si WEIGHT_EVERY : sendWeights()   // utilise seq déjà incrémenté, sans +1
```

Conséquence : un `weights seq=N` et le `sensor seq=N` suivant peuvent partager le même numéro. Les stats de perte (`node_stats`) ne portent que sur l’ingest **capteur**. Ne pas fusionner les deux flux pour compter les trous.

## Placement expérimental

Gateway + PC **fixes**.

| | Nœud 1 | Nœud 2 |
|--|--------|--------|
| Carte | WROOM-32D | ESP32-S3 |
| TX | 5 dBm (brownout à 14 dBm) | 14 dBm |
| Position | ~2 m, même pièce que l’Uno | autre pièce, ~30-40 m indoor |
| Rôle | **Témoin** (lien sain) | **Dégradé** (bord de couverture) |

Ne pas reculer le nœud 1 pour « égaliser » les RSSI : on perd le contrôle. La portée marketing « 1 km » suppose LOS, SF élevé, ~14 dBm. Ici : intérieur, SF7, murs. Distance utile : pièces, pas des kilomètres.

Les deux climats diffèrent (pièces distinctes). Chaque nœud apprend **ses** DHT : données non i.i.d. C’est le régime pour lequel FedAvg est conçu.

## Artefacts de mesure (à ne pas confondre avec la radio)

### Taux de perte dashboard ~99 %

`loss_rate = missing / (received + missing)` sur **toute** la vie de `node_stats`. Après un flash, `seq` repart près de 0. Si `last_seq` en base vaut encore ~995 et que `995 - 34 = 961 < 1000`, le code ne traite pas un reboot. Alors `(curr - prev - 1) % 65536` ajoute ~64 500 « manquants » d’un coup. Plusieurs reflashes : 2 ou 3 × 65536. Le pourcentage reste coincé vers 98-99 %.

Les **reçus** (ex. 1052, 1130) sont réels (campagnes précédentes + session en cours). Corrompus = 0 : ce qui arrive est lisible.

Correctif labo : exporter `readings` / `fl_updates`, puis remettre `packets_missing` (et éventuellement `packets_received` pour la session) à zéro **sans** `DELETE` des mesures. `last_seq` doit suivre le `seq` live pour ne pas retrigger le wrap.

### Trou simultané des deux nœuds

Un fade LoRa ne coupe pas les deux cartes à la même seconde. Un trou commun (ex. ~11 min, ~43-44 `seq` manquants des deux côtés) vient de l’agent, du PC (COM, sommeil) ou du VPS. Pour la thèse : citer la perte **hors** ce trou.

## Campagnes (exports `results/`)

Radio commune : 433 MHz, SF7, BW 125 kHz, CR 4/5. Tables Postgres non vidées.

### Campagne A (fenêtre 24-27 août)

Le 24, les deux nœuds sont encore proches (RSSI ~ −50 dBm). Le 27 est le contraste pièce distante. Les moyennes « toute la fenêtre » mélangent les deux jours. Pour le lien dégradé, citer le 27.

Capteurs, journée du 27 (heure de Paris) :

| Nœud | Lectures | RSSI moy. | SNR moy. | T | H |
|------|----------|-----------|----------|---|---|
| 1 | 782 | −64,8 dBm | +9,77 dB | 24,4 °C | 62,2 % |
| 2 | 774 | −98,2 dBm | +1,50 dB | 27,9 °C | 54,9 % |

Toute la fenêtre 24-27 (`resume_readings.csv`) :

| Nœud | Lectures | RSSI moy. (méd.) | SNR | T | H |
|------|----------|------------------|-----|---|---|
| 1 | 995 | −62,3 dBm (−64) | +9,77 dB | 24,9 °C | 63,1 % |
| 2 | 1082 | −83,9 dBm (−98) | +3,78 dB | 28,6 °C | 54,8 % |

Un `bad_header` (`node_id` 0).

Poids (27 seulement) :

| Nœud | Mises à jour | RSSI | SNR | \(w\) moyen approx. |
|------|----------------|------|-----|---------------------|
| 1 | 197 | −63,7 dBm | +9,87 dB | (0,612 ; 0,312 ; 0,016 ; 0,027) |
| 2 | 195 | −97,6 dBm | +1,48 dB | (0,599 ; 0,048 ; 0,080 ; 0,153) |

CSV : `results/campagne-2026-08-27-complete/`.

### Campagne B (session ~2 h 37)

Reflash firmware v2, agent relancé. Durée brute ~2 h 37.

| Nœud | Capteurs | Poids | RSSI moy. | SNR moy. | T | H |
|------|----------|-------|-----------|----------|---|---|
| 1 | 579 | 147 | −68,7 dBm | +9,52 dB | 24,8 °C | 76,0 % |
| 2 | 515 | 131 | −100,7 dBm | −5,11 dB | 29,4 °C | 63,5 % |

SNR nœud 2 négatif sur 489 / 515 paquets (95 %), toujours `ok` sur ces lignes. Cinq `bad_header`. Contraste plus dur que le 27 (SNR loin : +1,5 dB puis −5 dB).

Perte sur le span de `seq` capteur (y compris un trou agent commun ~11 min, ~43-44 seq des deux nœuds) :

| | Nœud 1 | Nœud 2 |
|--|--------|--------|
| Brut | 52 / 631 = 8,2 % | 116 / 631 = 18,4 % |
| Hors trou commun | ~1 % | ~12 % (surtout des pertes d’1 paquet) |

Les poids suivent ~1/4 des capteurs (147 vs 579/4 ; 131 vs 515/4). Le nœud faible ne « perd que les poids ». \(w_1\) ~ 0,31 (nœud 1) vs ~ 0,02 (nœud 2).

CSV : `results/campagne-2026-08-31/`.

## Fichiers

```text
firmware/common/fl_model.h
firmware/common/fl_pkt.h
firmware/node_esp32/          (copies locales pour Arduino)
firmware/node_esp32_s3/
firmware/gateway_uno/         parse capteur + poids, start_round TX
agent/serial_bridge.py        route type weights -> /api/fl/update
backend/app/fl_ingest.py
database/schema.sql           table fl_updates
```

Le dashboard v1 n’affiche pas les rounds ni les \(w\). Les poids sont en base et dans le JSON agent.

## Ce que la v2 a montré

Un client sain et un client en bord de couverture coexistent. Un SNR négatif reste souvent décodable. Quatre poids passent en 25 octets sur le même canal que les DHT. Les \(w\) divergent avec le microclimat. FedAvg n’a pas encore eu lieu : personne n’a moyenné, personne n’a renvoyé un modèle global.
