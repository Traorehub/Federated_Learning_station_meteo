# v1 : chaîne de communication

Objectif : prouver que deux nœuds ESP32 (DHT11 + RA-02) joignent une gateway Arduino Uno par LoRa, que le PC lit le JSON USB et que l’API + le dashboard affichent des mesures réelles (température, humidité, RSSI, SNR, `seq`, `ok`). Pas d’apprentissage dans cette version.

## Pourquoi LoRa et un PC au milieu

Envoyer les DHT en Wi-Fi (ou 4G) depuis chaque ESP32 vers le cloud serait plus simple. On ne mesurerait plus le canal LoRa : plus de RSSI, plus de SNR, plus de trous de `seq` liés à la radio.

Un serveur (VPS ou Docker local) n’a pas de module RA-02. Si les nœuds publiaient directement en HTTP, la radio disparaîtrait du chemin. D’où la chaîne :

```text
DHT11 --> ESP32 + RA-02
                |
                |  LoRa 433 MHz, SF7, BW 125 kHz, CR 4/5
                v
         Arduino Uno + RA-02
                |
                |  USB 115200, une ligne JSON
                v
         agent/serial_bridge.py  (PC de labo)
                |
                |  HTTPS POST /api/ingest  (header X-Ingest-Token)
                v
         FastAPI + PostgreSQL + dashboard React
```

MQTT n’apporte rien tant que ce relais USB existe. Il pourra servir plus tard si un nœud doit joindre le cloud sans PC.

Il n’y a pas d’instance publique maintenue en continu. Chacun déploie (Docker local, VPS, nom de domaine) et arrête quand il a fini.

## Vocabulaire

| Terme | Signification |
|-------|----------------|
| LoRa | Modulation longue portée, bas débit. Ici : 433 MHz, module RA-02 (SX1278). |
| RSSI | Puissance du signal **reçu par la gateway**, en dBm. −40 dBm : fort. −100 dBm : très faible. |
| SNR | Rapport signal / bruit, en dB. Plus il est élevé, plus le paquet est facile à décoder. Un SNR négatif n’interdit pas toujours le décodage. |
| dBm / dB | dBm : puissance (réf. 1 mW). dB : rapport (SNR). |
| SF | Spreading factor. Ici SF7 : débit plus élevé, portée de laboratoire. Un SF plus grand allonge la portée et ralentit l’émission. |
| BW / CR | Bande passante 125 kHz. Coding rate 4/5 (`setCodingRate4(5)`). |
| `seq` | Compteur uint16 du nœud, +1 à chaque envoi capteur. Un saut (1, 2, puis 4) signale un paquet perdu. |
| `ok` | Checksum XOR du paquet LoRa valide. |
| checksum | XOR des octets utiles. La gateway recalcule et renseigne `ok`. |
| `bad_header` | Magic ou version invalides. Souvent RSSI trop faible. Enregistré `node_id` 0 : paquet corrompu, pas un trou de `seq`. |
| `node_id` | 1 = WROOM-32D, 2 = ESP32-S3, 0 = illisible. |
| uptime | Secondes depuis le boot du nœud. Une chute indique un redémarrage. |
| SPI | Bus RA-02 : NSS (CS), SCK, MOSI, MISO. |
| DIO0 | Interruption RA-02 (paquet reçu ou TX fini). |
| Gateway | L’Uno : décode LoRa, ajoute RSSI/SNR, JSON vers le PC. |

## Matériel et câblage

Deux nœuds **différents**, une gateway. Couleurs identiques par signal RA-02, sauf MISO gateway (violet : plus de fil vert).

Huit broches utilisées : 3V3, GND, NSS, SCK, MOSI, MISO, RST, DIO0. DIO1 à DIO5 non câblées. Antenne IPEX **avant** toute émission. Jamais 5 V sur le RA-02. GND commun sur chaque montage. Découplage conseillé : 100 nF entre 3.3 V et GND du RA-02, au plus près du module.

