# Session d’inversion : la pénalité suit-elle le lien ou le nœud ?

Deuxième session FedAvg, **40 rounds** (32 à 71), menée en série automatique à 5 minutes d’intervalle. Export : `results/campagne-2026-09-05-inverse/`.

Elle répond à une objection que la première session ne pouvait pas écarter. Le 4 septembre, on avait montré qu’un nœud exclu d’un round reçoit un modèle moins précis pour lui. Mais un seul placement laissait ouverte une explication concurrente : peut-être que le modèle du nœud éloigné était simplement mauvais en soi, indépendamment de la radio. Pour trancher, il fallait **échanger les rôles**.

## Ce qui a changé, et pourquoi on ne peut pas fusionner

| | Session du 4 septembre | Cette session |
|---|---|---|
| Nœud 1 (WROOM-32D) | ~2 m, **5 dBm**, témoin | **autre pièce**, **14 dBm** |
| Nœud 2 (ESP32-S3) | autre pièce, 14 dBm, dégradé | **~2 m**, 14 dBm |
| RSSI nœud éloigné | −105 à −109 dBm | −93 à −100 dBm |
| Cadence | manuelle | série automatique, 5 min |

Deux variables ont bougé : la position **et** la puissance d’émission. Le nœud 1 était à 5 dBm parce qu’un brownout le faisait redémarrer à 14 dBm en v1 ; le laisser à 5 dBm dans la pièce éloignée aurait mélangé l’effet de la distance et celui du bilan de liaison. Une fois les deux nœuds à 14 dBm, **seule la position distingue les clients**.

Le passage à 14 dBm n’a pas réveillé le brownout : la séquence du nœud 1 est continue sur toute la session, sans aucune remise à zéro.

Il s’ensuit que les deux sessions décrivent **deux conditions distinctes** et ne doivent jamais être agrégées dans les mêmes moyennes. Ce n’est pas une gêne : c’est précisément ce qui permet la comparaison croisée ci-dessous.

### Rounds écartés

Les rounds 22 à 31 forment une phase intermédiaire où le nœud 1 avait déjà déménagé mais émettait encore à 5 dBm : il perdait environ 89 % de ses paquets et ne fournissait aucun triplet exploitable. Les rounds 20 et 27 à 30 se sont clos à vide ou ont été recollés après coup avec des poids arrivés hors délai. Tous sont écartés. L’analyse part du round 32.

## Participation

| Clôture | Rounds | Durée |
|---|---|---|
| Les **deux** nœuds | 22 | ~56 s (médiane), avant le timeout |
| **Un seul** ou aucun | 18 | 90 s (timeout) |

Le nœud 1 a participé à 25 rounds et manqué les 15 autres ; le nœud 2 a participé 37 fois et manqué 3 fois. Les pertes mesurées sur la session valent 17,5 % pour le nœud 1 et 9,3 % pour le nœud 2.

Ce dernier chiffre mérite attention : à −46 dBm, le canal ne devrait rien coûter au nœud proche. Ces 9 % sont le prix du protocole, la gateway étant sourde pendant ses propres émissions — retransmission du `start_round` toutes les 2,5 s, puis diffusion du modèle global.

Les absences du nœud 1 ne sont pas réparties au hasard dans le temps : les rounds 46 à 51 forment un bloc continu d’exclusions, avec par moments aucun paquet reçu du tout. La dégradation vient par épisodes.

## Erreur de prédiction

Même méthode que la première session : chaque \(w\) est rejoué sur les températures mesurées dans les 15 min suivant la clôture, avec la persistance (\(T_t = T_{t-1}\)) comme référence, et seuls les triplets à `seq` consécutifs sont retenus. Sur 1412 lectures, **1200 triplets** exploitables — contre 319 le 4 septembre.

RMSE moyen, en degrés Celsius :

| Nœud | Persistance | Son modèle local | Global **s’il a participé** | Global **s’il était absent** | Pénalité |
|---|---|---|---|---|---|
| 1 (éloigné) | 0,039 | 0,036 | 0,539 | 1,042 | **×1,8 à 1,9** |
| 2 (proche) | 0,410 | 0,352 | 0,539 | 0,990 | **×1,8** |

La colonne « global s’il a participé » du nœud 1 inclut trois rounds (41, 42, 54) où c’était le nœud **2** qui manquait : le global valait alors le vecteur du nœud 1 lui-même, avec une erreur de 0,03. Ces valeurs tirent le dénominateur vers le bas. En les écartant, la pénalité du nœud 1 vaut **×1,8** au lieu de ×1,9. Le résultat ne dépend donc pas de ces trois rounds, mais le chiffre annoncé doit être lu comme ×1,8 à ×1,9.

