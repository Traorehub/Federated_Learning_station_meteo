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

La question de thèse n’est pas « peut-on afficher 24 °C sur un site ». C’est : **que devient cette moyenne quand le lien entre clients et agrégateur est du LoRa réel** (pertes, SNR faible, nœud absent, et deux jeux de données non i.i.d.) ?

Sans la couche radio, on pourrait faire du FedAvg sur un PC. On ne pourrait pas dire *pourquoi* un nœud n’a pas participé à un round, ni relier une erreur de modèle à un RSSI de −100 dBm.

## Ce qu’on cherche à trouver

Questions, du plus immédiat au plus loin :

| Question | Où ça se joue | État |
|----------|----------------|------|
| La chaîne physique tient-elle (deux nœuds, une gateway, un site) ? | v1 | Oui. Dashboard T, H, RSSI, SNR, `seq`, `ok`. |
| Les poids d’un modèle minuscule passent-ils en LoRa (paquet court) ? | v2 | Oui. 25 octets, table `fl_updates`. |
| Un nœud « bon lien » et un nœud « bord de couverture » coexistent-ils ? | v2 | Oui. Témoin ~ −70 dBm / SNR +10 dB ; loin ~ −100 dBm / SNR souvent négatif, encore décodable. |
| Les modèles locaux divergent-ils (non i.i.d.) ? | v2 | Oui, \(w\) différents (ex. \(w_1\) ~ 0,31 vs ~ 0,02). L’origine de l’écart est la **calibration des capteurs**, non les pièces (v3, échange des rôles). |
| Quelle part des « pertes » est radio, quelle part est le PC / l’agent ? | v2 | Un trou **simultané** des deux nœuds n’est pas LoRa. Un ~99 % dashboard après flash est un wrap de `seq`, pas le canal. Hors trou PC : ~1 % près, ~12 % loin. |
| FedAvg sous ces pertes : le modèle global reste-t-il utilisable si un nœud timeout ? | v3 | **Défini oui, utilisable non.** Le global se réduit au seul client reçu à temps et devient **1,7 à 1,9× moins précis** pour le nœud absent. |
| Cette dégradation vient-elle du lien ou du nœud ? | v3 | **Du lien.** Après échange des deux nœuds de pièce, à puissances égalisées, le phénomène a suivi la pièce (×1,8 à 1,9 sur le nouveau nœud éloigné). |
| Le modèle agrégé prédit-il mieux que les modèles locaux ? | v3 | Non, et c’est attendu : local meilleur dans 62 cas sur 62 (non i.i.d., *client drift*). |
| Le régresseur appris bat-il la prédiction triviale ? | v3 | **Seulement si le signal bouge.** +14 % sur le nœud bruité de jour ; indistinguable de la persistance sur un signal quasi immobile. |
| Le RSSI moyen renseigne-t-il sur la fiabilité du lien ? | v3 | **Non**, biais du survivant : il n’est mesuré que sur les paquets reçus. C’est le **taux de réception** qui sépare participation et exclusion (96 % contre 50 %). |
| RSSI/latence dans le temps | v4 | Fait. Vue `#reseau`. |
| Variation du SF, async, plus de deux nœuds | v4+ | Plus tard. |

Ce qu’on **ne** cherche pas ici : un thermomètre cloud, un réseau LoRaWAN opérateur, un réseau de neurones profond sur ESP32, une démo SaaS 24/7.

## Comment c’est monté

### Quatre couches IoT

| Couche | Rôle | Ici |
|--------|------|-----|
| Physique | Capteurs, MCU, alim, fils | DHT11, ESP32 WROOM + S3, RA-02, Uno, shifter 5 V / 3,3 V |
| Communication | Transport objet → labo | LoRa 433 MHz SF7, USB 115200 JSON, HTTP POST |
| Plateforme | Stockage | FastAPI, PostgreSQL (`readings`, `node_stats`, `fl_updates`, `fl_rounds`) |
| Application | Preuve que ça marche | Dashboard React, WebSocket |

### Pourquoi pas le Wi-Fi des ESP32

Le Wi-Fi irait au cloud sans passer par la radio LoRa. RSSI/SNR/`seq` disparaîtraient. Le serveur n’a pas d’antenne RA-02 : il ne peut pas « écouter » les nœuds. D’où l’Uno + le PC au laboratoire : c’est le point de mesure du canal. HTTP suffit tant que ce relais USB existe (MQTT : plus tard, si un nœud doit publier sans PC).

### Deux nœuds volontaires différents

Un nœud reste près de la gateway (**témoin**), l’autre occupe une pièce distante (**lien dégradé**). On ne rapproche pas le nœud éloigné pour égaliser les RSSI : le proche est le contrôle, le loin est la contrainte.

Les deux rôles ont depuis été **échangés** : le WROOM-32D est parti dans la pièce distante et l’ESP32-S3 est revenu près de la gateway, les deux à 14 dBm pour que seule la position les distingue. C’est ce contrôle qui établit que la dégradation du modèle suit le lien et non le matériel, et que l’écart de température entre clients vient des capteurs. Le WROOM tourne donc aujourd’hui à 14 dBm ; il avait été limité à 5 dBm après un brownout en v1, qui ne s’est pas reproduit.

### Apprentissage (cible)

Capture DHT toutes les 15 s, tampon local. Entraînement par **round**, pas en continu et pas « tout capter puis un seul fit ». FedAvg synchrone pour le POC (signal `start_round`). Détail : [rapport v3](v3/V3_Rapport.md).

Les dashboards ne se fusionnent pas : v1 = radio, v3 = rounds et modèle, v4 = métriques d’échelle.

## Comment on avance

| Version | Rôle | Statut |
|---------|------|--------|
| v1 | Chaîne comms | Faite. [Rapport](v1/V1_Rapport.md) |
| v2 | SGD local + poids LoRa + campagnes témoin/dégradé | Faite. [Rapport](v2/V2_Rapport.md) |
| v3 | Moyenne FedAvg + renvoi de \(w_{\text{global}}\) | Faite. [Rapport](v3/V3_Rapport.md), puis [échange des rôles](v3/V3_Session_inversion.md) |
| v4 | Historique du taux de réception, du RSSI et de la latence | Faite. Vue `#reseau` |
| v5 | Variation du SF, asynchrone, plus de deux nœuds | Plus tard |

Chaque version s’appuie sur la précédente. Flasher aujourd’hui installe la v3 (poids 27 octets + RX du modèle global). Relancer l’agent et reconstruire Docker.

## Où lire la suite

| Document | Contenu |
|----------|---------|
| [README](../README.md) | Hub : démo, table des versions, lancement |
| [v1](v1/V1_Rapport.md) | Câblage, paquet 14 o, RSSI, agent, `seq` |
| [v2](v2/V2_Rapport.md) | Modèle 4 poids, campagnes, artefacts de perte |
| [v3](v3/V3_Rapport.md) | FedAvg, paquets, API, UI `#rounds` |
| [HARDWARE.md](HARDWARE.md) | Broches et couleurs |
| [LORA.md](LORA.md) | Format radio |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Sync/async, périmètre |
| [DEPLOY.md](DEPLOY.md) | Docker |
| `results/` | CSV des campagnes |

Référence FedAvg : McMahan et al. (2017), AISTATS, PMLR 54, 1273-1282. [http://proceedings.mlr.press/v54/mcmahan17a.html](http://proceedings.mlr.press/v54/mcmahan17a.html)