| Fil | Broche RA-02 | WROOM-32D | ESP32-S3 | Uno |
|-----|--------------|-----------|----------|-----|
| Rouge | 3V3 | 3.3V | 3.3V | 3.3V (jamais le 5 V Uno) |
| Noir | GND | GND | GND | GND |
| Blanc | NSS | GPIO 5 | GPIO 5 | D10 via shifter |
| Orange | SCK | GPIO 18 | GPIO 18 | D13 via shifter |
| Jaune | MOSI | GPIO 23 | GPIO 6 | D11 via shifter |
| Vert | MISO | GPIO 19 | GPIO 16 | (nœuds seulement) |
| Violet | MISO | | | D12 direct |
| Marron | RST | GPIO 14 | GPIO 14 | D9 via shifter |
| Bleu | DIO0 | GPIO 26 | GPIO 15 | D2 direct |

Shifter obligatoire sur NSS, RST, MOSI, SCK (Uno 5 V vers RA-02 3.3 V). MISO et DIO0 en direct (3.3 V vers l’Uno, en général toléré).

**WROOM-32D, nœud 1.** DHT11 externe, DATA GPIO 4, VCC 3.3 V, GND. Module 3 broches : VCC, DATA, GND. Puce 4 broches : 1 = VCC, 2 = DATA, 3 = NC, 4 = GND. Sans résistance interne : pull-up 4,7 kΩ DATA–3.3 V. Sketch : `firmware/node_esp32`.

**ESP32-S3, nœud 2.** DHT déjà soudé sur la carte d’extension (pas un second module). Scan `firmware/test_dht_s3` : seule GPIO 2 répond (après une première lecture aberrante ~0,8 °C, puis des valeurs cohérentes). Cavalier DATA souvent requis à côté du capteur. `SPI.begin(18, 16, 6, 5)` **avant** `LoRa.begin` : le SPI par défaut ne correspond pas à ce câblage. Sketch : `firmware/node_esp32_s3`. Ne pas flasher le binaire WROOM sur le S3.

**Brownout WROOM.** À 14 dBm : `Brownout detector was triggered`, reboot. Puissance d’émission du nœud 1 : **5 dBm**. Le S3 et l’Uno restent à 14 dBm. Conséquence : le WROOM reste le nœud **proche** ; le S3 part au loin (voir v2).

Ne pas faire : 5 V sur VCC RA-02 ; MOSI/SCK/NSS/RST Uno sans shifter ; oubli d’antenne ; deux nœuds avec le même `NODE_ID`.

Table complète : [HARDWARE.md](../HARDWARE.md).

## Radio et paquet capteur (14 octets)

Little-endian. Bibliothèque LoRa (Sandeep Mistry). Intervalle : 15 s.

| Paramètre | Valeur |
|-----------|--------|
| Fréquence | 433,0 MHz |
| SF | 7 |
| BW | 125 kHz |
| CR | 4/5 |
| Sync | 0x12 (privé ; 0x34 = LoRaWAN public) |
| Preamble | 8 |
| TX | WROOM 5 dBm, S3/Uno 14 dBm |

| Offset | Taille | Champ |
|--------|--------|--------|
| 0 | 1 | MAGIC `0xA5` |
| 1 | 1 | VERSION `0x01` |
| 2 | 1 | `node_id` |
| 3 | 2 | `seq` uint16 |
| 5 | 2 | `temp_x10` int16 (24,5 °C → 245) |
| 7 | 2 | `hum_x10` uint16 (61,0 % → 610) |
| 9 | 4 | `uptime_s` uint32 (`millis()/1000`) |
| 13 | 1 | checksum XOR des octets 0-12 |

Le nœud n’a pas d’horloge murale. Le timestamp du dashboard est l’heure d’ingestion (PC). `uptime_s` détecte un reboot.

## D’où viennent RSSI, SNR, `ok`, la perte

Les ESP32 ne mesurent pas le RSSI de leur propre TX. C’est le SX1278 de l’Uno, juste après `parsePacket()` : `LoRa.packetRssi()` et `LoRa.packetSnr()`.

La gateway ne relaie pas le binaire brut. Elle décode et envoie une ligne JSON USB, par exemple :

