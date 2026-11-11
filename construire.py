"""Générateur du site vitrine #30DayMapChallenge.

Lit la configuration (edition.json), le suivi des cartes (suivi.csv) et la
liste des thèmes (themes_AAAA.md), puis produit le site statique dans docs/ :
images WebP, téléchargements, données JSON et pages HTML.

Le script est idempotent : on peut le relancer autant de fois qu'on veut.
Les images ne sont régénérées que si leur source est plus récente.
Rien n'est jamais écrit en dehors de site_web/.

Usage : python construire.py
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------

DOSSIER_SITE = Path(__file__).resolve().parent
DOSSIER_DOCS = DOSSIER_SITE / "docs"
DOSSIER_SRC = DOSSIER_SITE / "src"
DOSSIER_GABARITS = DOSSIER_SRC / "gabarits"
DOSSIER_CONTENU = DOSSIER_SITE / "contenu"

# Couleur de fond « Charente de nuit », utilisée pour l'image de partage.
CHARENTE_DE_NUIT = (0x0F, 0x1E, 0x22)
PAPIER_CALQUE = (0xE9, 0xE6, 0xDC)
VASE = (0x93, 0xA3, 0xA4)
LAMPE = (0xF2, 0xB5, 0x44)

# Variantes d'images générées : suffixe -> (largeur, hauteur, qualité, source).
# La source « std » est le PNG 1080 × 1350, « hd » le PNG 4320 × 5400.
VARIANTES = {
    "480": (480, 600, 80, "std"),
    "960": (960, 1200, 80, "std"),
    "1350": (1080, 1350, 84, "std"),
    "hd": (4320, 5400, 85, "hd"),
}
PARTAGE = (1200, 630)

SEUIL_POIDS_DOCS = 800 * 1000 * 1000  # 800 Mo
Image.MAX_IMAGE_PIXELS = None  # les PNG HD dépassent la limite par défaut

# Fichiers de docs/ qui ne sont jamais supprimés par le nettoyage.
FICHIERS_PROTEGES = {".nojekyll", "CNAME"}


# --------------------------------------------------------------------------
# Console
# --------------------------------------------------------------------------

class Journal:
    """Collecte les avertissements pour le résumé final."""

    def __init__(self) -> None:
        self.avertissements: list[str] = []

    def info(self, message: str) -> None:
        print(f"  {message}")

    def avertir(self, message: str) -> None:
        self.avertissements.append(message)
        print(f"  ATTENTION : {message}")


journal = Journal()


class ErreurConstruction(Exception):
    """Erreur bloquante : la construction s'arrête."""


# --------------------------------------------------------------------------
# Lecture des sources
# --------------------------------------------------------------------------

def normaliser(texte: str) -> str:
    """Normalise un texte pour les comparaisons (accents composés, casse)."""
    return unicodedata.normalize("NFC", texte or "").strip().lower()


def lire_edition() -> dict:
    chemin = DOSSIER_SITE / "edition.json"
    if not chemin.exists():
        raise ErreurConstruction(f"configuration introuvable : {chemin}")
    with chemin.open(encoding="utf-8-sig") as f:
        edition = json.load(f)
    for cle in ("annee", "titre", "sous_titre", "auteur", "defi_url",
                "racine_projet", "suivi", "themes"):
        if cle not in edition:
            raise ErreurConstruction(f"clé « {cle} » absente de edition.json")
    edition["url_publique"] = (edition.get("url_publique") or "").rstrip("/")
    return edition


def chemin_projet(relatif: str) -> Path:
    """Résout un chemin de edition.json, relatif à site_web/."""
    return (DOSSIER_SITE / relatif).resolve()


