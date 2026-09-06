# Synthèse : agrégation FedAvg sur liaison LoRa réelle

## Problématique

Le présent banc examine le comportement de Federated Averaging (McMahan et al., 2017) lorsque l’échange des paramètres s’effectue sur une liaison LoRa mesurée, et non sur un canal idéal. Les données brutes demeurent sur les nœuds. Seuls circulent quatre coefficients d’un régresseur linéaire. Deux clients sont en présence : l’un près de la gateway, l’autre en pièce distante. La question porte sur la moyenne globale lorsqu’un client est hors délai, lorsque le rapport signal sur bruit est faible ou négatif, et lorsque les distributions locales ne sont pas identiques.

Cinq versions successives documentent la chaîne, l’agrégation, un contrôle par échange des rôles, la latence de réponse, puis la sensibilité au timeout. Les mesures détaillées figurent dans les rapports de version et dans le répertoire `results/`. Le présent texte en donne la synthèse.

| Version | Objet | Document |
|---|---|---|
| v1 | Chaîne de communication | [V1_Rapport](v1/V1_Rapport.md) |
| v2 | Entraînement local et transport des poids | [V2_Rapport](v2/V2_Rapport.md) |
| v3 | FedAvg, erreur de prédiction, échange des rôles | [V3_Rapport](v3/V3_Rapport.md), [session d’inversion](v3/V3_Session_inversion.md) |
| v4 | Historique de réception et latence | [V4_Rapport](v4/V4_Rapport.md) |
| v5 | Alternance des timeouts 90 s, 120 s et 150 s | [V5_Rapport](v5/V5_Rapport.md) |

## Dispositif

Deux nœuds ESP32 (WROOM-32D et ESP32-S3), capteurs DHT11, modules RA-02 à 433 MHz (SF7, 125 kHz, CR 4/5), gateway Arduino Uno, agent série sur ordinateur de laboratoire, API et tableau de bord déployés par l’expérimentateur. Les lectures (température, humidité, RSSI, SNR, compteur de séquence, checksum) et les vecteurs de poids sont enregistrés en base.

La capture est continue (une lecture toutes les 15 s, tampon de 32 échantillons). L’entraînement local (descente de gradient stochastique) s’exécute sur ce tampon. L’agrégation a lieu à la clôture d’un round, ouvert par le serveur. Un nœud dont les poids arrivent après le timeout n’entre pas dans la moyenne. Le modèle global est renvoyé en liaison descendante.

## Résultats

### Chaîne et canal (v1, v2)

Les deux nœuds joignent le serveur. Un lien proche (RSSI de l’ordre de −70 dBm, SNR voisin de +10 dB) et un lien distant (RSSI voisin de −100 dBm, SNR fréquemment négatif) coexistent ; le second demeure souvent décodable. Les vecteurs locaux divergent, chaque nœud s’entraînant sur ses propres lectures.

Les pertes affichées par le tableau de bord ne sont pas toutes imputables à la radio. Un trou de séquence simultané sur les deux nœuds indique une interruption de l’agent, de l’ordinateur ou du serveur. Un taux proche de 99 % après reflashage correspond à un repli du compteur `seq`. Hors de ces artefacts, les pertes observées sont d’environ 1 % près de la gateway et d’environ 12 % en pièce distante.

### Agrégation et contrôle par échange des rôles (v3)

Le modèle global reste défini lorsqu’un seul client répond : il coïncide alors avec le vecteur de ce client. Pour le nœud exclu, l’erreur de prédiction, mesurée sur les lectures postérieures à la clôture, est 1,7 à 1,9 fois plus élevée que lorsqu’il a participé. Après échange des pièces et égalisation des puissances à 14 dBm, ce facteur se reproduit sur le nouveau nœud éloigné. La dégradation est donc attribuable à la liaison, et non à un exemplaire particulier.

À deux clients, l’exclusion d’un nœud laisse l’autre seul à définir le global. Le facteur mesuré est un plafond propre à cette configuration, et non une valeur générale de FedAvg. Le modèle local demeure plus précis que le modèle global dans 62 comparaisons sur 62 (*client drift*). Le régresseur n’améliore la persistance que lorsque le signal varie (+14 % sur le nœud le plus bruité, en session diurne).

Le RSSI moyen, calculé uniquement sur les paquets reçus, ne sépare pas participation et exclusion (biais du survivant). Le taux de réception le fait : 96 % contre 50 % pour le nœud éloigné.

L’écart de température d’environ 4 °C entre les deux nœuds ne s’est pas inversé avec les pièces. Une décomposition attribue 4,2 °C à la calibration des DHT11 (tolérance ±2 °C par exemplaire), 0,9 °C à l’heure de la journée et 0,1 °C à la différence entre pièces. L’hétérogénéité des données locales, à laquelle FedAvg est confronté, provient donc des capteurs.

### Latence et fenêtre d’attente (v4, v5)

Sur une session de 35 rounds, aucun paquet corrompu n’a été observé. Les latences médianes valent 45,9 s (nœud éloigné) et 38,6 s (nœud proche), avec un écart-type inférieur à une seconde. Un nœud n’émet ses poids qu’une fois par minute. Le signal `start_round` est reçu (le `round_id` des paquets est correct) mais n’entraîne aucune réponse immédiate ; les poids partent au créneau périodique suivant. La latence mesure l’écart de phase entre l’ouverture du round et cette horloge, et non la qualité radio.

Avec une réponse nominale d’environ 45 s, un cycle de 60 s et un timeout de 90 s, la fenêtre ne contient qu’une occasion d’émettre. Une perte unique reporte la réponse à environ 105 s et exclut le nœud. Ce mécanisme rend compte de l’écart entre un taux de perte paquet d’environ 17 % et un taux d’exclusion d’environ 37 %. Le modèle agrégé n’atteint pas de plateau en cinq heures ($w_0$ passe de 0,54 à 0,40).

L’alternance, au sein d’une même session, des timeouts 90 s, 120 s et 150 s permet de comparer les trois règles à radio, heure et matériel constants. Sur la phase de liaison stable (45 rounds, 15 par fenêtre), un rejeu des mêmes latences sous une règle unique donne 84 % de rounds à deux participants à 90 s, et 98 % à 120 s comme à 150 s. Les seconds créneaux observés se situent entre 107 s et 116 s. Les deux timeouts longs sont donc équivalents sur ce banc : le seuil utile est de dépasser un cycle d’émission (environ 115 s). Une arrivée à 174 s, correspondant à deux pertes consécutives, demeure hors de 120 s et de 150 s.

Une dégradation ultérieure du nœud éloigné (réception tombant à quelques pourcents) n’est compensée par aucune des trois fenêtres. L’allongement du timeout n’agit que sur une perte unitaire ; il ne rétablit pas un lien interrompu.

## Limites

Les résultats portent sur deux nœuds, un spreading factor unique (SF7) et un environnement intérieur. L’amplitude de la pénalité d’exclusion n’est pas extrapolable à un plus grand nombre de clients. La cause de l’absence de réponse immédiate à `start_round` n’est pas établie. Le modèle global n’a pas convergé sur la durée observée. Les capteurs n’ont pas été recalibrés.

## Référence

McMahan, H. B., Moore, E., Ramage, D., Hampson, S. et y Arcas, B. A. (2017). Communication-efficient learning of deep networks from decentralized data. In *Proceedings of the 20th International Conference on Artificial Intelligence and Statistics* (AISTATS), PMLR 54, 1273-1282.
