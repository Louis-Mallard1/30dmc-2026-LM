"""Génère le calque de Rochefort pour l'en-tête du site (à lancer une fois).

Produit, dans ce dossier :
  - calque.svg        : plan vectoriel (groupes #eau, #voirie, #fer, #bati, #toponymes),
                        sans aucun style : les couleurs sont pilotées en CSS ;
  - calque.json       : emprise en WGS84 (ouest, sud, est, nord) et en Lambert-93,
                        pour les coordonnées affichées sous le curseur ;
  - charente_axe.svg  : axe simplifié de la Charente, pour les séparateurs ;
  - calque.webp       : (option --image) le même plan en image, fond transparent.

Ce script lit 01_fonds/rochefort.gpkg en lecture seule. Il demande geopandas,
shapely et pyproj (et matplotlib pour --image) : on le lance avec le Python
système ou celui de QGIS, pas avec l'environnement .venv du site.

Usage :
  python generer_calque.py                 cadrage par défaut
  python generer_calque.py --image         ajoute la variante image
  python generer_calque.py --centre 392600 6544425 --largeur 7200
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely import affinity
from shapely.geometry import (GeometryCollection, LineString, MultiLineString,
                              MultiPolygon, Polygon, box)
from shapely.ops import linemerge, unary_union

ICI = Path(__file__).resolve().parent
DOSSIER_SITE = ICI.parent.parent

# Cadrage par défaut (Lambert-93) : le plan en damier un peu à droite et en
# haut du centre, la boucle de la Charente en entier, le port à l'est, et les
# marais à l'ouest, peu chargés, sous le titre. Format 16:9.
CENTRE_DEFAUT = (392900.0, 6544750.0)
LARGEUR_DEFAUT = 7600.0          # mètres
RAPPORT = 16 / 9
LARGEUR_SVG = 1600               # unités du viewBox

TOLERANCE = 1.5                  # simplification, en mètres
SURFACE_EAU_MIN = 150.0          # m² : on ignore les mares minuscules
SURFACE_BATI_MIN = 100.0         # m² : on ignore les annexes et garages
IMPORTANCES_VOIRIE = {"1", "2", "3", "4", "5"}   # 6 = sentiers, exclus
NATURES_VOIRIE_EXCLUES = {"Sentier", "Escalier", "Bac ou liaison maritime"}
POIDS_MAX_SVG = 300_000          # octets


def journal(message: str) -> None:
    print(f"  {message}")


# --------------------------------------------------------------------------
# Lecture
# --------------------------------------------------------------------------

def chemin_gpkg() -> Path:
    edition = json.loads((DOSSIER_SITE / "edition.json").read_text(encoding="utf-8"))
    racine = (DOSSIER_SITE / edition["racine_projet"]).resolve()
    chemin = racine / "01_fonds" / "rochefort.gpkg"
    if not chemin.exists():
        sys.exit(f"ERREUR : GeoPackage introuvable : {chemin}")
    return chemin


def lire(gpkg: Path, couche: str, emprise: Polygon, colonnes=None) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(gpkg, layer=couche, bbox=emprise.bounds, columns=colonnes)
    if gdf.crs is None or gdf.crs.to_epsg() != 2154:
        gdf = gdf.set_crs(2154, allow_override=True) if gdf.crs is None else gdf.to_crs(2154)
    gdf["geometry"] = gdf.geometry.force_2d()
    return gdf


# --------------------------------------------------------------------------
# Géométrie -> SVG
# --------------------------------------------------------------------------

class Projection:
    """Lambert-93 -> coordonnées SVG (axe des y inversé)."""

    def __init__(self, emprise: Polygon, largeur_svg: int) -> None:
        self.x0, self.y0, x1, self.y1 = emprise.bounds
        self.echelle = largeur_svg / (x1 - self.x0)
        self.largeur = largeur_svg
        self.hauteur = round((self.y1 - self.y0) * self.echelle)

    def point(self, x: float, y: float, decimales: int) -> tuple:
        px = round((x - self.x0) * self.echelle, decimales)
        py = round((self.y1 - y) * self.echelle, decimales)
        if decimales == 0:
            return int(px), int(py)
        return px, py


def nombre(v) -> str:
    """Écriture compacte : 12.0 -> 12 ; 0.5 -> .5 ; -0.5 -> -.5."""
    texte = f"{v:g}" if isinstance(v, float) else str(v)
    if texte.startswith("0."):
        texte = texte[1:]
    elif texte.startswith("-0."):
        texte = "-" + texte[2:]
    return texte


def anneau_vers_d(coords, proj: Projection, decimales: int, fermer: bool) -> str:
    """Suite de coordonnées -> commandes SVG relatives (m, l), dédoublonnées."""
    points = []
    for x, y in coords:
        p = proj.point(x, y, decimales)
        if not points or p != points[-1]:
            points.append(p)
    if fermer and len(points) > 1 and points[0] == points[-1]:
        points.pop()
    if len(points) < (3 if fermer else 2):
        return ""
    morceaux = [f"M{nombre(points[0][0])} {nombre(points[0][1])}"]
    prec = points[0]
    rel = []
    for p in points[1:]:
        dx, dy = p[0] - prec[0], p[1] - prec[1]
        if decimales:
            dx, dy = round(dx, decimales), round(dy, decimales)
        rel.append(f"{nombre(dx)}{'' if nombre(dy).startswith('-') else ' '}{nombre(dy)}")
        prec = p
    morceaux.append("l" + " ".join(rel))
    if fermer:
        morceaux.append("z")
    return "".join(morceaux)


def geom_vers_d(geom, proj: Projection, decimales: int = 1) -> str:
    if geom is None or geom.is_empty:
        return ""
    if isinstance(geom, Polygon):
        parties = [anneau_vers_d(geom.exterior.coords, proj, decimales, True)]
        parties += [anneau_vers_d(i.coords, proj, decimales, True) for i in geom.interiors]
        return "".join(p for p in parties if p)
    if isinstance(geom, LineString):
        return anneau_vers_d(geom.coords, proj, decimales, False)
    if isinstance(geom, (MultiPolygon, MultiLineString, GeometryCollection)):
        return "".join(geom_vers_d(g, proj, decimales) for g in geom.geoms)
    return ""


def preparer(gdf: gpd.GeoDataFrame, emprise: Polygon, tolerance: float):
    """Découpe à l'emprise, simplifie et fusionne en une seule géométrie."""
    if gdf.empty:
        return GeometryCollection()
    geoms = gdf.geometry.clip_by_rect(*emprise.bounds)
    geoms = geoms[~geoms.is_empty]
    return unary_union(list(geoms.simplify(tolerance, preserve_topology=True)))


