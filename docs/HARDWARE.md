# Branchements matériels (POC 2 nœuds)

Deux nœuds **différents** (WROOM-32D et ESP32-S3), une gateway Uno reliée au PC.

```
Nœud WROOM-32D (distant)              Gateway (au PC)
ESP32 + DHT11 + RA-02 --LoRa 433--> Arduino Uno + RA-02 --USB--> PC
Nœud ESP32-S3 (distant)               (convertisseur 5 V / 3.3 V)
ESP32 + DHT11 + RA-02 --LoRa 433--/
```

Brancher par **nom de signal**. Les couleurs sont identiques pour un même signal RA-02, sauf le MISO de la gateway (violet).

Alimentation : **GND commun** sur chaque montage. Antenne 433 MHz vissée sur **chaque** RA-02 avant de transmettre.

## Code couleur RA-02

| Fil | Broche RA-02 | Où |
|---|---|---|
| Rouge | 3V3 / VCC | partout, jamais le 5 V de l’Uno |
| Noir | GND | partout |
| Blanc | NSS / CS | partout |
| Orange | SCK | partout |
| Jaune | MOSI | partout |
| Vert | MISO | nœuds ESP32 seulement |
| Violet | MISO | gateway Uno uniquement (à la place du vert) |
| Marron | RST | partout |
| Bleu | DIO0 | partout |

## Broches MCU

| Fil | RA-02 | WROOM-32D | ESP32-S3 | Uno |
|---|---|---|---|---|
| Rouge | 3V3 | 3.3V | 3.3V | 3.3V (ou AMS1117) |
| Noir | GND | GND | GND | GND |
| Blanc | NSS | GPIO 5 | GPIO 5 | D10 via convertisseur |
| Orange | SCK | GPIO 18 | GPIO 18 | D13 via convertisseur |
| Jaune | MOSI | GPIO 23 | GPIO 6 | D11 via convertisseur |
| Vert / violet | MISO | GPIO 19 (vert) | GPIO 16 (vert) | D12 direct (violet) |
| Marron | RST | GPIO 14 | GPIO 14 | D9 via convertisseur |
| Bleu | DIO0 | GPIO 26 | GPIO 15 | D2 direct |

Firmware WROOM : `firmware/node_esp32` (`NODE_ID` 1 par défaut).
Firmware S3 : `firmware/node_esp32_s3` (`NODE_ID` 2 par défaut). Inverser les identifiants si besoin.

Sur l’ESP32-S3, MOSI, MISO et DIO0 ne sont pas les broches du WROOM. Le sketch appelle `SPI.begin(18, 16, 6, 5)` avant `LoRa.begin`.

## 1. Nœuds : 3.3 V, pas de convertisseur

Alimenter l’ESP32 en USB. Le 3.3 V interne alimente le RA-02 et le DHT11.

**WROOM-32D** : DHT11 externe. DATA sur GPIO 4, VCC 3.3 V, GND. Module 3 broches : VCC, DATA, GND. Puce nue 4 broches : 1 = VCC, 2 = DATA, 3 = NC, 4 = GND. Sans résistance intégrée : pull-up 4,7 kΩ entre DATA et 3.3 V.

**ESP32-S3** : le DHT11 est déjà soudé sur la carte d’extension (ce n’est pas un second module). DATA souvent GPIO 2, avec un cavalier à côté du capteur. Confirmer avec `firmware/test_dht_s3` avant de compter sur cette broche.

## 2. Gateway Arduino Uno + RA-02

L’Uno travaille en **5 V**. Le RA-02 est en logique **3.3 V** : une alimentation en 5 V l’endommage de façon irréversible.

Un convertisseur de niveaux est obligatoire sur blanc / marron / jaune / orange (NSS, RST, MOSI, SCK). MISO et DIO0 restent en direct (3.3 V vers l’Uno, en général toléré).

```
        Uno 5V (fil hors code) ------> HV du convertisseur
        3.3V -- rouge ---------------> LV + VCC RA-02
        GND  -- noir ----------------> GND convertisseur, GND RA-02, GND Uno
        D10 -- blanc --> convertisseur -> NSS
        D9  -- marron -> convertisseur -> RST
        D11 -- jaune --> convertisseur -> MOSI
        D13 -- orange -> convertisseur -> SCK
        D12 <--- violet -------------  MISO (direct)
        D2  <--- bleu ---------------  DIO0 (direct)
```

USB Uno → PC : port COM lu par `serial_bridge.py`.

## 3. À ne pas faire

- 5 V sur le VCC du RA-02
- MOSI / SCK / NSS / RST de l’Uno (5 V) branchés directement sur le RA-02
- Oublier l’antenne
- Deux nœuds avec le même `NODE_ID`
- Flasher le sketch WROOM sur le S3 (MOSI, MISO et DIO0 différents)

Découplage : 100 nF entre 3.3 V et GND du RA-02, au plus près du module.
