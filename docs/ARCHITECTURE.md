# Architecture : POC 2 nœuds (étape 1)

## Périmètre actuel

**Dashboard v1 uniquement.** Chaîne de réception et visualisation brute.
Aucune logique d’entraînement, d’agrégation FedAvg, ni de rounds.

```
ESP32 + DHT11 + RA-02  --LoRa 433 MHz-->  Arduino Uno + RA-02
                                              |
                                         USB série 115200
                                              |
                                      Agent PC (poste de labo)
                                              |
                                      HTTPS POST /api/ingest
                                              v
                    API + PostgreSQL + dashboard
                    (Docker local ou VPS personnel)
```

L’Arduino est branché en USB sur le **PC**, pas sur le serveur.
L’agent local lit le port série et transmet vers l’API (locale ou distante).
C’est volontaire : le backend et le frontend restent sur le serveur déployé
par l’expérimentateur, le lien radio reste au laboratoire.

Il n’existe pas d’instance publique maintenue en continu. Chacun déploie
son propre serveur et peut l’arrêter à tout moment.

## Capture vs entraînement (cycle réel d’un nœud)

La capture et l’entraînement ne sont pas simultanés. Ce n’est pas non plus un schéma où l’on accumule d’abord toutes les données, puis on entraîne une seule fois.

1. Le nœud **capte en continu**, en tâche de fond, à intervalle fixe
   (DHT11 toutes les 15 s dans ce POC, plage cible 10-30 s).
   Cette capture est indépendante de tout entraînement. Les mesures sont
   stockées dans un tampon local.
2. L’**entraînement se déclenche par round**, pas en continu :
   - soit un critère local (assez de nouvelles données pour s’entraîner) ;
   - soit un signal du serveur (tous les nœuds s’entraînent maintenant).

Cette étape 1 n’implémente que (1) : capter, envoyer, stocker, afficher.

## Décision méthodologique : synchrone vs asynchrone

| Mode | Qui déclenche le round | Intérêt | Coût |
|---|---|---|---|
| **Synchrone (FedAvg classique)** | Le serveur envoie `start round` | Timing contrôlé, débogage plus simple | Les nœuds attendent un signal centralisé |
| **Asynchrone** | Chaque nœud selon son tampon / sa radio | Plus réaliste pour un FL décentralisé | Plus difficile à déboguer |

**Choix du POC à 2 nœuds : synchrone, piloté par le serveur.**

Justification : FedAvg classique, reproductible, timing maîtrisé.
L’asynchrone est plus fidèle à la thèse finale (dans un FL vraiment
décentralisé, les nœuds n’attendent pas un orchestrateur). Il viendra
après, une fois la chaîne radio et le dashboard v1 stables.

Cette décision est **documentée** pour la thèse ; elle n’est **pas encore
codée**. La v1 ne contient ni `start round` ni agrégation.

## Dashboards : trois étapes distinctes

Ces trois versions ne doivent pas être fusionnées.

| Version | Objectif | Statut |
|---|---|---|
| **v1** | Vérifier les communications : données brutes en direct (temp, hum, RSSI, SNR, seq, âge du dernier message) | **Cette étape** |
| **v2** | Rounds, état des nœuds (attente / entraînement / mise à jour envoyée), précision et perte du modèle agrégé | Après v1 testée sur matériel |
| **v3** | Métriques réseau et expérimentales à l’échelle : pertes, latence, RSSI dans le temps | Mise à l’échelle 15-20 nœuds |

Les métriques de liaison (RSSI, SNR, trous de séquence) remontent **dès la v1**
pour ne pas refaire le schéma plus tard. Le dashboard v3 les historisera finement.

## Ce que le serveur calcule déjà (v1)

Le serveur ne se limite pas au stockage :

- **RSSI / SNR** du dernier paquet (qualité instantanée du lien LoRa)
- **Compteur de séquence** : détection des paquets manquants
- **Taux de perte** = `missing / (received + missing)`
- **Paquets corrompus** (checksum LoRa invalide)
- **Âge** = maintenant - `last_seen_at`

## Hors périmètre (volontairement)

- Entraînement local sur ESP32
- Agrégation FedAvg
- Signal `start round`
- MQTT (inutile tant que le PC relaie déjà en HTTP)
- Dashboard v2 / v3
