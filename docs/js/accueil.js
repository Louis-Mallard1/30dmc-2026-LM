// Accueil : la lampe qui éclaire le calque, et les coordonnées sous le curseur.
// Module sans dépendance. Si JavaScript est absent, la lampe reste au centre.

const table = document.querySelector(".table");
if (table) allumerTable(table);
const carrousel = document.querySelector(".carrousel");
if (carrousel) lancerCarrousel(carrousel);

// --- Carrousel --------------------------------------------------------------
// Défilement continu de droite à gauche, à vitesse constante (~30 px/s),
// quel que soit le nombre de cartes. La série est dupliquée autant qu'il faut
// pour couvrir au moins deux largeurs d'écran ; les copies sont inertes et
// masquées aux lecteurs d'écran, qui ne lisent chaque carte qu'une fois.
function lancerCarrousel(carrousel) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return; // rangée manuelle
  const VITESSE = 30; // px par seconde
  const piste = carrousel.querySelector(".carrousel-piste");
  const serie = piste.querySelector(".carrousel-serie");
  const bouton = carrousel.querySelector(".carrousel-pause");

  function preparer() {
    piste.querySelectorAll("[data-copie]").forEach((copie) => copie.remove());
    const ecart = parseFloat(getComputedStyle(piste).columnGap) || 0;
    const decalage = serie.getBoundingClientRect().width + ecart;
    const copies = Math.max(1, Math.ceil((2 * window.innerWidth) / decalage));
    for (let i = 0; i < copies; i += 1) {
      const copie = serie.cloneNode(true);
      copie.dataset.copie = "";
      copie.setAttribute("aria-hidden", "true");
      copie.inert = true;
      copie.querySelectorAll("a").forEach((lien) => lien.setAttribute("tabindex", "-1"));
      copie.querySelectorAll("img").forEach((image) => {
        image.removeAttribute("fetchpriority");
        image.loading = "lazy";
      });
      piste.append(copie);
    }
    piste.style.setProperty("--decalage", `${decalage}px`);
    piste.style.setProperty("--duree", `${(decalage / VITESSE).toFixed(1)}s`);
  }

  preparer();
  carrousel.classList.add("defile");
  bouton.hidden = false;
  bouton.addEventListener("click", () => {
    const enPause = carrousel.classList.toggle("en-pause");
    bouton.textContent = enPause ? "Lecture" : "Pause";
  });

  let largeur = window.innerWidth;
  let minuterie;
  window.addEventListener("resize", () => {
    if (window.innerWidth === largeur) return;
    largeur = window.innerWidth;
    clearTimeout(minuterie);
    minuterie = setTimeout(preparer, 200);
  });
}

function allumerTable(table) {
  const reduit = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const tactile = matchMedia("(hover: none)").matches;
  const zoneCoord = table.querySelector("[data-coordonnees]");
  let emprise = null;
  try { emprise = JSON.parse(table.dataset.emprise || "null"); } catch (e) { /* sans calque */ }

  // Position de la lampe, en pixels, mesurée depuis le centre de la table.
  const cible = { x: 0, y: 0 };
  const lampe = { x: 0, y: 0 };
  let largeur = table.clientWidth;
  let hauteur = table.clientHeight;
  let visible = true;
  let enCours = false;
  let debutDerive = performance.now();

  function placer() {
    table.style.setProperty("--dx", `${lampe.x.toFixed(1)}px`);
    table.style.setProperty("--dy", `${lampe.y.toFixed(1)}px`);
  }

  // Une image par rafraîchissement : la lampe rejoint la cible avec un amorti.
  function boucle(maintenant) {
    if (!visible) { enCours = false; return; }
    if (tactile) deriver(maintenant);
    lampe.x += (cible.x - lampe.x) * 0.12;
    lampe.y += (cible.y - lampe.y) * 0.12;
    placer();
    const arrivee = Math.abs(cible.x - lampe.x) < 0.3 && Math.abs(cible.y - lampe.y) < 0.3;
    if (arrivee && !tactile) { enCours = false; return; }
    requestAnimationFrame(boucle);
  }

  function relancer() {
    if (reduit || enCours || !visible) return;
    enCours = true;
    requestAnimationFrame(boucle);
  }

  // Sur écran tactile, la lampe dérive lentement d'elle-même sur le calque.
  function deriver(maintenant) {
    const t = (maintenant - debutDerive) / 1000;
    cible.x = Math.sin(t / 9) * largeur * 0.28;
    cible.y = Math.sin(t / 13 + 1) * hauteur * 0.22;
  }

  // --- Coordonnées géographiques sous le curseur ---------------------------
  // Le calque remplit la table en mode « slice » : on retrouve la position
  // dans le viewBox, puis on interpole linéairement dans l'emprise WGS84.
  function versGeo(x, y) {
    const [, , vbL, vbH] = emprise.viewbox;
    const echelle = Math.max(largeur / vbL, hauteur / vbH);
    const vx = (x - (largeur - vbL * echelle) / 2) / echelle;
    const vy = (y - (hauteur - vbH * echelle) / 2) / echelle;
    return {
      lon: emprise.ouest + (vx / vbL) * (emprise.est - emprise.ouest),
      lat: emprise.nord - (vy / vbH) * (emprise.nord - emprise.sud),
    };
  }

  function dms(valeur, positif, negatif) {
    const hemisphere = valeur >= 0 ? positif : negatif;
    let secondes = Math.round(Math.abs(valeur) * 3600);
    const degres = Math.floor(secondes / 3600);
    secondes -= degres * 3600;
    const minutes = Math.floor(secondes / 60);
    secondes -= minutes * 60;
    const deux = (n) => String(n).padStart(2, "0");
    return `${degres}° ${deux(minutes)}′ ${deux(secondes)}″ ${hemisphere}`;
  }

  function afficherCoordonnees(x, y) {
    if (!zoneCoord || !emprise) return;
    const { lon, lat } = versGeo(x, y);
    zoneCoord.textContent = `${dms(lat, "N", "S")}, ${dms(lon, "E", "O")}`;
  }

  // --- Événements ---------------------------------------------------------
  function mesurer() {
    largeur = table.clientWidth;
    hauteur = table.clientHeight;
  }

  table.addEventListener("pointermove", (evenement) => {
    if (evenement.pointerType === "touch") return;
    const rect = table.getBoundingClientRect();
    const x = evenement.clientX - rect.left;
    const y = evenement.clientY - rect.top;
    afficherCoordonnees(x, y);
    if (reduit) return; // lampe fixe au centre
    cible.x = x - largeur / 2;
    cible.y = y - hauteur / 2;
    relancer();
  });

  new ResizeObserver(mesurer).observe(table);
  new IntersectionObserver(([entree]) => {
    visible = entree.isIntersecting;
    if (visible && tactile) relancer();
  }).observe(table);
  document.addEventListener("visibilitychange", () => {
    visible = document.visibilityState === "visible";
    if (visible && tactile) relancer();
  });

  mesurer();
  afficherCoordonnees(largeur / 2, hauteur / 2);
  if (tactile) {
    // On laisse l'allumage se terminer avant la première dérive.
    const attente = document.documentElement.classList.contains("allumage") ? 1100 : 0;
    setTimeout(() => { debutDerive = performance.now(); relancer(); }, attente);
  }
}