```json
{"node_id":1,"seq":42,"temp":24.5,"hum":61.0,"rssi":-87,"snr":8.25,"uptime_s":120,"ok":true}
```

| Champ | Origine |
|-------|---------|
| `node_id`, `seq`, `temp`, `hum`, `uptime_s` | Paquet nœud |
| `rssi`, `snr` | SX1278 gateway à la réception |
| `ok` | XOR reçu = XOR recalculé |
| `received_at` | Agent PC (UTC) |

`bad_header` (magic/version faux) : `node_id` 0, compteur **corrompus**, pas un trou de `seq` du nœud 1 ou 2.

Côté serveur (`backend/app/seq.py`, `ingest.py`) :

- `packets_received` : +1 à chaque ingest capteur
- `packets_missing` : `missing_between(last_seq, seq)` ; wrap uint16 (65536)
- si `curr < prev` et `prev - curr > 1000` : reboot, **0** manquant ajouté
- `loss_rate = missing / (received + missing)` (cumul depuis le début de `node_stats`, pas « les 5 dernières minutes »)
- `packets_corrupt` si `ok` faux
- âge / « en ligne » : frontend, `now - last_seen_at` (≤ 30 s en ligne, ≤ 90 s faible)

Si le seuil 1000 est trop élevé par rapport au `last_seq` d’une campagne précédente (~995) et qu’un flash remet `seq` à 0, le wrap compte ~64 000 manquants et le dashboard affiche ~99 %. Ce n’est pas la radio. Voir v2.

Tables : `readings`, `node_stats`. Une table unique + `node_id` (pas une table par nœud).

## Agent, token, COM

`agent/serial_bridge.py` : 115200, une ligne JSON. `POST /api/ingest` avec `X-Ingest-Token`.

Le Moniteur série Arduino **occupe** le port COM. Tant qu’il est ouvert, l’agent ne lit rien : le site reste vide alors que l’Uno affiche déjà des paquets. Fermer le moniteur, puis lancer l’agent (COM5 typiquement pour l’Uno).

Token identique dans `agent/.env` et `docker/.env`. Jeton laissé à `change-me-ingest-token` en labo. Un 401 Unauthorized, c’est presque toujours ce décalage.

`python simulator.py` envoie des paquets fictifs vers l’API (sans hardware).

## Stack serveur

Docker Compose (`name: federated`) : nginx :8082, frontend, API FastAPI, Postgres 16. Volume `fl_postgres_data` (ne pas réutiliser le volume Timescale d’un autre projet dans le même dossier `docker/`). `deploy.sh` en CRLF provoque `bash\r` : convertir les fins de ligne Unix. Tunnel optionnel (ex. Cloudflare) vers `localhost:8082`. Santé : `{"ok":true,"stage":"v1",...}`.

`down` **sans** `-v` conserve Postgres. `down -v` ou destruction du VPS : données perdues. Pas de `pg_dump` automatique.

Frontend v1 : cartes nœuds, journal de paquets, WebSocket `/ws/live` + polling. Ne pas y fusionner une UI de rounds FedAvg.

## Fichiers

```text
firmware/node_esp32/
firmware/node_esp32_s3/
firmware/gateway_uno/
firmware/test_dht_s3/          scan GPIO DHT (pas le nœud LoRa)
agent/serial_bridge.py
backend/app/ingest.py
backend/app/seq.py
frontend/
database/schema.sql
docker/
```

## Ce que la v1 a montré

La chaîne tient : les deux nœuds apparaissent sur le dashboard. Au tout début, les deux cartes étaient encore proches de la gateway (RSSI de l’ordre de −40 à −55 dBm, SNR ~ +10 dB). Le JSON Uno (`node_id`, temp, hum) vient du nœud LoRa, pas d’un DHT sur l’Arduino.

La v1 ne contient pas d’entraînement. Le placement témoin / pièce distante et les paquets poids sont la v2.

Captures Serial : `docs/media/serial/`. Démo : `docs/media/demo-dashboard.gif`.