def lire_themes(chemin: Path) -> list[dict]:
    """Lit le tableau Markdown | J | Thème | Consigne | Dossier |."""
    if not chemin.exists():
        raise ErreurConstruction(f"fichier des thèmes introuvable : {chemin}")
    jours: dict[int, dict] = {}
    motif = re.compile(r"^\|\s*(\d{1,2})\s*\|(.*)\|\s*$")
    for ligne in chemin.read_text(encoding="utf-8-sig").splitlines():
        m = motif.match(ligne.strip())
        if not m:
            continue
        cellules = [c.strip() for c in m.group(2).split("|")]
        if len(cellules) < 3:
            journal.avertir(f"ligne de thème incomplète ignorée : {ligne.strip()}")
            continue
        numero = int(m.group(1))
        if not 1 <= numero <= 30:
            continue
        if numero in jours:
            journal.avertir(f"jour {numero:02d} présent deux fois dans les thèmes")
            continue
        theme, consigne, dossier = cellules[0], cellules[1], cellules[2]
        jours[numero] = {
            "numero": numero,
            "theme": theme,
            "consigne": consigne,
            "dossier": dossier,
        }
    manquants = [n for n in range(1, 31) if n not in jours]
    if manquants:
        raise ErreurConstruction(
            "jours absents du fichier des thèmes : "
            + ", ".join(f"{n:02d}" for n in manquants)
        )
    return [jours[n] for n in range(1, 31)]


def lire_suivi(chemin: Path) -> dict[int, dict]:
    """Lit suivi.csv et renvoie les cartes livrées des jours 01 à 30.

    Seules les colonnes publiables sont conservées : idee, corrections,
    duree_min et tokens_* ne sont jamais lues.
    """
    if not chemin.exists():
        raise ErreurConstruction(f"suivi introuvable : {chemin}")
    colonnes_utiles = ("jour", "theme", "titre", "statut", "date", "png", "sources")
    livrees: dict[int, dict] = {}
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        absentes = [c for c in colonnes_utiles if c not in (lecteur.fieldnames or [])]
        if absentes:
            raise ErreurConstruction(
                "colonnes absentes de suivi.csv : " + ", ".join(absentes)
            )
        for ligne in lecteur:
            jour_brut = (ligne.get("jour") or "").strip()
            if not jour_brut.isdigit():
                continue
            numero = int(jour_brut)
            if not 1 <= numero <= 30:
                continue  # J00 (test) et lignes hors défi : exclus
            if normaliser(ligne.get("statut")) != "livrée":
                continue
            if numero in livrees:
                journal.avertir(f"jour {numero:02d} livré deux fois dans le suivi, "
                                "la dernière ligne est retenue")
            livrees[numero] = {c: (ligne.get(c) or "").strip() for c in colonnes_utiles}
    return livrees


# --------------------------------------------------------------------------
# Modèle des cartes
# --------------------------------------------------------------------------

@dataclass
class Carte:
    numero: int
    theme: str
    consigne: str
    dossier: str
    slug: str
    livree: bool = False
    titre: str = ""
    date: str = ""
    sources: list[str] = field(default_factory=list)
    png_std: Path | None = None
    png_hd: Path | None = None
    pdf: Path | None = None
    images: dict = field(default_factory=dict)
    telechargements: dict = field(default_factory=dict)

    @property
    def jour(self) -> str:
        return f"{self.numero:02d}"


def slug_depuis_dossier(dossier: str) -> str:
    """J05_sight -> 05-sight ; J07_10-minute -> 07-10-minute."""
    m = re.match(r"^J(\d{2})_(.+)$", dossier)
    if not m:
        raise ErreurConstruction(f"nom de dossier inattendu : « {dossier} »")
    reste = re.sub(r"[^a-z0-9-]+", "-", m.group(2).lower()).strip("-")
    return f"{m.group(1)}-{reste}"


def segment_fichier(texte: str) -> str:
    """Texte -> segment de nom de fichier sans accent ni ponctuation.

    « Senses: Sight » -> « Senses-Sight » ; « Louis MALLARD » -> « Louis-MALLARD ».
    """
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", sans_accent).strip("-")


