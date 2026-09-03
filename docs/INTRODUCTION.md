# Introduction au projet


## De quoi il s’agit

Banc d’essai pédagogique à **deux nœuds** IoT, dans le cadre d’un travail sur l’apprentissage fédéré (Federated Learning) sous contrainte réseau.

Chaque nœud : ESP32 + capteur DHT11 (température, humidité) + radio LoRa RA-02 (433 MHz). Une gateway Arduino Uno, aussi équipée d’un RA-02, reçoit les paquets. Un PC lit le port USB et envoie les données vers une API (Docker local ou VPS personnel) et un dashboard.

Licence MIT. Ce n’est pas un produit, ni un site public allumé en permanence. Le dépôt doit permettre de **reproduire** le banc avec son propre matériel et son propre serveur.

## Pourquoi ce projet

Trois raisons, dans cet ordre.

**1. Apprendre la chaîne IoT sur du matériel réel.**  
Câbler, alimenter (3,3 V, jamais 5 V sur le RA-02), flasher, lire un DHT, tenir un lien LoRa. Spreading factor, RSSI, SNR, paquets perdus ou illisibles : ce n’est pas une simulation. Le canal est physique.

**2. Disposer d’un banc reproductible.**  
Firmware, couleurs de fils, sketches et dashboard documentés pour qu’une autre personne refasse l’expérience.

**3. Relier le Federated Learning à un réseau imparfait mesuré.**  
Le FL entraîne un modèle **sans centraliser les données brutes**. Chaque client garde ses DHT ; seuls des **poids** circulent. L’algorithme visé est FedAvg (McMahan et al., 2017) : moyenne pondérée des modèles locaux.

La question de thèse n’est pas « peut-on afficher 24 °C sur un site ». C’est : **que devient cette moyenne quand le lien entre clients et agrégateur est du LoRa réel** (pertes, SNR faible, nœud absent, deux climats donc deux jeux non i.i.d.) ?

Sans la couche radio, on pourrait faire du FedAvg sur un PC. On ne pourrait pas dire *pourquoi* un nœud n’a pas participé à un round, ni relier une erreur de modèle à un RSSI de −100 dBm.

## Ce qu’on cherche à trouver

Questions, du plus immédiat au plus loin :

| Question | Où ça se joue | État |
|----------|----------------|------|
| La chaîne physique tient-elle (deux nœuds, une gateway, un site) ? | v1 | Oui. Dashboard T, H, RSSI, SNR, `seq`, `ok`. |
| Les poids d’un modèle minuscule passent-ils en LoRa (paquet court) ? | v2 | Oui. 25 octets, table `fl_updates`. |
| Un nœud « bon lien » et un nœud « bord de couverture » coexistent-ils ? | v2 | Oui. Témoin ~ −70 dBm / SNR +10 dB ; loin ~ −100 dBm / SNR souvent négatif, encore décodable. |
| Les modèles locaux divergent-ils (non i.i.d.) ? | v2 | Oui. Autre pièce, autre climat, \(w\) différents (ex. \(w_1\) ~ 0,31 vs ~ 0,02). |
| Quelle part des « pertes » est radio, quelle part est le PC / l’agent ? | v2 | Un trou **simultané** des deux nœuds n’est pas LoRa. Un ~99 % dashboard après flash est un wrap de `seq`, pas le canal. Hors trou PC : ~1 % près, ~12 % loin. |
| FedAvg sous ces pertes : le modèle global reste-t-il utilisable si le nœud 2 timeout ? | v3 | Pas encore mesuré. Agrégation non codée. |
| Sync vs async, plus de nœuds, historique RSSI | v3 puis v4 | Plus tard. |

Ce qu’on **ne** cherche pas ici : un thermomètre cloud, un réseau LoRaWAN opérateur, un réseau de neurones profond sur ESP32, une démo SaaS 24/7.

## Comment c’est monté

### Quatre couches IoT

| Couche | Rôle | Ici |
|--------|------|-----|
| Physique | Capteurs, MCU, alim, fils | DHT11, ESP32 WROOM + S3, RA-02, Uno, shifter 5 V / 3,3 V |
| Communication | Transport objet → labo | LoRa 433 MHz SF7, USB 115200 JSON, HTTP POST |
| Plateforme | Stockage | FastAPI, PostgreSQL (`readings`, `node_stats`, `fl_updates`) |
| Application | Preuve que ça marche | Dashboard React, WebSocket |

### Pourquoi pas le Wi-Fi des ESP32

Le Wi-Fi irait au cloud sans passer par la radio LoRa. RSSI/SNR/`seq` disparaîtraient. Le serveur n’a pas d’antenne RA-02 : il ne peut pas « écouter » les nœuds. D’où l’Uno + le PC au laboratoire : c’est le point de mesure du canal. HTTP suffit tant que ce relais USB existe (MQTT : plus tard, si un nœud doit publier sans PC).

### Deux nœuds volontaires différents

Nœud 1 (WROOM-32D) : 5 dBm (brownout à 14 dBm), près de la gateway : **témoin**.  
Nœud 2 (ESP32-S3) : 14 dBm, autre pièce : **lien dégradé** et autre microclimat.

On ne recule pas le nœud 1 pour égaliser les RSSI. Le proche est le contrôle ; le loin est la contrainte.

### Apprentissage (cible)

Capture DHT toutes les 15 s, tampon local. Entraînement par **round**, pas en continu et pas « tout capter puis un seul fit ». FedAvg synchrone pour le POC (signal `start_round`). Formule et travail restant : [rapport v3](v3/V3_Rapport.md).

Les dashboards ne se fusionnent pas : v1 = radio, v3 = rounds et modèle, v4 = métriques d’échelle.

## Comment on avance

| Version | Rôle | Statut |
|---------|------|--------|
| v1 | Chaîne comms | Faite. [Rapport](v1/V1_Rapport.md) |
| v2 | SGD local + poids LoRa + campagnes témoin/dégradé | Faite. [Rapport](v2/V2_Rapport.md) |
| v3 | Moyenne FedAvg + renvoi de \(w_{\text{global}}\) | À faire. [Rapport](v3/V3_Rapport.md) |
| v4 | Historique RSSI, latence, plus de nœuds | Plus tard |

Chaque version s’appuie sur la précédente. Flasher aujourd’hui installe la v2 (poids), pas la v3.

## Où lire la suite

| Document | Contenu |
|----------|---------|
| [README](../README.md) | Hub : démo, table des versions, lancement |
| [v1](v1/V1_Rapport.md) | Câblage, paquet 14 o, RSSI, agent, `seq` |
| [v2](v2/V2_Rapport.md) | Modèle 4 poids, campagnes, artefacts de perte |
| [v3](v3/V3_Rapport.md) | FedAvg, ce qui reste à coder |
| [HARDWARE.md](HARDWARE.md) | Broches et couleurs |
| [LORA.md](LORA.md) | Format radio |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Sync/async, périmètre |
| [DEPLOY.md](DEPLOY.md) | Docker |
| `results/` | CSV des campagnes |

Référence FedAvg : McMahan et al. (2017), AISTATS, PMLR 54, 1273-1282. [http://proceedings.mlr.press/v54/mcmahan17a.html](http://proceedings.mlr.press/v54/mcmahan17a.html)
