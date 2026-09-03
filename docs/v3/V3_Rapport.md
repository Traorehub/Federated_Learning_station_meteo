# v3 : FedAvg (à implémenter)

La v2 fait monter les vecteurs \(w^{(k)}\) jusqu’à Postgres. La v3 doit les **agréger** et **renvoyer** un modèle global aux nœuds, sur le même LoRa.

Rien de cette version n’est encore exécuté côté serveur. Le firmware écoute déjà un paquet `start_round` (type `0x10`, 8 octets). La gateway peut l’émettre depuis une ligne USB `{"cmd":"start_round","round":1}`. Il manque : clôture de round, moyenne, downlink \(w_{\text{global}}\), UI rounds.

## Algorithme

Federated Averaging, McMahan, Moore, Ramage, Hampson et y Arcas (2017), *Communication-Efficient Learning of Deep Networks from Decentralized Data*, AISTATS, PMLR 54.

Les données brutes \(D_k\) (DHT) restent sur le client \(k\). Seuls les paramètres circulent. Après un round \(t\) :

$$
w_{t+1}
\leftarrow
\sum_{k=1}^{K} \frac{n_k}{n}\, w_{t+1}^{(k)}
\quad\text{avec}\quad
n = \sum_{k=1}^{K} n_k .
$$

Ici \(K = 2\), \(w \in \mathbb{R}^4\) (même modèle que la v2). \(n_k\) : taille du jeu local (dans le firmware : `n_samples` / `n_trained`, borné par le tampon 32). Un nœud qui n’envoie pas à temps (perte LoRa, hors couverture) **n’entre pas** dans la somme. C’est le cas expérimental du client loin.

POC : mode **synchrone**. Le serveur envoie `start_round`. Les nœuds qui reçoivent le signal s’entraînent dans la même fenêtre puis montent \(w^{(k)}\). Plus simple à déboguer. L’asynchrone (chaque nœud envoie selon tampon / radio, sans barrière) est plus fidèle à un FL décentralisé sur LoRa ; il est prévu après le sync.

Ne pas fusionner le dashboard v1 (T, H, RSSI, `seq`) avec l’UI v3 (rounds, état attente / entraînement / update envoyée, perte du modèle agrégé).

## Travail restant (ordre utile)

1. API : démarrer un round, timeout, lister les `fl_updates` de ce `round_id`, calculer \(w_{\text{global}}\), persister le résultat.
2. Downlink : paquet LoRa des 4 poids globaux (réutiliser le format 25 octets ou un type dédié). Gateway : aujourd’hui TX `start_round` seulement.
3. Firmware : appliquer \(w_{\text{global}}\) au `FlModel` local quand le paquet est pour ce nœud / ce round.
4. Frontend v3 : round courant, qui a participé, \(w_{\text{global}}\), éventuellement une erreur de prédiction locale. Laisser les cartes radio v1 intactes.
5. Campagne : même placement témoin / dégradé, comparer un round où les deux nœuds répondent et un round où le nœud 2 timeout.

## Hors v3

Historique RSSI fin, latence, 15-20 nœuds : **v4**. MQTT : hors périmètre tant que le PC relais USB existe.

## Référence

McMahan et al. (2017), PMLR 54, 1273-1282. [http://proceedings.mlr.press/v54/mcmahan17a.html](http://proceedings.mlr.press/v54/mcmahan17a.html)