# --------------------------------------------------------------------------
# La Charente
# --------------------------------------------------------------------------

def axe_charente(gpkg: Path, emprise: Polygon) -> LineString:
    """Axe de la Charente : le plus long tronçon continu dans l'emprise donnée."""
    ce = lire(gpkg, "cours_eau", emprise, ["cpx_toponyme_de_cours_d_eau"])
    ce = ce[ce["cpx_toponyme_de_cours_d_eau"].fillna("").str.lower() == "la charente"]
    if ce.empty:
        sys.exit("ERREUR : aucun tronçon « la Charente » dans cours_eau.")
    fusion = linemerge(unary_union(list(ce.geometry.clip_by_rect(*emprise.bounds))))
    lignes = list(fusion.geoms) if hasattr(fusion, "geoms") else [fusion]
    return max(lignes, key=lambda l: l.length)


def segment_etiquette(axe: LineString, longueur: float) -> LineString:
    """Portion de l'axe, de longueur donnée, la plus rectiligne et horizontale
    possible, orientée de l'ouest vers l'est, pour poser « La Charente »."""
    meilleur, score_min = None, math.inf
    pas = 50.0
    d = 0.0
    while d + longueur <= axe.length:
        morceau = substring(axe, d, d + longueur)
        (xa, ya), (xb, yb) = morceau.coords[0], morceau.coords[-1]
        corde = math.hypot(xb - xa, yb - ya)
        sinuosite = longueur / max(corde, 1)
        pente = abs(math.atan2(yb - ya, xb - xa))
        pente = min(pente, math.pi - pente)
        score = sinuosite * 3 + pente
        if score < score_min:
            meilleur, score_min = morceau, score
        d += pas
    if meilleur.coords[0][0] > meilleur.coords[-1][0]:
        meilleur = LineString(list(meilleur.coords)[::-1])
    return meilleur


