# Déploiement (local ou VPS personnel)

Il n’existe pas d’instance publique maintenue en continu. Chaque personne
déploie l’API, PostgreSQL et le dashboard chez elle (Docker en local, ou
un VPS / nom de domaine personnel) et peut tout arrêter à la fin.

Le PC de laboratoire reste au milieu : l’agent série lit la gateway Uno
et envoie les paquets vers **l’API que vous avez déployée**.

## 1. Secrets locaux

```powershell
copy docker\.env.example docker\.env
```

Renseigner `DB_PASSWORD` et `INGEST_TOKEN` (jeton long, aléatoire).
L’agent PC doit utiliser **le même** `INGEST_TOKEN`.

## 2. Docker Compose (recommandé pour commencer)

À la racine du dossier `docker/` :

```bash
docker compose up -d --build
```

Vérifier : `http://localhost:8082/health`.
Le reverse proxy nginx écoute sur le port **8082**.

Sur un VPS personnel, la même commande s’applique. Un script `docker/deploy.sh`
reconstruit les images et relance les services.

## 3. Accès distant (optionnel)

Si l’API doit être joignable hors du PC de labo, exposer le port 8082
derrière un tunnel ou un reverse proxy (Cloudflare Tunnel, nginx, etc.)
sur **votre** nom de domaine.

Exemple d’entrée Cloudflare Tunnel :

```yaml
# /etc/cloudflared/config.yml  (extrait)
ingress:
  - hostname: votredomaine.example
    service: http://localhost:8082
  - service: http_status:404
```

Puis redémarrer le service tunnel. Ce n’est pas une démonstration publique :
c’est un accès personnel, que l’on peut couper.

Dans `agent/.env`, `INGEST_URL` pointe alors vers cette URL HTTPS
(ou vers `http://localhost:8082` en local).

## 4. Agent PC (laboratoire)

```powershell
cd agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# INGEST_URL=http://localhost:8082   (ou l'URL HTTPS personnelle)
# INGEST_TOKEN=le même que docker/.env
python serial_bridge.py --port COM3
```

Sans matériel, pour valider le dashboard :

```powershell
python simulator.py
```
