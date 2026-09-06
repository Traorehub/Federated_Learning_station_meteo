# v5 : comparaison des timeouts 90 s, 120 s et 150 s

La [v4](../v4/V4_Rapport.md) a établi qu’un nœud n’émet ses poids qu’une fois par minute, et que la fenêtre de 90 s ne contient donc **qu’une seule occasion**. Une perte unique reporte la réponse de 60 s et exclut le nœud, même si le lien n’est pas deux fois plus mauvais que mesuré.

La v5 teste cette prédiction sans toucher au firmware. Dans une même session, le serveur alterne les fenêtres **90 / 120 / 150 s** d’un round au suivant. L’heure, le climat et la radio restent communs aux trois conditions : seule change la durée d’attente.

Export : `results/campagne-2026-09-06-timeout/`. Placement inchangé : nœud 1 (WROOM-32D) en pièce éloignée, nœud 2 (ESP32-S3) à ~2 m, les deux à 14 dBm. Série automatique toutes les 5 minutes, lancée à 13:36 UTC, arrêtée d’elle-même à 18:57 UTC après trois rounds vides.

## Deux phases

La session n’est pas homogène. Il faut la couper, sinon on attribue à la fenêtre ce qui est une chute radio.

| Phase | Rounds | Heure (UTC) | Lien |
|---|---|---|---|
| **A — stable** | 295 à 339 (45) | 13:36 → 17:17 | Réception nœud 1 ~90–98 %, nœud 2 ~90–100 % |
| **B — dégradation du nœud 1** | 340 à 356 (17) | 17:22 → 18:42 | Réception nœud 1 2–67 %, puis reprise partielle |
| Queue vide | 357 à 359 | 18:47 → 18:57 | Plus personne ; la série s’arrête |

La phase A est l’expérience timeout. La phase B est un accident de liaison, utile comme contre-épreuve : quand le paquet n’arrive plus du tout, allonger la fenêtre ne ressuscite pas le nœud.

Les trois rounds vides de fin ne sont pas une pollution : le garde-fou (arrêt après trois clôtures sans participant) a fait ce pour quoi il avait été écrit.

## Phase A : la prédiction tient

Quinze rounds de chaque fenêtre, enchevêtrés.

| Fenêtre | Complets (2 nœuds) | Exclus nœud 1 | Exclus nœud 2 |
|---|---|---|---|
| 90 s | **13 / 15 (87 %)** | 0 | 2 |
| 120 s | **14 / 15 (93 %)** | 1 | 0 |
| 150 s | **15 / 15 (100 %)** | 0 | 0 |

Les latences nominales restent celles de la v4 : nœud 1 **54,4 s**, nœud 2 **47,9 s**. Quand le premier créneau manque, le suivant arrive **+60 s** plus tard — 107 à 116 s. Jamais autre chose.

| Round | Nœud | Latence | Fenêtre | Sort |
|---|---|---|---|---|
| 301, 331 | 2 | 109,7 s / 107,0 s | 90 s | **exclu** |
| 300, 303 | 1 | 115,6 s / 115,8 s | 150 s | **sauvé** |
| 309 | 2 | 108,9 s | 150 s | **sauvé** |
| 323 | 1 | 114,4 s | 120 s | **sauvé** |
| 329 | 1 | 173,9 s | 120 s | **exclu** (deux pertes, troisième créneau) |

Les deux exclusions à 90 s sont des seconds créneaux qui auraient passé 120 s. Les sauvetages à 120 s et 150 s sont des seconds créneaux qui auraient raté 90 s. Le seul échec au-delà de 90 s est un **troisième** créneau à 174 s : 150 s ne l’aurait pas sauvé non plus.

### Contre-factuel

Même latences, autre règle. Si toute la phase A avait tourné à une seule fenêtre :