def assembler_cartes(themes: list[dict], livrees: dict[int, dict],
                     racine_projet: Path) -> list[Carte]:
    cartes: list[Carte] = []
    for t in themes:
        carte = Carte(
            numero=t["numero"],
            theme=t["theme"],
            consigne=t["consigne"],
            dossier=t["dossier"],
            slug=slug_depuis_dossier(t["dossier"]),
        )
        ligne = livrees.get(t["numero"])
        if ligne:
            if ligne["theme"] and normaliser(ligne["theme"]) != normaliser(t["theme"]):
                journal.avertir(
                    f"#{carte.jour} : thème « {ligne['theme']} » dans le suivi, "
                    f"« {t['theme']} » dans les thèmes (ce dernier est retenu)"
                )
            dossier_export = racine_projet / t["dossier"] / "export"
            nom_std = ligne["png"] or f"{t['dossier']}_1080x1350.png"
            png_std = dossier_export / nom_std
            png_hd = dossier_export / f"{t['dossier']}_HD_4320x5400.png"
            pdf = dossier_export / f"{t['dossier']}.pdf"

            if not png_std.exists():
                journal.avertir(f"#{carte.jour} : PNG 1080 introuvable ({png_std}), "
                                "carte non publiée")
            else:
                carte.livree = True
                carte.titre = ligne["titre"]
                carte.date = ligne["date"]
                carte.sources = [s.strip() for s in ligne["sources"].split(" | ")
                                 if s.strip()]
                carte.png_std = png_std
                if png_hd.exists():
                    carte.png_hd = png_hd
                else:
                    journal.avertir(f"#{carte.jour} : PNG HD introuvable ({png_hd.name}), "
                                    "pas de zoom HD ni de téléchargement HD")
                if pdf.exists():
                    carte.pdf = pdf
                else:
                    journal.avertir(f"#{carte.jour} : PDF introuvable ({pdf.name}), "
                                    "pas de téléchargement PDF")
                if not carte.titre:
                    journal.avertir(f"#{carte.jour} : titre vide dans le suivi")
        cartes.append(carte)
    return cartes


# --------------------------------------------------------------------------
# Écriture dans docs/ (avec suivi des fichiers produits)
# --------------------------------------------------------------------------

class Sortie:
    """Mémorise chaque fichier produit, pour nettoyer ensuite les orphelins."""

    def __init__(self, racine: Path) -> None:
        self.racine = racine
        self.produits: set[Path] = set()
        self.compteurs = {"images": 0, "images_a_jour": 0, "copies": 0}

    def chemin(self, relatif: str) -> Path:
        cible = (self.racine / relatif).resolve()
        if self.racine.resolve() not in cible.parents:
            raise ErreurConstruction(f"chemin hors de docs/ refusé : {relatif}")
        cible.parent.mkdir(parents=True, exist_ok=True)
        self.produits.add(cible)
        return cible

    def ecrire_texte(self, relatif: str, contenu: str) -> None:
        cible = self.chemin(relatif)
        # On ne réécrit pas un fichier identique : les dates restent stables.
        if cible.exists() and cible.read_text(encoding="utf-8") == contenu:
            return
        cible.write_text(contenu, encoding="utf-8", newline="\n")

    def copier(self, source: Path, relatif: str) -> Path:
        cible = self.chemin(relatif)
        if a_regenerer(source, cible) or source.stat().st_size != cible.stat().st_size:
            shutil.copy2(source, cible)
            self.compteurs["copies"] += 1
        return cible


def a_regenerer(source: Path, cible: Path) -> bool:
    return not cible.exists() or cible.stat().st_mtime < source.stat().st_mtime


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------

def ouvrir_rgb(chemin: Path) -> Image.Image:
    """Ouvre une image et l'aplatit sur fond blanc si elle a de la transparence."""
    image = Image.open(chemin)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        image = image.convert("RGBA")
        fond = Image.new("RGB", image.size, (255, 255, 255))
        fond.paste(image, mask=image.getchannel("A"))
        return fond
    return image.convert("RGB")


