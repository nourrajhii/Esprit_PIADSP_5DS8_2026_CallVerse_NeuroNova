# Script PowerShell pour lancer le projet Digital Twin PharmaShop
# Usage : .\lancer_projet.ps1

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  🚀 Lancement du Digital Twin PharmaShop" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Fonction pour vérifier si un port est occupé
function Test-Port {
    param([int]$Port)
    $connection = Test-NetConnection -ComputerName localhost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
    return $connection
}

# Fonction pour tuer un processus sur un port
function Kill-ProcessOnPort {
    param([int]$Port)
    $process = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($process) {
        Write-Host "⚠️  Port $Port occupé, arrêt du processus..." -ForegroundColor Yellow
        Stop-Process -Id $process -Force
        Start-Sleep -Seconds 2
    }
}

# Vérifier PostgreSQL
Write-Host "🔍 Vérification de PostgreSQL..." -ForegroundColor Yellow
if (Test-Port 5432) {
    Write-Host "✅ PostgreSQL est actif (port 5432)" -ForegroundColor Green
} else {
    Write-Host "❌ PostgreSQL n'est pas actif. Veuillez le démarrer !" -ForegroundColor Red
    Write-Host "   Windows : services.msc → PostgreSQL" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# Vérifier les fichiers .env
Write-Host "🔍 Vérification des fichiers de configuration..." -ForegroundColor Yellow

$envFiles = @(
    "RAG\.env",
    "dt-front\.env"
)

$allEnvExist = $true
foreach ($envFile in $envFiles) {
    if (Test-Path $envFile) {
        Write-Host "✅ $envFile existe" -ForegroundColor Green
    } else {
        Write-Host "❌ $envFile manquant" -ForegroundColor Red
        $allEnvExist = $false
    }
}

if (-not $allEnvExist) {
    Write-Host ""
    Write-Host "⚠️  Fichiers .env manquants. Veuillez les créer avant de continuer." -ForegroundColor Red
    Write-Host "   Voir LANCEMENT_PROJET.md pour les instructions" -ForegroundColor Gray
    exit 1
}

Write-Host ""

# Nettoyer les ports si nécessaire
Write-Host "🔍 Vérification des ports..." -ForegroundColor Yellow
if (Test-Port 8000) {
    Write-Host "⚠️  Port 8000 (Backend) déjà utilisé" -ForegroundColor Yellow
    $response = Read-Host "Voulez-vous arrêter le processus existant ? (O/N)"
    if ($response -eq "O" -or $response -eq "o") {
        Kill-ProcessOnPort 8000
    }
}

if (Test-Port 5173) {
    Write-Host "⚠️  Port 5173 (Frontend) déjà utilisé" -ForegroundColor Yellow
    $response = Read-Host "Voulez-vous arrêter le processus existant ? (O/N)"
    if ($response -eq "O" -or $response -eq "o") {
        Kill-ProcessOnPort 5173
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  🎯 Démarrage des services" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Démarrer le Backend FastAPI
Write-Host "🔧 Démarrage du Backend FastAPI (port 8000)..." -ForegroundColor Yellow
$backendPath = "RAG"
if (Test-Path $backendPath) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; .\venv\Scripts\activate; uvicorn backend.main:app --reload --port 8000"
    Write-Host "✅ Backend lancé dans un nouveau terminal" -ForegroundColor Green
    Start-Sleep -Seconds 5
} else {
    Write-Host "❌ Dossier RAG introuvable !" -ForegroundColor Red
}

Write-Host ""

# Démarrer le Frontend React
Write-Host "🎨 Démarrage du Frontend React (port 5173)..." -ForegroundColor Yellow
$frontendPath = "dt-front"
if (Test-Path $frontendPath) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; npm run dev"
    Write-Host "✅ Frontend lancé dans un nouveau terminal" -ForegroundColor Green
    Start-Sleep -Seconds 5
} else {
    Write-Host "❌ Dossier dt-front introuvable !" -ForegroundColor Red
}

Write-Host ""

# Proposer de lancer le Dashboard Streamlit
$launchStreamlit = Read-Host "Voulez-vous lancer le Dashboard Streamlit ? (O/N)"
if ($launchStreamlit -eq "O" -or $launchStreamlit -eq "o") {
    Write-Host "📊 Démarrage du Dashboard Streamlit (port 8501)..." -ForegroundColor Yellow
    $dashboardPath = "dashboard"
    if (Test-Path $dashboardPath) {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dashboardPath'; streamlit run app.py"
        Write-Host "✅ Dashboard Streamlit lancé dans un nouveau terminal" -ForegroundColor Green
    } else {
        Write-Host "❌ Dossier dashboard introuvable !" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ Projet lancé avec succès !" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Accès aux interfaces :" -ForegroundColor Yellow
Write-Host "   • Frontend React :     http://localhost:5173" -ForegroundColor White
Write-Host "   • Backend API :        http://localhost:8000" -ForegroundColor White
Write-Host "   • Swagger Docs :       http://localhost:8000/docs" -ForegroundColor White
if ($launchStreamlit -eq "O" -or $launchStreamlit -eq "o") {
    Write-Host "   • Dashboard Streamlit: http://localhost:8501" -ForegroundColor White
}
Write-Host ""
Write-Host "📝 Logs disponibles dans les terminaux ouverts" -ForegroundColor Gray
Write-Host ""
Write-Host "🛑 Pour arrêter : Ctrl+C dans chaque terminal" -ForegroundColor Gray
Write-Host ""

# Attendre 3 secondes puis ouvrir le navigateur
Write-Host "🌐 Ouverture du frontend dans 3 secondes..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "Appuyez sur Entrée pour fermer cette fenêtre..." -ForegroundColor Gray
Read-Host
