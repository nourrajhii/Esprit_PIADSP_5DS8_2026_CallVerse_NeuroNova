@echo off
REM Script batch simple pour lancer le projet Digital Twin PharmaShop
REM Double-cliquez sur ce fichier pour démarrer

echo ========================================
echo   Digital Twin PharmaShop - Lancement
echo ========================================
echo.

REM Vérifier PostgreSQL
echo [1/4] Verification PostgreSQL...
netstat -an | findstr ":5432" >nul
if %errorlevel% neq 0 (
    echo [ERREUR] PostgreSQL n'est pas actif !
    echo Demarrez PostgreSQL puis relancez ce script.
    pause
    exit /b 1
)
echo [OK] PostgreSQL actif
echo.

REM Démarrer Backend
echo [2/4] Demarrage Backend FastAPI...
start "Backend FastAPI" cmd /k "cd RAG && venv\Scripts\activate && uvicorn backend.main:app --reload --port 8000"
timeout /t 5 /nobreak >nul
echo [OK] Backend demarre (port 8000)
echo.

REM Démarrer Frontend
echo [3/4] Demarrage Frontend React...
start "Frontend React" cmd /k "cd dt-front && npm run dev"
timeout /t 5 /nobreak >nul
echo [OK] Frontend demarre (port 5173)
echo.

REM Ouvrir navigateur
echo [4/4] Ouverture du navigateur...
timeout /t 3 /nobreak >nul
start http://localhost:5173
echo.

echo ========================================
echo   Projet lance avec succes !
echo ========================================
echo.
echo Interfaces disponibles :
echo   - Frontend :   http://localhost:5173
echo   - Backend :    http://localhost:8000
echo   - API Docs :   http://localhost:8000/docs
echo.
echo Pour arreter : Fermez les fenetres de commande
echo.

REM Option pour lancer Streamlit
choice /c ON /n /m "Voulez-vous lancer le Dashboard Streamlit ? (O/N) "
if %errorlevel%==1 (
    echo.
    echo Demarrage Dashboard Streamlit...
    start "Dashboard Streamlit" cmd /k "cd dashboard && streamlit run app.py"
    echo [OK] Dashboard Streamlit demarre (port 8501)
    echo   - Dashboard :  http://localhost:8501
)

echo.
echo Appuyez sur une touche pour fermer cette fenetre...
pause >nul
