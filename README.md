# Banc d’essai LoRa : Federated Learning IoT (version mini-station météo)

[![C++](https://img.shields.io/badge/Firmware-C%2B%2B-blue?logo=cplusplus)](firmware/gateway_uno/gateway_uno.ino)
[![ESP32](https://img.shields.io/badge/ESP32-Embarqué-blue?logo=espressif)](https://www.espressif.com/)
[![Arduino](https://img.shields.io/badge/Gateway-Arduino%20Uno-00979D?logo=arduino)](firmware/gateway_uno/gateway_uno.ino)
[![LoRa](https://img.shields.io/badge/Radio-RA--02%20433%20MHz-green)](docs/LORA.md)
[![DHT11](https://img.shields.io/badge/Capteur-DHT11-orange)](docs/HARDWARE.md)
[![Python](https://img.shields.io/badge/Agent%20%2B%20API-Python-3776AB?logo=python)](backend/app/main.py)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688)](backend/)
[![PostgreSQL](https://img.shields.io/badge/DB-PostgreSQL-4169E1?logo=postgresql)](database/schema.sql)
[![React](https://img.shields.io/badge/Dashboard-React-61DAFB?logo=react)](frontend/)
[![Docker](https://img.shields.io/badge/Deploy-Docker-2496ED?logo=docker)](docker/docker-compose.yml)
[![IoT](https://img.shields.io/badge/Projet-IoT-red)]()
[![FL](https://img.shields.io/badge/Objectif-Federated%20Learning-purple)](docs/ARCHITECTURE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Prototype pédagogique. Deux nœuds ESP32 distants (capteur DHT11 et radio LoRa RA-02) communiquent avec une gateway Arduino Uno. Un PC, placé entre la radio et le serveur, transmet les paquets vers le backend que chacun déploie. Le dashboard permet de vérifier que la liaison radio fonctionne réellement.

**État actuel du code.** La chaîne de communication (**v1**) est opérationnelle. Les nœuds entraînent **localement** un régresseur linéaire minuscule et envoient les poids par LoRa (table `fl_updates`). L’**agrégation FedAvg** au sens de McMahan et al. (2017), c’est-à-dire la moyenne des modèles et le renvoi du modèle global, n’est **pas encore** exécutée sur le serveur.

Il n’existe pas d’instance publique maintenue en continu. Chaque personne déploie le serveur chez elle (Docker en local, VPS ou nom de domaine personnel) et peut l’arrêter à tout moment.

## Objectifs du projet

Trois niveaux, dans cet ordre.

**1. Apprendre la chaîne IoT sur du matériel réel.**  
Câbler, alimenter, flasher, lire un capteur, établir un lien LoRa. Cette étape forme à l’embarqué, à l’électronique de laboratoire, et aux contraintes d’un réseau longue portée et bas débit : spreading factor, RSSI, SNR, paquets perdus ou illisibles. Le canal n’est pas simulé : il est physique.

**2. Partager un banc reproductible.**  
Le firmware, le câblage et le dashboard sont documentés pour qu’une autre personne puisse refaire le montage **avec son matériel et son serveur**. Licence MIT. L’intérêt n’est pas un site d’auteur accessible en permanence, mais la possibilité de reproduire l’expérience.

**3. Poser l’instrument pour le Federated Learning.**  
Lorsque la radio et l’ingestion sont stables, le même banc sert à l’apprentissage fédéré : entraînement local sur les nœuds, puis agrégation de type FedAvg (McMahan et al., 2017), comparaison synchrone / asynchrone, et mesure de l’effet du réseau LoRa sur le modèle (pertes, latence, nœuds absents). Sans la couche de communication, les expériences FL ne pourraient pas relier leurs résultats au canal radio.

## Prérequis

### Matériel utilisé

<table>
  <tr>
    <td align="center" width="25%">
      <img src="docs/media/hardware/01-ra02-lora.png" alt="Module LoRa RA-02 SX1278 433 MHz" width="100%" />
      <br /><sub><b>LoRa</b> RA-02 (SX1278, 433 MHz)</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/media/hardware/02-dht11.png" alt="Capteur DHT11 température humidité" width="100%" />
      <br /><sub><b>Capteur</b> DHT11</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/media/hardware/03-arduino-uno.png" alt="Arduino Uno gateway" width="100%" />
      <br /><sub><b>Gateway</b> Arduino Uno</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/media/hardware/04-jumpers.png" alt="Jumpers Dupont male-male male-female female-female" width="100%" />
      <br /><sub><b>Fils</b> Dupont M-M, M-F, F-F</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="25%">
      <img src="docs/media/hardware/05-esp32-wroom32d.png" alt="ESP32 WROOM-32D nœud 1" width="100%" />
      <br /><sub><b>Nœud 1</b> ESP32 WROOM-32D</sub>
    </td>
    <td align="center" width="25%">
      <img src="docs/media/hardware/06-esp32-s3-extension.jpg" alt="ESP32-S3-CAM et carte d extension DHT11" width="100%" />
      <br /><sub><b>Nœud 2</b> ESP32-S3-CAM + extension</sub>
    </td>
    <td align="center" colspan="2">
      <img src="docs/media/hardware/07-esp32-s3-cam-on-extension.jpg" alt="ESP32-S3-CAM clipsé sur sa carte d extension DHT soudé" width="100%" />
      <br /><sub><b>Nœud 2</b> S3-CAM clipsé, DHT11 déjà soudé</sub>
    </td>
  </tr>
</table>

| Élément | Remarque |
|---------|----------|
| ESP32 WROOM-32D | Nœud 1, DHT11 externe |
| ESP32-S3 (+ carte d’extension) | Nœud 2, DHT11 déjà soudé (GPIO 2) |
| 3 × RA-02 (SX1278, 433 MHz) | Antenne IPEX, **3.3 V uniquement** |
| Arduino Uno | Gateway USB, convertisseur 5 V / 3.3 V obligatoire |
| DHT11 | Nœud WROOM (le S3 a le sien sur l’extension) |
| Jumpers M-M, M-F, F-F | Code couleur : [docs/HARDWARE.md](docs/HARDWARE.md) |
| PC + serveur | Agent série sur le PC. API et dashboard en local ou sur un VPS personnel |

RA-02 : huit broches utilisées (3.3V, GND, NSS, SCK, MOSI, MISO, RST, DIO0). DIO1 à DIO5 restent non connectées. L’antenne IPEX doit être en place **avant** la première transmission.

### Logiciel

| Outil | Usage |
|-------|--------|
| Arduino IDE 2.x | ESP32 Dev Module, ESP32-S3, Arduino Uno |
| LoRa (Sandeep Mistry) + DHT Adafruit | Firmware nœuds / gateway |
| Python 3 | `agent/serial_bridge.py`, API FastAPI |
| Docker Compose | Postgres, API, nginx, front |

### Vocabulaire

Les termes ci-dessous reviennent dans le firmware, le JSON de la gateway et le dashboard. Ils sont expliqués ici une fois, pour la suite du texte.

| Terme | Signification |
|-------|----------------|
| **LoRa** | Modulation radio longue portée, bas débit. Ici : 433 MHz, module RA-02 (puce SX1278). |
| **RSSI** | *Received Signal Strength Indicator*. Puissance du signal **reçu** par la gateway, en **dBm**. Une valeur proche de 0 (par exemple −40 dBm) indique un signal fort ; −100 dBm indique un signal très faible. |
| **SNR** | *Signal-to-Noise Ratio*. Rapport entre le signal utile et le bruit, en **dB**. Plus il est élevé, plus le paquet est facile à décoder. |
| **dBm / dB** | Le **dBm** mesure une puissance (référence : 1 mW). Le **dB** mesure un rapport, comme le SNR. |
| **SF** | *Spreading factor* (facteur d’étalement). Ici **SF7** : débit plus élevé, portée de laboratoire suffisante. Un SF plus grand allonge la portée et ralentit l’émission. |
| **BW / CR** | **BW** : bande passante radio (ici 125 kHz). **CR** : *coding rate*, redondance du code correcteur (ici 4/5). |
| **`seq`** | Compteur de séquence : entier incrémenté à chaque envoi du nœud. Un saut (1, 2, puis 4) signale un paquet perdu. |
| **`ok`** | Champ JSON émis par la gateway. `true` : le **checksum** du paquet LoRa est valide, le contenu est cohérent. `false` : le paquet a été reçu, mais son contenu n’est pas fiable. |
| **checksum** | Contrôle d’intégrité (XOR des octets du paquet). La gateway compare la valeur reçue à celle qu’elle recalcule, puis renseigne `ok`. |
| **`bad_header`** | En-tête illisible (octet magique ou numéro de version invalides). Souvent lié à un RSSI trop faible pour un décodage correct. Enregistré avec `node_id` 0 : paquet **corrompu**, pas un trou de `seq`. |
| **`node_id`** | Identifiant du nœud émetteur (1 = WROOM-32D, 2 = ESP32-S3). La valeur 0 est réservée aux paquets corrompus. |
| **uptime** | Temps écoulé depuis le dernier démarrage du nœud, en secondes. Une chute brutale indique un redémarrage. |
| **SPI** | Bus série entre le microcontrôleur et le RA-02. Lignes : **NSS** (sélection de la puce), **SCK** (horloge), **MOSI** / **MISO** (données). |
| **DIO0** | Broche d’interruption du RA-02 : signale qu’un paquet est arrivé ou que l’émission est terminée. |
| **GPIO** | Broche d’entrée/sortie programmable d’un ESP32 (numérotée, par exemple GPIO 5). |
| **Gateway** | Ici : l’Arduino Uno. Elle reçoit les paquets LoRa, ajoute RSSI et SNR, et envoie une ligne JSON vers le PC. |
| **FedAvg** | *Federated Averaging* (McMahan et al., 2017) : moyenne pondérée des poids locaux. Formule et statut : section ci-dessous. |
| **POC** | *Proof of concept* : maquette destinée à démontrer que la chaîne fonctionne, pas un produit fini. |

Le détail radio (format des 14 octets, SF / BW / CR) est dans [docs/LORA.md](docs/LORA.md).

## Pourquoi ce montage

Il serait plus simple d’envoyer les mesures en Wi-Fi ou en 4G depuis chaque ESP32 vers le cloud. Ce choix ne permettrait pas de mesurer le **canal LoRa réel**, qui est l’objet de l’expérience (RSSI, SNR, trous de `seq`, paquets illisibles).

Un VPS n’a pas d’antenne RA-02. Si les nœuds publiaient directement en HTTP, on ne pourrait plus observer la radio. Le PC et l’Uno au milieu ne sont pas un détour : c’est l’instrument de mesure.

Un banc limité au Serial Monitor reste difficile à relire et à partager. D’où les quatre couches :

| Couche | Rôle | Ici |
|--------|------|-----|
| **1. Physique** | Capteurs, MCU, alimentation, fils | DHT11, ESP32, RA-02, Uno, convertisseur de niveaux |
| **2. Communication** | Transport objet → laboratoire | LoRa 433 MHz, USB 115200, HTTP POST |
| **3. Plateforme** | Stockage | FastAPI, PostgreSQL (`readings`, `node_stats`, `fl_updates`) |
| **4. Application** | Preuve que la chaîne fonctionne | Dashboard React, flux WebSocket |

## Méthodologie

| Phase | Objectif | Statut |
|-------|----------|--------|
| **v1** | Prouver ESP32 → LoRa → Uno → PC → site | **Réalisée** (dashboard comms) |
| **v2a** | Entraînement local + transport des poids sur LoRa | **Réalisée** (table `fl_updates`) |
| **v2b** | FedAvg synchrone : moyenne serveur + modèle global renvoyé | **À faire** |
| **v3** | Pertes, latence, RSSI dans le temps (métriques de thèse) | Plus tard |

FedAvg **synchrone** pour le POC : le serveur envoie un signal de début de round, et les nœuds qui participent s’entraînent dans la même fenêtre. Ce mode est plus simple à déboguer. L’asynchrone (chaque nœud envoie selon sa radio) est plus réaliste en LoRa ; il est prévu après le FedAvg sync.

Capture en continu (DHT toutes les 15 s, tampon local de 32 échantillons). L’entraînement local (SGD) tourne sur ce tampon. L’agrégation fédérée, elle, n’a lieu **que** lorsqu’un round est clos côté serveur. Ce n’est pas encore le cas.

## Apprentissage fédéré et FedAvg

Le Federated Learning vise à entraîner un modèle **sans centraliser les données brutes**. Chaque client \(k\) minimise une perte locale \(F_k\) sur son jeu \(D_k\) (ici : mesures DHT11 qui **restent sur l’ESP32**). Seuls les **paramètres** circulent.

L’algorithme retenu pour le POC est **Federated Averaging** (FedAvg), introduit par McMahan, Moore, Ramage, Hampson et y Arcas (2017) dans *Communication-Efficient Learning of Deep Networks from Decentralized Data* (AISTATS, PMLR 54). Après un round \(t\), le serveur forme le modèle global par **moyenne pondérée** par la taille des jeux locaux \(n_k = |D_k|\) :

$$
w_{t+1} \;\leftarrow\; \sum_{k=1}^{K} \frac{n_k}{n}\, w_{t+1}^{(k)}
\quad\text{avec}\quad
n = \sum_{k=1}^{K} n_k .
$$

\(K = 2\) sur ce banc. Un nœud absent (timeout LoRa) n’entre pas dans la somme : c’est précisément le cas expérimental du client en bord de couverture.

### Modèle embarqué (déjà en firmware)

Régresseur linéaire, quatre coefficients. On prédit la température au pas suivant à partir des deux températures précédentes et de l’humidité précédente (entrées normalisées \(T/50\), \(H/100\)) :

$$
\frac{\hat{T}_t}{50}
=
w_0\,\frac{T_{t-1}}{50}
+ w_1\,\frac{T_{t-2}}{50}
+ w_2\,\frac{H_{t-1}}{100}
+ w_3 .
$$

Le vecteur \(w = (w_0,w_1,w_2,w_3)\) part en LoRa (paquet 25 octets). **FedAvg consistera à moyenner ces quatre composantes** entre nœuds, puis à renvoyer \(w_{\text{global}}\). Cette moyenne n’est **pas** encore calculée par l’API.

## Première campagne (matériel réel)

Deux pièces, même gateway Uno. Nœud 1 (WROOM-32D) près de la gateway (lien témoin). Nœud 2 (ESP32-S3) plus loin (lien dégradé, climat distinct). LoRa 433 MHz, SF7, BW 125 kHz. Données lues sur le Postgres du déploiement personnel (29 août 2026) :

| Nœud | Lectures capteur | Poids reçus | RSSI moyen | SNR moyen | T moy. | Hum. moy. |
|------|------------------|-------------|------------|-----------|--------|-----------|
| 1 | 995 | 197 | −62,3 dBm | 9,77 dB | 24,9 °C | 63,1 % |
| 2 | 1082 | 195 | −83,9 dBm | 3,78 dB | 28,6 °C | 54,8 % |

Un seul `bad_header` (`node_id` 0). En phase « pièce distante », le nœud 2 a été observé vers **−100 dBm** avec un SNR parfois **négatif**, tout en restant décodable (`ok = true`). Les deux vecteurs \(w\) locaux divergent : chaque nœud apprend **son** microclimat (données non i.i.d.). C’est le régime pour lequel FedAvg est conçu.

Le nœud proche n’est **pas** un défaut : c’est le client qui répond de façon fiable. Le nœud loin teste la fédération sous contrainte radio.

## Chaîne

```text
[ DHT11 ] --1-wire--> [ ESP32 WROOM ou S3 ]
                            |
                      [ RA-02 433 MHz SF7 ]
                            | LoRa
                            v
                      [ RA-02 + Uno ]  --USB 115200-->  [ agent PC ]
                                                            |
                                                      HTTPS /api/ingest et /api/fl/update
                                                            v
                                              [ API + Postgres + dashboard ]
```

## Choix des protocoles

| Lien | Protocole | Pourquoi |
|------|-----------|----------|
| Nœud → gateway | **LoRa SPI**, paquet 14 octets | C’est le phénomène à mesurer |
| Gateway → PC | **USB série**, une ligne JSON | Lisible dans le moniteur série, sans pile IP sur l’Uno |
| PC → serveur | **HTTP POST** | Le PC a Internet. MQTT n’apporte pas d’avantage tant que ce relais existe |
| Serveur → navigateur | **WebSocket** + polling | Affichage en direct sur le dashboard |

MQTT pourra être envisagé plus tard, si un nœud doit joindre le cloud **sans** PC intermédiaire. Ce n’est pas le cas de ce banc.

Paquet capteur LoRa (14 octets, v1) : `node_id`, `seq`, température, humidité, uptime, checksum. Paquet **poids** (25 octets, v2) : les quatre coefficients \(w_i\). La gateway ajoute RSSI et SNR (mesurés par le SX1278 **à la réception**). Un `bad_header` est enregistré avec `node_id` 0 : paquet **corrompu**, pas un trou de `seq`.

Détail radio et broches : [docs/LORA.md](docs/LORA.md), [docs/HARDWARE.md](docs/HARDWARE.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Firmware

| Carte | Sketch | Radio |
|-------|--------|-------|
| WROOM-32D | `firmware/node_esp32` | NSS 5, SCK 18, MOSI 23, MISO 19, RST 14, DIO0 26 |
| ESP32-S3 | `firmware/node_esp32_s3` | NSS 5, SCK 18, MOSI 6, MISO 16, RST 14, DIO0 15, DHT GPIO 2 |
| Arduino Uno | `firmware/gateway_uno` | NSS D10, SCK D13, MOSI D11, MISO D12, RST D9, DIO0 D2 |

Sur l’ESP32-S3, `SPI.begin(18, 16, 6, 5)` est obligatoire avant `LoRa.begin` (le SPI par défaut ne correspond pas au câblage). Les sketches nœuds font aussi le SGD local et l’émission des poids (`fl_model.h`, `fl_pkt.h`).

Validation Serial Monitor (115200) :

<table>
  <tr>
    <td align="center" width="33%">
      <img src="docs/media/serial/01-serial-noeud1-wroom.png" alt="Serial Monitor nœud 1 WROOM-32D TX LoRa" width="100%" />
      <br /><sub><b>Nœud 1</b> WROOM-32D, COM3, <code>TX id=1</code></sub>
    </td>
    <td align="center" width="33%">
      <img src="docs/media/serial/02-serial-noeud2-s3.png" alt="Serial Monitor nœud 2 ESP32-S3 LoRa OK" width="100%" />
      <br /><sub><b>Nœud 2</b> ESP32-S3, COM9, <code>LoRa OK</code></sub>
    </td>
    <td align="center" width="33%">
      <img src="docs/media/serial/03-serial-gateway.png" alt="Serial Monitor gateway Arduino JSON LoRa" width="100%" />
      <br /><sub><b>Gateway</b> Uno, COM5, JSON reçu</sub>
    </td>
  </tr>
</table>

## Démo

Le GIF s’anime dans la page. Un clic ouvre la vidéo complète (MP4).

<a href="docs/media/demo-dashboard.mp4">
  <img src="docs/media/demo-dashboard.gif" alt="Dashboard v1 : nœuds 1 et 2, temp, hum, RSSI, seq" width="100%" />
</a>

*Dashboard v1, les deux nœuds en direct. [Vidéo complète (MP4)](docs/media/demo-dashboard.mp4)*

<a href="docs/media/demo-hardware.mp4">
  <img src="docs/media/demo-hardware.gif" alt="Banc matériel : ESP32, RA-02, Arduino Uno et DHT11" width="100%" />
</a>

*Banc câblé : nœuds ESP32, RA-02 et gateway. [Vidéo complète (MP4)](docs/media/demo-hardware.mp4)*

## Couche applicative

| Composant | Rôle |
|-----------|------|
| `agent/serial_bridge.py` | Lit le port COM, POST `/api/ingest` et `/api/fl/update` |
| FastAPI + Uvicorn | Ingest capteur, ingest poids, overview, WebSocket `/ws/live` |
| PostgreSQL 16 | `readings`, `node_stats`, `fl_updates` |
| React (Vite) | Cartes nœuds, journal, âge du dernier paquet |
| Docker / nginx | Reverse proxy. Brancher un domaine personnel ou un tunnel si besoin |

## Structure du dépôt

| Dossier | Rôle |
|---------|------|
| `firmware/` | Nœuds et gateway (cœur IoT) |
| `agent/` | Pont série → HTTP |
| `backend/` | API Python |
| `frontend/` | Dashboard v1 |
| `database/` | Schéma SQL |
| `docker/` | Compose (local ou VPS personnel) |
| `docs/` | Architecture, LoRa, matériel, déploiement, photos |

## Démarrage rapide

Matériel déjà câblé :

1. Flasher le WROOM (`NODE_ID` 1) et le S3 (`NODE_ID` 2), puis l’Uno.
2. Fermer le Moniteur série de l’Uno (sinon le port COM est occupé).
3. Agent :

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# INGEST_URL = l'URL de l'API déployée (exemple : http://localhost:8082)
# INGEST_TOKEN = le même que docker/.env
python serial_bridge.py --port COM5
```

Sans matériel, `python simulator.py` envoie des paquets simulés vers l’API.

Déploiement (local ou VPS personnel) : [docs/DEPLOY.md](docs/DEPLOY.md).

## Documentation

| Fichier | Contenu |
|---------|---------|
| [docs/HARDWARE.md](docs/HARDWARE.md) | Broches, couleurs, convertisseur de niveaux |
| [docs/LORA.md](docs/LORA.md) | Format paquet, SF / BW / CR |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Sync vs async, v1 / v2 / v3 |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Docker, tunnel optionnel |

## Références

McMahan, H. B., Moore, E., Ramage, D., Hampson, S. et y Arcas, B. A. (2017). Communication-efficient learning of deep networks from decentralized data. In *Proceedings of the 20th International Conference on Artificial Intelligence and Statistics* (AISTATS), PMLR 54, 1273-1282. [http://proceedings.mlr.press/v54/mcmahan17a.html](http://proceedings.mlr.press/v54/mcmahan17a.html)

## Licence

MIT. Projet pédagogique, destiné à la communauté IoT, embarqué et Federated Learning. Le code peut être copié, modifié et redistribué (voir [LICENSE](LICENSE)).
