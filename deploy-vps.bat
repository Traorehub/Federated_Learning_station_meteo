@echo off
setlocal
echo ================================================
echo   Federated IoT - transfert vers VPS Hetzner
echo ================================================
echo.

set SSH_KEY=C:\Users\MOH\Documents\id_nearu_key
set SERVER=root@159.69.0.15
set PROJECT=/root/Federated_Learning_IoT

cd /d "%~dp0"

echo [1/2] Creation dossiers sur le VPS...
ssh -i "%SSH_KEY%" %SERVER% "mkdir -p %PROJECT%/backend/app %PROJECT%/frontend/src %PROJECT%/frontend/public %PROJECT%/docker/nginx/conf.d %PROJECT%/database %PROJECT%/docs %PROJECT%/agent %PROJECT%/firmware"

echo.
echo [2/2] Transfert...

scp -i "%SSH_KEY%" -r backend\app %SERVER%:%PROJECT%/backend/
scp -i "%SSH_KEY%" backend\requirements.txt backend\Dockerfile %SERVER%:%PROJECT%/backend/

scp -i "%SSH_KEY%" -r frontend\src %SERVER%:%PROJECT%/frontend/
scp -i "%SSH_KEY%" -r frontend\public %SERVER%:%PROJECT%/frontend/
scp -i "%SSH_KEY%" frontend\package.json frontend\index.html frontend\vite.config.ts frontend\tsconfig.json frontend\tsconfig.app.json frontend\tsconfig.node.json frontend\Dockerfile frontend\nginx.conf %SERVER%:%PROJECT%/frontend/

scp -i "%SSH_KEY%" docker\docker-compose.yml docker\deploy.sh docker\.env.example %SERVER%:%PROJECT%/docker/
scp -i "%SSH_KEY%" docker\nginx\conf.d\default.conf %SERVER%:%PROJECT%/docker/nginx/conf.d/

scp -i "%SSH_KEY%" database\schema.sql %SERVER%:%PROJECT%/database/
scp -i "%SSH_KEY%" README.md %SERVER%:%PROJECT%/

echo.
echo OK. Sur le VPS :
echo   cd %PROJECT%/docker
echo   cp .env.example .env   ^(si besoin^)
echo   chmod +x deploy.sh ^&^& ./deploy.sh
echo.
pause
