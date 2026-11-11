"""Prépare les polices du site (à lancer une fois).

Lit les TTF originaux de sources/ (dépôt officiel google/fonts, licence OFL),
les réduit aux sous-ensembles latin et latin étendu, et les convertit en
woff2 dans ce dossier. Les licences OFL sont copiées à côté.

Demande fonttools et brotli :
  .venv\\Scripts\\python.exe -m pip install fonttools brotli
  .venv\\Scripts\\python.exe src\\polices\\preparer_polices.py
"""

import shutil
import sys
from pathlib import Path

from fontTools import subset

ICI = Path(__file__).resolve().parent
SOURCES = ICI / "sources"

# Latin de base, latin-1 et latin étendu A (toutes les langues d'Europe de
# l'Ouest et centrale), quelques diacritiques isolés, ponctuation
# typographique (espaces fines, tirets, guillemets, prime, seconde), euro.
# Le latin étendu B et le vietnamien sont écartés : 50 Ko de moins à charger.
UNICODES = ("U+0000-017F,U+0192,U+0218-021B,U+02C6,U+02C7,U+02D8-02DD,"
            "U+2000-206F,U+20AC,U+2122,U+2190-2193,U+2212,U+FEFF,U+FFFD")

# Fonctions OpenType conservées : crénage, ligatures, chiffres tabulaires
# (données), chiffres proportionnels et alignés, formes de capitales.
FONCTIONS = ["kern", "liga", "tnum", "lnum", "pnum", "ccmp", "locl",
             "mark", "mkmk", "case", "rvrn"]

POLICES = {
    "Archivo[wdth,wght].ttf": "archivo-variable.woff2",
    "Spectral-LightItalic.ttf": "spectral-300-italique.woff2",
    "Spectral-Italic.ttf": "spectral-400-italique.woff2",
}
LICENCES = {"OFL_Archivo.txt": "OFL-Archivo.txt", "OFL_Spectral.txt": "OFL-Spectral.txt"}


def main() -> int:
    for source, cible in POLICES.items():
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = FONCTIONS
        options.name_IDs = ["*"]
        options.notdef_outline = True
        options.hinting = False
        police = subset.load_font(str(SOURCES / source), options)
        sousens = subset.Subsetter(options)
        sousens.populate(unicodes=subset.parse_unicodes(UNICODES))
        sousens.subset(police)
        subset.save_font(police, str(ICI / cible), options)
        print(f"  {cible} : {(ICI / cible).stat().st_size / 1000:.0f} Ko")
    for source, cible in LICENCES.items():
        shutil.copyfile(SOURCES / source, ICI / cible)
    return 0


if __name__ == "__main__":
    sys.exit(main())