### La pénalité suit le lien, pas le nœud

C’est le résultat de la session. Le 4 septembre, quand le nœud **2** était l’éloigné, sa pénalité valait ×1,7. Ici, rôles échangés, on mesure ×1,9 pour le nœud 1 et ×1,8 pour le nœud 2. L’ordre de grandeur est le même dans les deux configurations et pour les deux matériels.

L’explication concurrente tombe donc : ce n’est pas une propriété d’un nœud particulier, c’est une conséquence de l’exclusion. Un client qui rate un round repart avec un modèle calibré sur les données de l’autre, quel que soit le client.

Réserve de méthode : la pénalité du nœud 1 s’appuie sur 15 rounds, celle du nœud 2 sur 3 seulement, puisqu’il était bien reçu. C’est le nœud 1 qui porte la démonstration ici, et le nœud 2 qui la portait le 4 septembre — les deux sessions se complètent.

#### Contrôle : ce n’est pas un effet de période

Les absences du nœud 1 ne sont pas réparties uniformément, et son erreur globale dérive au fil de la session : environ 0,37 sur les premiers rounds à deux nœuds, environ 0,79 sur les derniers. Comme les absences tombent plutôt en fin de session, la pénalité pouvait n’être qu’un effet de période déguisé. Chaque absence a donc été comparée non à la moyenne de la session mais à ses **rounds voisins immédiats** :

| Round(s) absent(s) | Erreur | Voisins présents | Rapport local |
|---|---|---|---|
| 37-38 | 0,74 | 0,37 – 0,41 | ×1,9 |
| 49-51 | 1,08 | 0,57 – 0,89 | ×1,8 |
| 60 | 1,34 | 0,62 – 0,70 | ×2,0 |
| 65 | 1,55 | 0,70 – 0,81 | ×2,0 |
| 71 | 1,80 | 0,79 | ×2,3 |

Le rapport reste entre 1,8 et 2,3 sur toute la session, y compris à la fin. La pénalité n’est donc pas absorbée par la dérive temporelle. Cette dérive elle-même n’est pas expliquée : l’écart de température entre les deux pièces a pu croître au cours de la journée, rendant la moyenne progressivement moins adaptée au nœud 1, mais rien ne l’établit ici.

#### Portée de la pénalité : deux limites à ne pas taire

**À deux clients, la pénalité est maximale par construction.** Quand le nœud 1 est absent, le modèle « global » qu’il reçoit *est* le modèle du nœud 2 : il n’y a plus de moyenne, il n’y a plus qu’un contributeur. Ce qu’on mesure est donc le pire cas possible, « recevoir le modèle de l’autre à la place du sien ». Avec dix clients, l’absence d’un seul déplacerait à peine la moyenne. Le ×1,8 à ×1,9 n’est pas un chiffre général sur FedAvg : c’est le **plafond** d’un banc à deux clients. Le mécanisme est démontré, son amplitude est propre à cette configuration.

**La pénalité est mesurée sur un modèle figé.** Le nœud adopte réellement le vecteur global — `fl_apply_w` écrase ses poids locaux, ce n’est pas un simple stockage — mais il reprend ensuite son SGD à partir de là et se recale sur ses propres données. Le RMSE, lui, rejoue le vecteur *gelé* sur les quinze minutes suivantes. Il mesure donc la dégradation à l’instant de la remise, non l’erreur réellement vécue par le nœud, qui est plus faible. La pénalité est une borne supérieure.

### Le modèle global reste moins bon que les modèles locaux

Sur **62 comparaisons sur 62**, le modèle local d’un nœud prédit mieux ses propres températures que le modèle global. La première session donnait 27 sur 28. C’est le *client drift* attendu en apprentissage fédéré non i.i.d., et il se confirme sur un échantillon quatre fois plus grand.

Ce décompte est une description, pas un test statistique. Des rounds espacés de 5 minutes évalués sur des fenêtres de 15 minutes se recouvrent largement : ces 62 comparaisons ne constituent pas 62 observations indépendantes, et le rapport 62/62 ne doit pas être lu comme une significativité écrasante. `independance.py` montre que le sens du résultat tient à des horizons réduits (10, 5 et 3 min), ce qui est l’argument à retenir plutôt que le décompte lui-même.

### Correction : le régresseur bat la persistance, si le signal bouge

Le rapport de la première session concluait que la persistance battait le régresseur, et donc que le modèle à quatre poids n’apportait rien en précision. **Cette conclusion est infirmée ici**, mais de façon inégale selon le nœud.

