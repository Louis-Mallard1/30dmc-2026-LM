@echo off
rem Sert le dossier docs\ sur http://localhost:8030/ et ouvre le navigateur.
rem Fermez cette fenêtre pour arrêter le serveur.
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist "docs\index.html" goto serveur
echo Le site n'est pas encore construit : lancez d'abord construire_site.bat.
pause
exit /b 1

:serveur
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
echo Site visible sur http://localhost:8030/ (sans cache : un rechargement suffit)
echo Fermez cette fenêtre pour arrêter le serveur.
rem Le navigateur s'ouvre une seconde après le démarrage du serveur.
start "" /b cmd /c "timeout /t 1 /nobreak >nul & start http://localhost:8030/"
"%PYTHON%" serveur_local.py 8030
if errorlevel 1 pause
