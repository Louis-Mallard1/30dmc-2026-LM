# Trente cartes de Rochefort

Site vitrine du #30DayMapChallenge 2026 de Louis MALLARD : une carte par jour de novembre, toutes centrées sur Rochefort.

Le site est **statique** : pas de serveur, pas de base de données, pas de traceur. Le dossier `docs/` est généré par un script Python et se publie tel quel.

Le cahier des charges et les consignes de travail restent sur l'ordinateur de l'auteur ; ils ne sont pas publiés dans ce dépôt.

## Utilisation au quotidien

| Je veux… | Je fais… |
|---|---|
| Reconstruire le site après une nouvelle carte | double-clic sur `construire_site.bat` |
| Voir le site sur mon ordinateur | double-clic sur `voir_site.bat` (ouvre http://localhost:8030/) |
| Publier en ligne (reconstruit, enregistre et envoie sur GitHub) | double-clic sur `publier_site.bat` |

**Ajouter une carte** : il n'y a rien à toucher dans le site. Il suffit que la carte soit au statut `livrée` dans `../suivi.csv` et que ses exports soient dans `../JNN_slug/export/` (PNG 1080 × 1350, PNG HD 4320 × 5400, PDF). On relance ensuite `construire_site.bat`.

À la première utilisation, `construire_site.bat` crée un environnement Python dans `.venv/` et y installe Jinja2, Pillow et Markdown (connexion Internet nécessaire une fois). Il faut Python 3.11 ou plus récent ([python.org](https://www.python.org/)).

La console affiche un résumé : cartes publiées, avertissements (fichier manquant, par exemple) et poids total de `docs/`. Une carte dont le PDF ou le PNG HD manque est publiée sans le bouton correspondant.

## Ce qu'il reste à rédiger

| Fichier | Contenu |
|---|---|
| `contenu/a-propos.md` | Texte de la page À propos (marqueurs `[À COMPLÉTER]`) |
| `contenu/mentions-legales.md` | Contact, hébergeur, licence (marqueurs `[À COMPLÉTER]`) |
| `edition.json` → `licence_cartes` | Mention de licence affichée sous les téléchargements |
| `edition.json` → `accroche` | Les deux phrases de l'encart « À propos » de l'accueil |

Ces fichiers sont en Markdown ou en JSON ; on relance la construction après chaque modification.

## Organisation

```
site_web/
├─ edition.json            configuration de l'édition (titre, année, chemins, adresse publique…)
├─ construire.py           générateur : lit les sources, produit docs/
├─ construire_site.bat     double-clic : reconstruit docs/
├─ voir_site.bat           double-clic : serveur local + navigateur
├─ publier_site.bat        double-clic : reconstruit puis publie sur GitHub Pages
├─ serveur_local.py        serveur de prévisualisation sans cache (lancé par voir_site.bat)
├─ requirements.txt        Jinja2, Pillow, Markdown
├─ contenu/                textes des pages À propos et Mentions légales
├─ src/
│  ├─ gabarits/            pages (Jinja2)
│  ├─ css/site.css         feuille de style unique
│  ├─ js/                  accueil (lampe, carrousel), fiche (zoom), commun (flèche du nord)
│  ├─ polices/             woff2 + licences OFL ; sources/ = TTF originaux
│  └─ calque/              plan de Rochefort (SVG) et son script
└─ docs/                   GÉNÉRÉ : ne jamais modifier à la main
```

Le site lit `../suivi.csv`, `../00_charte/themes_2026.md` et les dossiers `../JNN_*/export/` **sans jamais les modifier**.

## Opérations ponctuelles

Ces scripts ne servent qu'une fois ; leurs résultats sont déjà dans `src/`.

- **Recadrer le calque de Rochefort** (demande geopandas, déjà présent avec le Python système) :
  ```bash
  python src/calque/generer_calque.py --centre 392900 6544750 --largeur 7600
  ```
  Le centre est en Lambert-93 (mètres), la hauteur vaut largeur × 9/16.
- **Refaire les polices** (demande fonttools et brotli) :
  ```bash
  .venv\Scripts\python.exe -m pip install fonttools brotli
  .venv\Scripts\python.exe src\polices\preparer_polices.py
  ```

## Une autre édition (2027…)

Copier `site_web/` pour la nouvelle édition, puis modifier `edition.json` : année, titre, chemins de `suivi` et de `themes`, adresse publique. Si la ville change, régénérer le calque. Aucun gabarit n'est à modifier.

## Publier sur GitHub Pages

Le site n'est **pas encore en ligne**. Le jour venu :

1. **Créer un dépôt public** sur GitHub, ici `30dmc-2026-LM` (sans README ni licence, pour qu'il soit vide).
2. **Envoyer `site_web/`** dans ce dépôt. Depuis le dossier `site_web/`, dans un terminal :
   ```bash
   git init -b main
   git add .
   git commit -m "Site du #30DayMapChallenge 2026"
   git remote add origin https://github.com/Louis-Mallard1/30dmc-2026-LM.git
   git push -u origin main
   ```
   Le fichier `.gitignore` exclut déjà `.venv/`, `captures/` et les documents de travail.
3. **Activer Pages** : sur GitHub, *Settings* > *Pages* > *Build and deployment* > *Source : Deploy from a branch*, branche `main`, dossier `/docs`, puis *Save*. Le site apparaît après une ou deux minutes à l'adresse `https://louis-mallard1.github.io/30dmc-2026-LM/`.
4. **Renseigner l'adresse publique** dans `edition.json`, sans barre finale :
   ```json
   "url_publique": "https://louis-mallard1.github.io/30dmc-2026-LM"
   ```
   Relancer `construire_site.bat`, puis envoyer la mise à jour :
   ```bash
   git add .
   git commit -m "Adresse publique"
   git push
   ```
   Cette adresse sert à deux choses : les **aperçus de partage** (LinkedIn, Mastodon…) qui exigent des adresses absolues, et la **page 404**, qui ne peut fonctionner sous un sous-chemin qu'avec elle.
5. **Remplir les mentions légales** avant d'annoncer le site : l'hébergeur est alors GitHub Inc. (reprendre l'adresse postale à jour indiquée dans les conditions d'utilisation de GitHub).

Après chaque nouvelle carte : double-clic sur `publier_site.bat`. Il reconstruit le site, enregistre les changements avec un message daté (« Mise à jour du site : 7 cartes sur 30 (…) ») et les envoie sur GitHub ; le site en ligne suit en une minute environ. S'il n'y a rien de nouveau, il le dit et n'envoie rien.

**Poids** : GitHub recommande de rester sous 1 Go par dépôt. La construction affiche le poids de `docs/` et avertit au-delà de 800 Mo (estimation pour 30 cartes : environ 400 Mo). Chaque nouvelle version d'un PNG HD s'ajoute à l'historique Git : mieux vaut publier les cartes une fois finalisées.

## Choix techniques

- HTML, CSS et JavaScript natifs, sans framework, sans Node, sans outil de compilation.
- Tous les chemins sont relatifs : le site fonctionne en local comme sous un sous-chemin GitHub Pages (seule la 404 a besoin de `url_publique`).
- Images en WebP (480, 960, 1080 px et HD), générées seulement si leur source a changé.
- Polices auto-hébergées (Archivo et Spectral, licence SIL OFL 1.1), aucun appel externe.
- Aucun cookie, aucune mesure d'audience.