def generer_images(carte: Carte, sortie: Sortie, police_partage: Path | None) -> None:
    sources = {"std": carte.png_std, "hd": carte.png_hd}
    ouvertes: dict[str, Image.Image] = {}

    def charger(cle: str) -> Image.Image:
        if cle not in ouvertes:
            ouvertes[cle] = ouvrir_rgb(sources[cle])
        return ouvertes[cle]

    for suffixe, (largeur, hauteur, qualite, cle_source) in VARIANTES.items():
        source = sources[cle_source]
        if source is None:
            continue
        relatif = f"img/{carte.slug}_{suffixe}.webp"
        cible = sortie.chemin(relatif)
        if a_regenerer(source, cible):
            image = charger(cle_source)
            if image.size != (largeur, hauteur):
                if abs(image.width / image.height - largeur / hauteur) > 0.01:
                    journal.avertir(f"#{carte.jour} : {source.name} n'est pas au format 4:5 "
                                    f"({image.width} × {image.height}), image recadrée")
                image = redimensionner_couvrir(image, largeur, hauteur)
            image.save(cible, "WEBP", quality=qualite, method=6)
            sortie.compteurs["images"] += 1
        else:
            sortie.compteurs["images_a_jour"] += 1
        carte.images[suffixe] = {"chemin": relatif, "largeur": largeur, "hauteur": hauteur}

    # Image de partage pour les réseaux sociaux.
    relatif = f"img/{carte.slug}_partage.jpg"
    if police_partage is None:
        cible = DOSSIER_DOCS / relatif
        if cible.exists():
            sortie.produits.add(cible.resolve())  # on garde l'ancienne
            carte.images["partage"] = {"chemin": relatif, "largeur": PARTAGE[0],
                                       "hauteur": PARTAGE[1]}
    else:
        cible = sortie.chemin(relatif)
        if (a_regenerer(carte.png_std, cible)
                or cible.stat().st_mtime < police_partage.stat().st_mtime):
            dessiner_partage(carte, charger("std"), police_partage).save(
                cible, "JPEG", quality=86, optimize=True, progressive=True)
            sortie.compteurs["images"] += 1
        else:
            sortie.compteurs["images_a_jour"] += 1
        carte.images["partage"] = {"chemin": relatif, "largeur": PARTAGE[0],
                                   "hauteur": PARTAGE[1]}

    for image in ouvertes.values():
        image.close()


def redimensionner_couvrir(image: Image.Image, largeur: int, hauteur: int) -> Image.Image:
    """Redimensionne en remplissant le cadre (recadrage centré si besoin)."""
    rapport = max(largeur / image.width, hauteur / image.height)
    taille = (round(image.width * rapport), round(image.height * rapport))
    image = image.resize(taille, Image.Resampling.LANCZOS, reducing_gap=3.0)
    gauche = (image.width - largeur) // 2
    haut = (image.height - hauteur) // 2
    return image.crop((gauche, haut, gauche + largeur, haut + hauteur))


def trouver_police_partage() -> Path | None:
    """Cherche Archivo (TTF de préférence) dans src/polices pour l'image de partage."""
    if not (DOSSIER_SRC / "polices").exists():
        return None
    candidates = sorted(
        p for p in (DOSSIER_SRC / "polices").rglob("*")
        if p.suffix.lower() in (".ttf", ".otf", ".woff2")
        and "archivo" in p.name.lower() and "italic" not in p.name.lower()
    )
    # On préfère le TTF, que Pillow lit à coup sûr.
    candidates.sort(key=lambda p: p.suffix.lower() != ".ttf")
    return candidates[0] if candidates else None