def substring(ligne: LineString, debut: float, fin: float) -> LineString:
    from shapely.ops import substring as sub
    return sub(ligne, debut, fin)


# --------------------------------------------------------------------------
# Production
# --------------------------------------------------------------------------

def calculer_emprise(centre, largeur) -> Polygon:
    hauteur = largeur / RAPPORT
    cx, cy = centre
    return box(cx - largeur / 2, cy - hauteur / 2, cx + largeur / 2, cy + hauteur / 2)


def emprise_wgs84(emprise: Polygon) -> dict:
    vers_wgs84 = Transformer.from_crs(2154, 4326, always_xy=True)
    x0, y0, x1, y1 = emprise.bounds
    coins = [vers_wgs84.transform(x, y) for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
    # Moyenne des deux coins de chaque bord : à cette échelle, l'écart entre
    # le rectangle Lambert-93 et le rectangle WGS84 est de quelques mètres.
    return {
        "ouest": round((coins[0][0] + coins[1][0]) / 2, 6),
        "est": round((coins[2][0] + coins[3][0]) / 2, 6),
        "sud": round((coins[0][1] + coins[2][1]) / 2, 6),
        "nord": round((coins[1][1] + coins[3][1]) / 2, 6),
    }


def generer_svg(gpkg: Path, emprise: Polygon, avec_bati: bool):
    proj = Projection(emprise, LARGEUR_SVG)
    groupes: dict[str, str] = {}

    journal("Eau : surfaces en eau…")
    se = lire(gpkg, "surface_eau", emprise, ["nature"])
    se = se[se["nature"] != "Conduit buse"]
    se = se[se.geometry.area >= SURFACE_EAU_MIN]
    eau = preparer(se, emprise, TOLERANCE)
    groupes["eau"] = f'<path d="{geom_vers_d(eau, proj, 1)}"/>'

    journal("Voirie…")
    rt = lire(gpkg, "route", emprise, ["importance", "nature"])
    rt = rt[rt["importance"].astype(str).isin(IMPORTANCES_VOIRIE)
            & ~rt["nature"].isin(NATURES_VOIRIE_EXCLUES)]
    chemins = []
    # Deux niveaux, pour pouvoir épaissir les grands axes en CSS.
    for classe, filtre in (("principale", rt["importance"].astype(str).isin({"1", "2", "3"})),
                           ("secondaire", ~rt["importance"].astype(str).isin({"1", "2", "3"}))):
        geom = linemerge(preparer(rt[filtre], emprise, TOLERANCE)) if filtre.any() else None
        if geom is not None and not geom.is_empty:
            chemins.append(f'<path class="{classe}" d="{geom_vers_d(geom, proj, 0)}"/>')
    groupes["voirie"] = "".join(chemins)

    journal("Voie ferrée…")
    vf = lire(gpkg, "voie_ferree", emprise, ["nature"])
    fer = preparer(vf, emprise, TOLERANCE)
    groupes["fer"] = f'<path d="{geom_vers_d(linemerge(fer) if not fer.is_empty else fer, proj, 1)}"/>' \
        if not fer.is_empty else ""

    if avec_bati:
        journal("Bâti…")
        bt = lire(gpkg, "batiment", emprise, ["nature"])
        bt = bt[bt.geometry.area >= SURFACE_BATI_MIN]
        # Le bâti est fusionné en îlots, puis simplifié plus fort : c'est un fond.
        bati = preparer(bt, emprise, TOLERANCE * 2.5)
        groupes["bati"] = f'<path d="{geom_vers_d(bati, proj, 0)}"/>'

    journal("La Charente : axe et étiquette…")
    axe = axe_charente(gpkg, emprise).simplify(TOLERANCE * 4)
    etiquette = segment_etiquette(axe, 1100.0)
    d_etiquette = geom_vers_d(etiquette.simplify(15), proj, 1)

    ordre = ["eau", "bati", "voirie", "fer"]
    corps = "\n".join(f'<g id="{g}">{groupes[g]}</g>' for g in ordre if groupes.get(g))
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {proj.largeur} {proj.hauteur}" '
        f'preserveAspectRatio="xMidYMid slice">\n'
        f'<defs><path id="charente-etiquette" d="{d_etiquette}"/></defs>\n'
        f'{corps}\n'
        f'<g id="toponymes"><text class="hydro"><textPath href="#charente-etiquette" '
        f'startOffset="50%" text-anchor="middle">La Charente</textPath></text></g>\n'
        f'</svg>\n'
    )
    return svg, proj, eau, axe