Pour le nœud 2, l’écart est substantiel : 0,352 contre 0,410, soit 14 % de gain. Pour le nœud 1, il vaut 0,036 contre 0,039, soit **trois millièmes de degré** — en dessous de tout sens physique pour un DHT11. Il faut donc énoncer la correction ainsi : le régresseur bat la persistance **sur le nœud dont le signal bouge réellement**, et reste indistinguable d’elle sur le nœud presque immobile.

La conclusion précédente reposait sur 319 triplets d’une session nocturne où la température bougeait à peine ; celle-ci s’appuie sur 1200 triplets sur une plage de milieu de journée, plus variable. C’est cette session qui fait foi. Le régresseur apporte donc quelque chose, à condition que le signal bouge — ce qui est une nuance, pas un gain général.

## Ce que le RSSI ne peut pas montrer

On attendait de pouvoir relier l’exclusion d’un nœud à la qualité de son lien. Le résultat est contre-intuitif.

| Nœud | RSSI s’il participe | RSSI s’il est absent | Réception s’il participe | Réception s’il est absent |
|---|---|---|---|---|
| 1 | −95,8 dBm | −97,5 dBm | 96 % | 50 % |
| 2 | −52,2 dBm | −46,2 dBm | 93 % | 83 % |

Le RSSI moyen **n’explique pas** l’exclusion : 1,7 dB d’écart sur le nœud 1, et un écart de signe contraire sur le nœud 2. En revanche le **taux de réception** pendant le round l’explique nettement : 96 % quand le nœud 1 participe, 50 % quand il manque, soit un facteur deux.

La raison tient à un **biais du survivant**. Le RSSI n’est enregistré que sur les paquets effectivement reçus. Quand le lien lâche, il n’arrive pas un paquet faible : il n’arrive rien. Le niveau moyen est donc structurellement incapable de refléter la dégradation, puisqu’il ne décrit que les paquets qui ont réussi.

C’est une conclusion de méthode, et elle a une conséquence directe sur la v4 : le tableau de bord prévu doit historiser le **débit de réception**, et pas seulement le RSSI comme envisagé jusqu’ici.

Le résultat à retenir est le résultat **nul** sur le RSSI. Le versant positif est en partie définitionnel : rater un round, c’est précisément n’avoir pas livré son paquet de poids, si bien que « faible taux de réception » et « non-participation » sont presque la même observation. Dire que la réception prédit la participation n’apprend donc pas grand-chose ; ce qui surprend, c’est que le niveau de signal, lui, n’en dise rien.

De la même façon, les 9,3 % de pertes du nœud proche sont *attribués* au half-duplex, mais cela n’est pas démontré : il faudrait vérifier que ces pertes coïncident bien avec les fenêtres d’émission de la gateway. Les séries de la v4 permettront de le faire.

## L’hétérogénéité vient des capteurs, pas des pièces

L’échange de pièces constitue une expérience de contrôle qui n’était pas prévue, et son résultat oblige à corriger la lecture des deux sessions.

| | Nœud 1 | Nœud 2 |
|---|---|---|
| 4 septembre | 25,4 °C — pièce **proche** | 29,5 °C — pièce **éloignée** |
| Cette session | 26,2 °C — pièce **éloignée** | 30,5 °C — pièce **proche** |

Si l’écart venait des pièces, l’échange aurait dû échanger les valeurs : le nœud 1, parti dans la pièce chaude, devait monter vers 29,5 °C, et le nœud 2, arrivé dans la fraîche, descendre vers 25,4 °C. On observe l’inverse exact. Rien ne s’est échangé : le nœud 1 est resté le froid, le nœud 2 le chaud, et il est même devenu légèrement plus chaud en rejoignant la pièce censée être la plus fraîche.

### Décomposition des trois effets

Deux choses ont bougé entre les sessions : les pièces **et** l’heure. Quatre mesures suffisent à les séparer. En notant \(A\) l’écart de calibration entre capteurs, \(B\) l’écart réel entre pièces et \(d\) le décalage dû à l’heure, les deux sessions donnent \(A + B = -4{,}1\) et \(A - B = -4{,}3\) (le signe de \(B\) s’inverse avec l’échange), et la somme des quatre mesures donne \(2d = +1{,}8\).

| Cause | Contribution |
|---|---|
| Écart de calibration entre les deux DHT11 | **4,2 °C** |
| Heure de la journée (nuit → milieu de journée) | **+0,9 °C**, sur les deux nœuds |
| Différence réelle entre les deux pièces | **0,1 °C** |

L’heure explique donc bien quelque chose, mais uniquement le **décalage commun** aux deux nœuds : un effet qui pousse les deux valeurs vers le haut du même montant ne modifie pas l’écart entre elles, et c’est cet écart qui est en question. Elle ne peut pas expliquer que la différence de 4 °C soit restée attachée aux boîtiers pendant l’échange.