def dessiner_partage(carte: Carte, image: Image.Image, police: Path) -> Image.Image:
    """Carte centrée à gauche sur fond Charente de nuit, titre à côté en Archivo."""
    from PIL import ImageDraw, ImageFont

    largeur, hauteur = PARTAGE
    toile = Image.new("RGB", PARTAGE, CHARENTE_DE_NUIT)
    marge = 45
    h_carte = hauteur - 2 * marge
    l_carte = round(h_carte * 4 / 5)
    vignette = image.resize((l_carte, h_carte), Image.Resampling.LANCZOS, reducing_gap=3.0)
    x_carte = 110
    toile.paste(vignette, (x_carte, marge))
    dessin = ImageDraw.Draw(toile)
    # Liseré discret autour de la feuille (Papier calque à faible opacité).
    lisere = tuple(round(c * 0.12 + f * 0.88) for c, f in zip(PAPIER_CALQUE, CHARENTE_DE_NUIT))
    dessin.rectangle((x_carte - 1, marge - 1, x_carte + l_carte, marge + h_carte), outline=lisere)

    def police_variable(taille: int, largeur_axe: int, graisse: int):
        f = ImageFont.truetype(str(police), taille)
        try:
            # L'ordre des axes dépend du fichier : on le lit plutôt que le supposer.
            valeurs = {"wdth": largeur_axe, "wght": graisse}
            axes = f.get_variation_axes()
            noms = [a.get("name", b"").decode() if isinstance(a.get("name"), bytes)
                    else str(a.get("name", "")) for a in axes]
            correspondance = {"Weight": "wght", "Width": "wdth"}
            f.set_variation_by_axes([valeurs.get(correspondance.get(n, n), a["default"])
                                     for n, a in zip(noms, axes)])
        except (OSError, AttributeError, ValueError, KeyError):
            pass  # police non variable : on garde l'instance par défaut
        return f

    x_texte = x_carte + l_carte + 70
    l_texte = largeur - x_texte - 70
    f_num = police_variable(34, 125, 700)
    f_theme = police_variable(30, 110, 600)
    f_titre = police_variable(46, 115, 650)
    f_pied = police_variable(22, 100, 400)

    y = marge + 40
    dessin.text((x_texte, y), f"#{carte.jour}", font=f_num, fill=LAMPE)
    y += 56
    dessin.text((x_texte, y), carte.theme, font=f_theme, fill=VASE)
    y += 70
    for ligne in couper_lignes(dessin, carte.titre, f_titre, l_texte)[:4]:
        dessin.text((x_texte, y), ligne, font=f_titre, fill=PAPIER_CALQUE)
        y += 54
    dessin.text((x_texte, hauteur - marge - 30), "#30DayMapChallenge", font=f_pied, fill=VASE)
    return toile


def couper_lignes(dessin, texte: str, police, largeur_max: int) -> list[str]:
    lignes: list[str] = []
    courante = ""
    for mot in texte.split():
        essai = f"{courante} {mot}".strip()
        if dessin.textlength(essai, font=police) <= largeur_max or not courante:
            courante = essai
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    return lignes


# --------------------------------------------------------------------------
# Téléchargements
# --------------------------------------------------------------------------

def copier_telechargements(carte: Carte, edition: dict, sortie: Sortie) -> None:
    base_nom = "_".join([
        f"30DMC{edition['annee']}",
        carte.jour,
        segment_fichier(carte.theme),
        segment_fichier(edition["auteur"]),
    ])
    for cle, source, extension, format_ in (
        ("hd", carte.png_hd, "png", "PNG"),
        ("pdf", carte.pdf, "pdf", "PDF"),
    ):
        if source is None:
            continue
        suffixe = "_HD" if cle == "hd" else ""
        relatif = f"telechargements/{carte.slug}{suffixe}.{extension}"
        cible = sortie.copier(source, relatif)
        carte.telechargements[cle] = {
            "chemin": relatif,
            "octets": cible.stat().st_size,
            "format": format_,
            "nom": f"{base_nom}.{extension}",
        }


# --------------------------------------------------------------------------
# Fichiers statiques (CSS, JS, polices, calque)
# --------------------------------------------------------------------------

def copier_statiques(sortie: Sortie) -> None:
    # Seuls les fichiers servis au navigateur sont copiés : pas les scripts
    # de préparation ni les TTF originaux de src/polices/sources/.
    extensions = {"css": {".css"}, "js": {".js"}, "polices": {".woff2", ".txt"}}
    for dossier, permises in extensions.items():
        source = DOSSIER_SRC / dossier
        if not source.exists():
            continue
        for fichier in source.iterdir():
            if fichier.is_file() and fichier.suffix.lower() in permises:
                sortie.copier(fichier, f"{dossier}/{fichier.name}")