def generer_axe(gpkg: Path, chemin: Path) -> None:
    """Tronçon de l'axe de la Charente utilisable comme séparateur horizontal.

    On cherche, parmi toutes les orientations, le plus long tronçon qui avance
    toujours de gauche à droite (sans revenir sur lui-même) : écrasé en hauteur
    par le CSS, il reste un trait continu, tiré de la vraie géométrie."""
    import pyogrio
    tout = box(*pyogrio.read_info(gpkg, layer="cours_eau")["total_bounds"])
    axe = axe_charente(gpkg, tout).simplify(20).segmentize(20)
    meilleur, longueur_max = None, 0.0
    for angle in range(0, 180, 3):
        coords = list(affinity.rotate(axe, angle, origin="centroid").coords)
        for suite in (coords, coords[::-1]):
            i = 0
            while i < len(suite) - 1:
                j = i
                while j + 1 < len(suite) and suite[j + 1][0] > suite[j][0]:
                    j += 1
                if j > i and suite[j][0] - suite[i][0] > longueur_max:
                    longueur_max = suite[j][0] - suite[i][0]
                    meilleur = LineString(suite[i:j + 1])
                i = j + 1
    axe = meilleur.simplify(15)
    minx, miny, maxx, maxy = axe.bounds
    largeur = 1200
    proj = Projection(box(minx, miny, maxx, maxy), largeur)
    d = geom_vers_d(axe, proj, 1)
    chemin.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {proj.largeur} {proj.hauteur}" '
        f'preserveAspectRatio="none"><path d="{d}" fill="none" stroke="currentColor" '
        f'stroke-width="1" vector-effect="non-scaling-stroke"/></svg>\n',
        encoding="utf-8")
    journal(f"charente_axe.svg : {chemin.stat().st_size / 1000:.1f} Ko "
            f"(tronçon de {axe.length / 1000:.1f} km, "
            f"proportions réelles {(maxx - minx) / (maxy - miny):.1f}:1)")


