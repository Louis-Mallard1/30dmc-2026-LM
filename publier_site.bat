@echo off
rem Reconstruit le site puis le publie en ligne (double-clic).
rem Enchaîne : construction de docs\, enregistrement Git, envoi sur GitHub.
rem GitHub Pages met ensuite environ une minute à afficher la nouvelle version.
chcp 65001 >nul
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 goto erreur_git
git remote get-url origin >nul 2>nul
if errorlevel 1 goto erreur_depot

rem --- 1. Construction ---------------------------------------------------
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
echo === 1/3  Construction du site
".venv\Scripts\python.exe" construire.py
if errorlevel 1 goto erreur

rem --- 2. Enregistrement -------------------------------------------------
echo.
echo === 2/3  Enregistrement des changements
git add -A
git diff --cached --quiet
if not errorlevel 1 goto rien

rem Message du type : « Mise à jour du site : 7 cartes sur 30 (12/11/2026 08:30) »
".venv\Scripts\python.exe" -c "import json,datetime;d=json.load(open('docs/donnees/cartes.json',encoding='utf-8-sig'));print('Mise à jour du site : %%d cartes sur %%d (%%s)' %% (d['nb_livrees'],d['nb_jours'],datetime.datetime.now().strftime('%%d/%%m/%%Y %%H:%%M')))" > "%TEMP%\message_publication.txt"
git commit -q -F "%TEMP%\message_publication.txt"
if errorlevel 1 goto erreur
type "%TEMP%\message_publication.txt"
del "%TEMP%\message_publication.txt" >nul 2>nul

:envoyer
rem --- 3. Envoi ----------------------------------------------------------
echo.
echo === 3/3  Envoi sur GitHub
git push
if errorlevel 1 goto erreur_envoi
echo.
echo Publication terminée. Le site en ligne sera à jour dans une minute environ :
".venv\Scripts\python.exe" -c "import json;u=json.load(open('edition.json',encoding='utf-8-sig')).get('url_publique');print('  '+u+'/' if u else '')"
pause
exit /b 0

:rien
rem Rien de nouveau dans docs\ : on envoie quand même d'éventuels
rem enregistrements locaux pas encore partis.
git status -sb | findstr /c:"ahead" >nul
if not errorlevel 1 goto envoyer
echo Rien de nouveau à publier : le site en ligne est déjà à jour.
pause
exit /b 0

:erreur_git
echo Git est introuvable sur cet ordinateur.
pause
exit /b 1

:erreur_depot
echo Ce dossier n'est pas relié à un dépôt GitHub (voir le README, « Publier sur GitHub Pages »).
pause
exit /b 1

:erreur_python
echo.
echo Python est introuvable. Installez Python 3.11 ou plus récent depuis python.org.
pause
exit /b 1

:erreur_envoi
echo.
echo L'envoi sur GitHub a échoué : vérifiez la connexion Internet, puis relancez.
echo Les changements restent enregistrés sur l'ordinateur et partiront au prochain envoi.
pause
exit /b 1

:erreur
echo.
echo La publication a échoué. Lisez les messages ci-dessus.
pause
exit /b 1