def ecrire_fond_calque(calque: dict | None, sortie: Sortie) -> None:
    """Version très atténuée du calque, sans bâti, pour le fond de l'atlas et
    des fiches. Les couleurs sont intégrées : le fichier sert d'image de fond."""
    if not calque:
        return
    plan = re.sub(r'<g id="bati">.*?</g>', "", calque["plan"], flags=re.S)
    plan = re.sub(r'<g id="toponymes">.*?</g>', "", plan, flags=re.S)
    style = (
        "<style>"
        "#eau path{fill:#112226}"
        "#voirie path,#fer path{fill:none;stroke:#182C30;stroke-width:.9;"
        "stroke-linecap:round;stroke-linejoin:round}"
        "#voirie .principale{stroke-width:1.8}#fer path{stroke-dasharray:4 2.5}"
        "</style>"
    )
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{calque["viewbox"]}" '
           f'preserveAspectRatio="xMidYMid slice">{style}{plan}</svg>\n')
    sortie.ecrire_texte("calque/fond.svg", svg)


# --------------------------------------------------------------------------
# Données publiques
# --------------------------------------------------------------------------

def carte_vers_dict(carte: Carte) -> dict:
    """Entrée de cartes.json : uniquement des informations publiables."""
    donnees = {
        "jour": carte.jour,
        "theme": carte.theme,
        "consigne": carte.consigne,
        "slug": carte.slug,
        "etat": "livree" if carte.livree else "a_venir",
    }
    if carte.livree:
        donnees.update({
            "titre": carte.titre,
            "sources": carte.sources,
            "date": carte.date,
            "page": f"carte/{carte.slug}/",
            "images": carte.images,
            "telechargements": carte.telechargements,
        })
    return donnees


# --------------------------------------------------------------------------
# Pages HTML (gabarits Jinja2)
# --------------------------------------------------------------------------

def lire_calque(edition: dict) -> dict | None:
    """Prépare le calque pour l'insertion dans les pages.

    Le contenu du SVG est placé une seule fois dans la page (dans <defs>),
    puis réutilisé par <use> pour la couche sombre et la couche éclairée."""
    chemin = DOSSIER_SITE / edition.get("calque", "src/calque/calque.svg")
    chemin_json = chemin.with_suffix(".json")
    if not chemin.exists() or not chemin_json.exists():
        journal.avertir("calque introuvable : lancez src/calque/generer_calque.py")
        return None
    svg = chemin.read_text(encoding="utf-8")
    m = re.search(r"<svg[^>]*viewBox=\"([^\"]+)\"[^>]*>(.*)</svg>", svg, re.S)
    if not m:
        raise ErreurConstruction(f"calque illisible : {chemin}")
    interieur = m.group(2)
    # Les définitions (chemin de l'étiquette) sortent du groupe réutilisé.
    defs = "".join(re.findall(r"<defs>(.*?)</defs>", interieur, re.S))
    interieur = re.sub(r"<defs>.*?</defs>", "", interieur, flags=re.S).strip()
    emprise = json.loads(chemin_json.read_text(encoding="utf-8"))
    axe = None
    chemin_axe = chemin.parent / "charente_axe.svg"
    if chemin_axe.exists():
        texte = chemin_axe.read_text(encoding="utf-8")
        ma = re.search(r'viewBox="([^"]+)".*?<path d="([^"]+)"', texte, re.S)
        if ma:
            # Position verticale de l'extrémité droite du tracé (0 = haut, 1 = bas),
            # pour y raccorder le filet du séparateur.
            nombres = [float(n) for n in re.findall(r"-?\d*\.?\d+", ma.group(2))]
            y_fin = nombres[1] + sum(nombres[3::2])
            hauteur = float(ma.group(1).split()[3])
            axe = {"viewbox": ma.group(1), "d": ma.group(2),
                   "fin": round(min(max(y_fin / hauteur, 0), 1), 3),
                   "rapport": round(float(ma.group(1).split()[2]) / hauteur, 3)}
    return {"viewbox": m.group(1), "defs": defs, "plan": interieur,
            "emprise": emprise, "axe": axe}


def accord_cartes(n: int) -> str:
    """« 1 carte sur 30 », « 6 cartes sur 30 »."""
    return f"{n} carte" if n <= 1 else f"{n} cartes"