Que les deux estimations de l’écart, −4,1 et −4,3, tombent à 0,2 °C l’une de l’autre alors qu’elles proviennent de placements opposés est ce qui rend la décomposition crédible. Une réserve : le raisonnement suppose que l’écart entre les deux pièces ne dépend pas lui-même de l’heure, ce qui est plausible pour deux pièces d’un même logement mais n’est pas mesuré.

Le nœud 2 est par ailleurs environ dix fois plus bruité que le nœud 1 — son RMSE de persistance vaut 0,41 contre 0,04 — et cela aussi dans les deux pièces.

La conclusion s’impose : l’hétérogénéité entre les deux clients provient d’un **écart de calibration entre les deux DHT11**, dont la tolérance est de ±2 °C par exemplaire, ce qui autorise 4 °C d’écart entre deux unités posées côte à côte. Il n’y a pas de microclimat.

Cela n’affaiblit pas le travail. Les distributions locales restent bel et bien différentes, FedAvg y est bel et bien confronté, et le *client drift* mesuré plus haut est réel. Seule la **cause** de l’hétérogénéité change. On peut même soutenir qu’elle est plus représentative ainsi : dans un parc IoT réel, des capteurs bon marché dérivent chacun de leur côté, et c’est une source de non-i.i.d. au moins aussi fréquente que la géographie.

## Ce que cette session établit

La qualité radio se propage jusqu’à la qualité du modèle, et l’effet est **attribuable au lien** puisqu’il se reproduit du même ordre quand on échange les nœuds de pièce. Un timeout ne retire pas seulement un client d’une statistique de participation : il lui renvoie, à l’instant de la remise, un modèle près de deux fois moins précis pour lui. Cette amplitude est celle d’un banc à deux clients, où l’exclusion d’un nœud laisse l’autre seul à définir le global ; c’est donc un plafond, pas une valeur générale.

Le modèle agrégé reste moins bon que chaque modèle local, ce qui est la contrepartie normale de l’hétérogénéité. Il bat la persistance sur le nœud dont le signal varie, là où la première session ne l’avait pas montré faute d’un signal assez dynamique ; sur le nœud presque immobile, il en reste indistinguable.

L’hétérogénéité entre clients, enfin, n’a pas l’origine qu’on lui prêtait : la décomposition attribue 4,2 °C à l’écart de calibration des capteurs et 0,1 °C seulement à la différence entre les pièces.

Enfin, la session livre un enseignement de méthode qu’aucune simulation n’aurait produit : au bord de la couverture, le niveau de signal moyen ne renseigne pas sur la fiabilité du lien, parce qu’on ne mesure que les paquets qui ont survécu.

## Corrections répercutées ailleurs

Ces résultats invalidaient des affirmations présentes dans les documents existants. Elles ont été reprises :

| Fichier | Correction |
|---|---|
| `README.md` | Section « Contrôle par échange des rôles » ajoutée ; « microclimats » remplacé par la décomposition capteur / heure / pièce ; conclusion sur la persistance rendue conditionnelle |
| `docs/v3/V3_Rapport.md` | Même deux corrections, avec un tableau de ce que l’échange révise ; conditions du relevé conservées telles quelles |
| `docs/v2/V2_Rapport.md` | Écart entre nœuds réattribué aux capteurs ; mention que les rôles et la puissance ont changé depuis |
| `docs/INTRODUCTION.md` | Rôles décrits comme échangeables plutôt que fixes ; questions de recherche mises à jour (lien vs nœud, RSSI aveugle, persistance conditionnelle) |
| `docs/ARCHITECTURE.md` | v4 marquée faite et orientée taux de réception plutôt que RSSI seul |
| `docs/LORA.md` | Puissances égalisées à 14 dBm sur les trois cartes |
| `docs/v1/V1_Rapport.md` | Note de brownout nuancée, pas supprimée : elle était exacte dans les conditions d’alimentation de l’époque |
| `firmware/node_esp32*.ino` | En-têtes corrigés (écoute continue, 14 dBm) et `RX_WINDOW_MS` mort supprimé |

En revanche, la description de la session du 4 septembre dans `V3_Rapport.md` **conserve** ses conditions d’origine : c’est un relevé daté, pas une description de la configuration courante.

## Fichiers

```text
results/campagne-2026-09-05-inverse/
  fl_rounds.csv          rounds 32 à 71
  fl_updates.csv         poids reçus, tagués par round
  readings.csv           lectures capteur de la fenêtre
  erreur.py              RMSE, persistance de référence
  participation.py       participation vs RSSI et taux de réception
  resume.txt             chiffres et mises en garde
```
