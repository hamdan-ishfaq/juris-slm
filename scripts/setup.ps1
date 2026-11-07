# JurisGuard V2 — Windows setup (Docker Desktop)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "=== JurisGuard V2 Windows Setup ===" -ForegroundColor Cyan

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker Desktop required. Install from https://www.docker.com/products/docker-desktop/"
}
docker compose version | Out-Null

if (Test-Path "images") {
    Get-ChildItem images\*.tar.gz | ForEach-Object {
        Write-Host "Loading $($_.Name)..."
        cmd /c "docker load -i `"$($_.FullName)`""
    }
}

New-Item -ItemType Directory -Force -Path data\models | Out-Null
if (Test-Path models) { Copy-Item -Recurse -Force models\* data\models\ }

$EnvFile = ".env"
if (-not (Test-Path $EnvFile)) {
    if (Test-Path ".env.airgap.example") { Copy-Item .env.airgap.example $EnvFile }
    elseif (Test-Path "config\.env.airgap.template") { Copy-Item config\.env.airgap.template $EnvFile }
}

$AdminEmail = Read-Host "Admin email [admin@local]"
if (-not $AdminEmail) { $AdminEmail = "admin@local" }
$AdminPassword = Read-Host "Admin password (min 8 chars)" -AsSecureString
$AdminPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($AdminPassword))
$OrgName = Read-Host "Organization name [Default Organization]"
if (-not $OrgName) { $OrgName = "Default Organization" }

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans
Start-Sleep -Seconds 15
docker compose exec -T api alembic upgrade head
$env:ADMIN_EMAIL = $AdminEmail
$env:ADMIN_PASSWORD = $AdminPasswordPlain
$env:ORG_NAME = $OrgName
docker compose exec -T api python /app/scripts/seed_admin.py

Write-Host ""
Write-Host "Setup complete. Open http://localhost:8002/app" -ForegroundColor Green