def taille_fr(octets: int) -> str:
    """Taille en français, base 1000 : 862 Ko ; 11,8 Mo ; 24 Mo."""
    if octets < 1000 * 1000:
        return f"{max(1, round(octets / 1000))} Ko"
    mo = octets / 1000 / 1000
    texte = f"{mo:.0f}" if mo >= 20 else f"{mo:.1f}"
    return texte.replace(".", ",") + " Mo"


def rendre_pages(edition: dict, cartes: list[Carte], sortie: Sortie) -> int:
    """Rend les gabarits présents. Un gabarit absent est simplement ignoré
    (le site se construit lot par lot)."""
    if not DOSSIER_GABARITS.exists() or not any(DOSSIER_GABARITS.glob("*.html")):
        journal.info("Aucun gabarit pour l'instant : pages HTML non générées.")
        return 0

    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

    env = Environment(
        loader=FileSystemLoader(DOSSIER_GABARITS),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["taille"] = taille_fr
    env.filters["cartes"] = accord_cartes

    livrees = [c for c in cartes if c.livree]
    donnees = [carte_vers_dict(c) for c in cartes]
    donnees_livrees = [d for d in donnees if d["etat"] == "livree"]
    commun = {
        "calque": lire_calque(edition),
        "edition": edition,
        "cartes": donnees,
        "livrees": donnees_livrees,
        "nb_livrees": len(livrees),
        "nb_jours": len(cartes),
    }
    nb_pages = 0

    def rendre(gabarit: str, destination: str, profondeur: int, **contexte) -> None:
        nonlocal nb_pages
        if not (DOSSIER_GABARITS / gabarit).exists():
            return
        racine = "../" * profondeur or "./"
        html = env.get_template(gabarit).render(
            **commun, racine=racine, chemin_page=destination, **contexte)
        sortie.ecrire_texte(destination, html)
        nb_pages += 1

    rendre("accueil.html", "index.html", 0, page="accueil")
    rendre("atlas.html", "atlas/index.html", 1, page="atlas")
    for i, carte in enumerate(donnees_livrees):
        rendre("fiche.html", f"carte/{carte['slug']}/index.html", 2, page="fiche",
               carte=carte,
               precedente=donnees_livrees[i - 1] if i > 0 else None,
               suivante=donnees_livrees[i + 1] if i + 1 < len(donnees_livrees) else None)
    for nom in ("a-propos", "mentions-legales"):
        source = DOSSIER_CONTENU / f"{nom}.md"
        if source.exists():
            import markdown
            texte = source.read_text(encoding="utf-8-sig")
            html = markdown.markdown(texte, extensions=["extra", "smarty"],
                                     output_format="html")
            m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            titre_page = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else nom
            if not m:
                journal.avertir(f"contenu/{nom}.md n'a pas de titre « # … »")
            rendre("page.html", f"{nom}/index.html", 1, page=nom,
                   contenu=html, titre_page=titre_page)

    # La 404 est servie à n'importe quelle profondeur d'adresse : ses liens
    # sont absolus (adresse publique si connue, sinon racine du domaine) et
    # ses styles sont intégrés à la page.
    if (DOSSIER_GABARITS / "404.html").exists():
        base_404 = (edition["url_publique"] + "/") if edition["url_publique"] else "/"
        css = (DOSSIER_SRC / "css" / "site.css").read_text(encoding="utf-8-sig")
        css = css.replace("../polices/", base_404 + "polices/")
        css = css.replace("../calque/", base_404 + "calque/")
        html = env.get_template("404.html").render(
            **commun, racine=base_404, chemin_page="404.html", page="404",
            css_en_ligne=css)
        sortie.ecrire_texte("404.html", html)
        nb_pages += 1
    return nb_pages


# --------------------------------------------------------------------------
# Nettoyage et résumé
# --------------------------------------------------------------------------

def nettoyer_orphelins(sortie: Sortie) -> int:
    racine = sortie.racine.resolve()
    supprimes = 0
    for fichier in sorted(racine.rglob("*"), reverse=True):
        if fichier.is_file():
            if fichier.name in FICHIERS_PROTEGES and fichier.parent == racine:
                continue
            if fichier.resolve() not in sortie.produits:
                fichier.unlink()
                supprimes += 1
        elif fichier.is_dir() and not any(fichier.iterdir()):
            fichier.rmdir()
    return supprimes


def poids_dossier(dossier: Path) -> int:
    return sum(f.stat().st_size for f in dossier.rglob("*") if f.is_file())


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------

def construire() -> int:
    print("Construction du site #30DayMapChallenge")
    print("\n1. Lecture des sources")
    edition = lire_edition()
    racine_projet = chemin_projet(edition["racine_projet"])
    themes = lire_themes(chemin_projet(edition["themes"]))
    livrees = lire_suivi(chemin_projet(edition["suivi"]))
    cartes = assembler_cartes(themes, livrees, racine_projet)
    publiees = [c for c in cartes if c.livree]
    journal.info(f"Édition {edition['annee']} : {len(cartes)} jours, "
                 f"{len(publiees)} cartes livrées.")

    DOSSIER_DOCS.mkdir(exist_ok=True)
    sortie = Sortie(DOSSIER_DOCS)

    print("\n2. Images et téléchargements")
    police = trouver_police_partage()
    if police is None and publiees:
        journal.info("Police Archivo absente de src/polices : "
                     "images de partage non générées pour l'instant.")
    for carte in publiees:
        generer_images(carte, sortie, police)
        copier_telechargements(carte, edition, sortie)
        journal.info(f"#{carte.jour} {carte.theme} : prête")
    journal.info(f"Images générées : {sortie.compteurs['images']}, "
                 f"déjà à jour : {sortie.compteurs['images_a_jour']}.")

    print("\n3. Fichiers statiques et données")
    copier_statiques(sortie)
    ecrire_fond_calque(lire_calque(edition), sortie)
    # Favicon : un segment d'échelle ambre et un segment vide, cerclés.
    sortie.ecrire_texte("favicon.svg", (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="3" fill="#0F1E22"/>'
        '<rect x="4.5" y="11.5" width="23" height="9" fill="none" stroke="#E9E6DC"/>'
        '<rect x="5" y="12" width="11" height="8" fill="#F2B544"/>'
        '</svg>\n'))
    sortie.ecrire_texte(".nojekyll", "")
    donnees = {
        "annee": edition["annee"],
        "titre": edition["titre"],
        "nb_livrees": len(publiees),
        "nb_jours": len(cartes),
        "cartes": [carte_vers_dict(c) for c in cartes],
    }
    sortie.ecrire_texte("donnees/cartes.json",
                        json.dumps(donnees, ensure_ascii=False, indent=2) + "\n")
    journal.info("donnees/cartes.json écrit.")

    print("\n4. Pages")
    nb_pages = rendre_pages(edition, cartes, sortie)
    if nb_pages:
        journal.info(f"{nb_pages} page(s) rendue(s).")

    print("\n5. Nettoyage")
    supprimes = nettoyer_orphelins(sortie)
    journal.info(f"{supprimes} fichier(s) orphelin(s) supprimé(s).")

    poids = poids_dossier(DOSSIER_DOCS)
    print("\nRésumé")
    print(f"  Cartes publiées : {len(publiees)} sur {len(cartes)} "
          f"({', '.join('#' + c.jour for c in publiees) or 'aucune'})")
    print(f"  Fichiers copiés : {sortie.compteurs['copies']}")
    print(f"  Poids de docs/ : {taille_fr(poids)}")
    if poids > SEUIL_POIDS_DOCS:
        journal.avertir("docs/ dépasse 800 Mo (limite recommandée par GitHub Pages : 1 Go)")
    if journal.avertissements:
        print(f"  Avertissements : {len(journal.avertissements)}")
        for message in journal.avertissements:
            print(f"   - {message}")
    else:
        print("  Avertissements : aucun")
    return 0


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        return construire()
    except ErreurConstruction as erreur:
        print(f"\nERREUR : {erreur}")
        print("La construction est interrompue.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
