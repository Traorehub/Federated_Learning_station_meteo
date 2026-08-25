# Liaison LoRa : format, radio, câblage

RA-02 = SX1278, bande **433 MHz**. C’est le canal mesuré par le banc : RSSI, SNR, pertes et paquets illisibles.

## Configuration radio de départ (POC)

À faire varier plus tard (Q3). Ne pas changer un paramètre sans noter la nouvelle valeur.

| Paramètre | Valeur POC | Pourquoi |
|---|---|---|
| Fréquence | **433.0 MHz** | Bande native RA-02 |
| Spreading factor | **SF7** | Débit maximal, portée de laboratoire suffisante |
| Bande passante | **125 kHz** | Valeur courante, proche de LoRaWAN |
| Coding rate | **4/5** | Compromis redondance / débit |
| TX power | **14 dBm** | Limite raisonnable, moins de brownout ESP32 |
| Sync word | **0x12** | Réseau privé (0x34 est le mot LoRaWAN public) |
| Preamble | **8** | Défaut de la bibliothèque LoRa |
| Intervalle d’envoi nœud | **15 s** | Dans la plage 10-30 s |

Bibliothèque : **LoRa (Sandeep Mistry)** côté ESP32 et Uno.
`setCodingRate4(5)` correspond au coding rate 4/5.

## Format binaire du paquet LoRa (14 octets)

Little-endian. Un paquet = une lecture DHT11.

| Offset | Taille | Champ | Type |
|---|---|---|---|
| 0 | 1 | `MAGIC` | `0xA5` |
| 1 | 1 | `VERSION` | `0x01` |
| 2 | 1 | `node_id` | uint8 (1 ou 2 pour le POC) |
| 3 | 2 | `seq` | uint16, +1 à chaque envoi, retour à 0 après 65535 |
| 5 | 2 | `temp_x10` | int16, température × 10 (24,5 °C → 245) |
| 7 | 2 | `hum_x10` | uint16, humidité × 10 (61,0 % → 610) |
| 9 | 4 | `uptime_s` | uint32, secondes depuis le démarrage du nœud |
| 13 | 1 | `checksum` | XOR des octets 0-12 |

Le nœud n’a **pas d’horloge murale** (pas de Wi-Fi / NTP).
Le timestamp d’affichage est celui de **réception** (PC ou serveur, UTC).
`uptime_s` permet de détecter un redémarrage.

Le **compteur `seq`** est obligatoire dès la v1 : c’est lui qui mesurera
le taux de perte de paquets (métrique de thèse).

Un `bad_header` (magic ou version invalides, souvent associé à un RSSI trop
faible pour un décodage fiable) est un paquet radio **reçu mais illisible**.
Il est enregistré avec `node_id` 0 : cela compte comme **corrompu**,
pas comme un trou de séquence d’un nœud.

## Ce que la gateway ajoute

La gateway ne relaie pas le binaire brut tel quel vers le PC.
Elle décode, mesure le canal, et envoie **une ligne JSON** sur USB :

```json
{"node_id":1,"seq":42,"temp":24.5,"hum":61.0,"rssi":-87,"snr":8.25,"uptime_s":120,"ok":true}
```

| Champ | Origine |
|---|---|
| `node_id`, `seq`, `temp`, `hum`, `uptime_s` | Paquet nœud |
| `rssi`, `snr` | Mesure SX1278 **à la réception gateway** |
| `ok` | Checksum LoRa valide |
| `received_at` | Ajouté par l’agent PC (horloge du poste) |

## Câblage

Deux cartes nœud distinctes. Détail des couleurs : [docs/HARDWARE.md](HARDWARE.md).

### Nœud ESP32 WROOM-32D

| RA-02 | GPIO |
|---|---|
| NSS / CS | 5 |
| RST | 14 |
| DIO0 | 26 |
| MOSI | 23 |
| MISO | 19 |
| SCK | 18 |
| 3.3V / GND | 3.3V / GND |

| DHT11 (module externe) | WROOM-32D |
|---|---|
| DATA | GPIO 4 |
| VCC / GND | 3.3V / GND |

Firmware : `firmware/node_esp32`.

### Nœud ESP32-S3

| RA-02 | GPIO |
|---|---|
| NSS / CS | 5 |
| RST | 14 |
| DIO0 | 15 |
| MOSI | 6 |
| MISO | 16 |
| SCK | 18 |
| 3.3V / GND | 3.3V / GND |

`SPI.begin(18, 16, 6, 5)` est obligatoire avant `LoRa.begin` : le SPI par défaut de la S3 ne correspond pas à ce câblage.

| DHT11 (déjà soudé sur l’extension) | ESP32-S3 |
|---|---|
| DATA | GPIO 2 (souvent un cavalier à côté du capteur) |
| VCC / GND | 3.3V / GND |

Confirmer la broche DATA avec `firmware/test_dht_s3`. Firmware nœud : `firmware/node_esp32_s3`.

### Gateway Arduino Uno + RA-02

| RA-02 | Uno |
|---|---|
| NSS / CS | D10 |
| RST | D9 |
| DIO0 | D2 |
| MOSI | D11 |
| MISO | D12 |
| SCK | D13 |
| GND | GND |

**Tension : le RA-02 est en logique 3.3 V, l’Uno en 5 V.**
Un convertisseur de niveaux est **obligatoire** sur MOSI, SCK, NSS et RST.
MISO et DIO0 restent en direct (3.3 V vers l’Uno, en général toléré).
Ne **jamais** alimenter le RA-02 en 5 V.

Alimentation RA-02 : 3.3 V régulé, découplage 100 nF au plus près du module.
Antenne 433 MHz sur **chaque** RA-02.

## Bibliothèques Arduino IDE

- **LoRa** par Sandeep Mistry
- **DHT sensor library** par Adafruit
- **Adafruit Unified Sensor**

Carte nœud 1 : ESP32 Dev Module (WROOM-32D).
Carte nœud 2 : ESP32-S3.
Carte gateway : Arduino Uno.