def generer_image(gpkg: Path, emprise: Polygon, chemin: Path, largeur_px: int) -> None:
    """Variante image : même plan, avec le bâti complet, fond transparent.
    Couleurs : Calque pour les traits, eau légèrement plus claire que le fond."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image

    x0, y0, x1, y1 = emprise.bounds
    hauteur_px = round(largeur_px / RAPPORT)
    dpi = 100
    fig = plt.figure(figsize=(largeur_px / dpi, hauteur_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    fig.patch.set_alpha(0)
    m_par_px = (x1 - x0) / largeur_px
    ep = lambda metres: max(metres / m_par_px * 72 / dpi, 0.35)  # mètres -> points

    se = lire(gpkg, "surface_eau", emprise, ["nature"])
    se[se.geometry.area >= SURFACE_EAU_MIN].plot(ax=ax, color="#173035", linewidth=0)
    bt = lire(gpkg, "batiment", emprise, ["nature"])
    bt.plot(ax=ax, color="#21363A", linewidth=0)
    rt = lire(gpkg, "route", emprise, ["importance", "nature"])
    rt = rt[~rt["nature"].isin(NATURES_VOIRIE_EXCLUES)]
    imp = rt["importance"].astype(str)
    rt[imp.isin({"5", "6"})].plot(ax=ax, color="#2C4448", linewidth=ep(4))
    rt[imp.isin({"3", "4"})].plot(ax=ax, color="#2C4448", linewidth=ep(7))
    rt[imp.isin({"1", "2"})].plot(ax=ax, color="#2C4448", linewidth=ep(11))
    vf = lire(gpkg, "voie_ferree", emprise, ["nature"])
    vf.plot(ax=ax, color="#2C4448", linewidth=ep(4), linestyle=(0, (4, 2)))
    png = chemin.with_suffix(".tmp.png")
    fig.savefig(png, dpi=dpi, transparent=True)
    plt.close(fig)
    with Image.open(png) as image:
        image.save(chemin, "WEBP", quality=72, method=6)
    png.unlink()
    journal(f"{chemin.name} : {largeur_px} × {hauteur_px} px, "
            f"{chemin.stat().st_size / 1000:.0f} Ko")


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parseur = argparse.ArgumentParser(description="Génère le calque de Rochefort.")
    parseur.add_argument("--centre", nargs=2, type=float, metavar=("X", "Y"),
                         default=CENTRE_DEFAUT, help="centre en Lambert-93")
    parseur.add_argument("--largeur", type=float, default=LARGEUR_DEFAUT,
                         help="largeur de l'emprise en mètres (hauteur = largeur × 9/16)")
    parseur.add_argument("--sans-bati", action="store_true", help="ne pas inclure le bâti")
    parseur.add_argument("--image", action="store_true",
                         help="produire aussi la variante image calque.webp")
    parseur.add_argument("--sortie", type=Path, default=ICI, help="dossier de sortie")
    args = parseur.parse_args()

    gpkg = chemin_gpkg()
    emprise = calculer_emprise(args.centre, args.largeur)
    sortie: Path = args.sortie
    sortie.mkdir(parents=True, exist_ok=True)
    print("Génération du calque de Rochefort")
    journal(f"Emprise Lambert-93 : {tuple(round(v) for v in emprise.bounds)}")

    svg, proj, _, _ = generer_svg(gpkg, emprise, avec_bati=not args.sans_bati)
    chemin_svg = sortie / "calque.svg"
    chemin_svg.write_text(svg, encoding="utf-8")
    poids = chemin_svg.stat().st_size
    journal(f"calque.svg : {poids / 1000:.0f} Ko (viewBox {proj.largeur} × {proj.hauteur})")
    if poids > POIDS_MAX_SVG:
        journal("ATTENTION : calque.svg dépasse 300 Ko. Essayez --sans-bati "
                "ou une emprise plus petite.")

    wgs = emprise_wgs84(emprise)
    x0, y0, x1, y1 = emprise.bounds
    donnees = {
        **wgs,
        "lambert93": {"xmin": round(x0), "ymin": round(y0), "xmax": round(x1), "ymax": round(y1)},
        "viewbox": [0, 0, proj.largeur, proj.hauteur],
        "metres_par_unite": round(1 / proj.echelle, 4),
    }
    (sortie / "calque.json").write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    journal(f"calque.json : O {wgs['ouest']}, S {wgs['sud']}, E {wgs['est']}, N {wgs['nord']}")

    generer_axe(gpkg, sortie / "charente_axe.svg")
    if args.image:
        generer_image(gpkg, emprise, sortie / "calque.webp", 2400)
    return 0


if __name__ == "__main__":
    sys.exit(main())