| Timeout | Nœud 1 à temps | Nœud 2 à temps | Les deux |
|---|---|---|---|
| 90 s | 91 % | 93 % | **84 %** |
| 120 s | 98 % | 100 % | **98 %** |
| 150 s | 98 % | 100 % | **98 %** |
| 180 s | 100 % | 100 % | 100 % |

**120 s et 150 s sont ici équivalents.** Tous les seconds créneaux sont tombés entre 107 et 116 s, donc sous 120 s. La frontière utile n’est pas 150 : c’est **dépasser un cycle** (latence nominale + 60 s ≈ 105–115 s). 150 s n’est qu’une marge. 180 s aurait rattrapé l’unique double perte.

C’est pour ça que le 150 s observé fait 15/15 et le 120 s 14/15 : le 174 s est tombé sur un round à 120 s par le hasard de l’alternance, pas parce que 150 s est une meilleure règle.

## Phase B : le timeout ne répare pas un lien mort

À partir de 17:15 UTC, la réception du nœud 1 s’effondre (67 %, puis 7 %, puis 2 %), alors que le nœud 2 reste à ~92 %. Le RSSI des rares paquets survivants du nœud 1 ne s’effondre pas au même rythme (biais du survivant, déjà vu en v3) : le SNR, lui, passe vers −10 dB.

Sur ces 17 rounds, le nœud 1 manque 12 fois, le nœud 2 jamais. La fenêtre n’y change presque rien (33 % / 17 % / 40 % de rounds complets). Deux seconds créneaux sont encore sauvés (112,6 s à 150 s, 105,4 s à 150 s). Les arrivées à 171 s, 172 s, 231 s, 292 s restent hors de toutes les fenêtres testées.

Allonger le timeout **amortit une perte unitaire**. Il ne remplace pas un nœud qui a cessé d’être entendu.

La cause de cette dégradation (déplacement, obstacle, alimentation ou brouillage) n’est pas établie. Elle n’entre pas dans la comparaison des timeouts.

## Réception de la phase A

Zéro paquet corrompu. Quand un paquet arrive, il arrive intact — comme en v4.

| Nœud | Réception (13:45–17:00 UTC) | RSSI | SNR |
|---|---|---|---|
| 1 loin | ~90–98 % | −96 à −104 dBm | souvent autour de 0 dB |
| 2 près | ~90–100 % | ~−59 dBm | ~+9,6 dB |

Le premier seau (13:30) est un démarrage à ~50 % : les nœuds venaient d’être branchés l’un après l’autre. Il ne compte pas.

## Ce que cette session établit

La prédiction de la v4 est mesurée, pas seulement déduite. **Le protocole convertit une perte unitaire en exclusion** tant que la fenêtre ne contient qu’un créneau. Lui en donner deux (timeout ≳ 115 s) ramène le taux de rounds complets de 84 % à 98 % sur le même trafic, dans la même après-midi.

Le gain observé ne correspond pas à une amélioration du canal : placement et matériel sont inchangés. Il résulte de l’admission du second créneau d’émission dans la fenêtre d’attente.

Deux pertes consécutives exigent un troisième créneau (environ 175 s). Une interruption de liaison (phase B) n’est compensée par aucune des fenêtres testées.

## Ce que cette session ne dit pas

Elle ne dit pas que 150 s est le bon timeout en général. Sur ce banc, 120 s suffisait. Un nœud plus lent au premier créneau, ou un cycle d’émission différent, déplacerait le seuil.

Elle ne dit pas pourquoi `start_round` ne déclenche toujours aucune réponse immédiate. Le firmware n’a pas été touché, volontairement : corriger la cause avant de mesurer l’effet aurait interdit d’attribuer le gain à la fenêtre.

Elle ne recalibre pas les DHT11. L’écart de 4 °C et le *client drift* sont toujours là ; ce n’était pas la question.

## Périmètre

Cette session ferme le fil ouvert en v4. Le firmware (voie immédiate muette) et tout ce qui n’est pas la fenêtre d’attente sont hors de **cette** question. Bilan du banc : [BILAN.md](../BILAN.md).
