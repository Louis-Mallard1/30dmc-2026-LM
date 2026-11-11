@echo off
rem Reconstruit le site dans docs\ (double-clic).
rem Crée l'environnement virtuel .venv au premier lancement.
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto dependances
echo Création de l'environnement virtuel .venv...
python -m venv .venv
if errorlevel 1 goto erreur_python

:dependances
".venv\Scripts\python.exe" -c "import jinja2, PIL, markdown" 2>nul
if not errorlevel 1 goto construire
echo Installation des dépendances (Jinja2, Pillow, markdown)...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto erreur

:construire
echo.
".venv\Scripts\python.exe" construire.py
if errorlevel 1 goto erreur
echo.
echo Construction terminée. Lancez voir_site.bat pour ouvrir le site.
pause
exit /b 0

:erreur_python
echo.
echo Python est introuvable. Installez Python 3.11 ou plus récent depuis python.org.
pause
exit /b 1

:erreur
echo.
echo La construction a échoué. Lisez les messages ci-dessus.
pause
exit /b 1
