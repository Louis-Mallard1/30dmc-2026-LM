// Fiche : vue zoom HD et feuilletage au clavier. Module sans dépendance.
//
// Zoom : un clic (ou Entrée) sur la carte ouvre une vue plein cadre. L'image
// déjà affichée sert d'aperçu immédiat, puis la version HD la remplace dès
// qu'elle est chargée. Molette, pincement, touches + et −, glisser pour se
// déplacer ; Échap, clic sur le fond ou « Fermer » pour sortir.

const lien = document.querySelector(".fiche-carte");
const vue = document.querySelector(".zoom");
if (lien && vue && typeof vue.showModal === "function") preparerZoom(lien, vue);
preparerFeuilletage();

function preparerZoom(lien, vue) {
  const scene = vue.querySelector(".zoom-scene");
  const image = vue.querySelector(".zoom-image");
  const apercu = lien.querySelector("img");
  const urlHD = lien.dataset.zoomHd;
  const reduit = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // État : échelle et position de l'image (coin haut gauche), en pixels écran.
  let echelle = 1;
  let x = 0;
  let y = 0;
  let echelleMin = 1;
  let largeurNat = 1080; // dimensions de référence de l'image affichée
  let hauteurNat = 1350;
  const pointeurs = new Map();
  let pincement = null;
  let deplacement = null;
  let aBouge = false;

  function appliquer(anime = false) {
    image.style.transition = anime && !reduit ? "transform 180ms ease-out" : "";
    image.style.transform = `translate(${x}px, ${y}px) scale(${echelle})`;
  }

  // L'image ne peut pas sortir du cadre ; plus petite que lui, elle est centrée.
  function contraindre() {
    const L = scene.clientWidth;
    const H = scene.clientHeight;
    const l = largeurNat * echelle;
    const h = hauteurNat * echelle;
    x = l <= L ? (L - l) / 2 : Math.min(0, Math.max(L - l, x));
    y = h <= H ? (H - h) / 2 : Math.min(0, Math.max(H - h, y));
  }

  function ajuster() {
    const marge = 24;
    echelleMin = Math.min((scene.clientWidth - marge * 2) / largeurNat,
                          (scene.clientHeight - marge * 2) / hauteurNat);
    echelle = echelleMin;
    contraindre();
    appliquer();
  }

  // Zoom autour d'un point de l'écran (px, py), qui reste immobile.
  function zoomer(facteur, px, py, anime = false) {
    const max = echelleMin * 8;
    const nouvelle = Math.min(max, Math.max(echelleMin, echelle * facteur));
    const r = nouvelle / echelle;
    x = px - (px - x) * r;
    y = py - (py - y) * r;
    echelle = nouvelle;
    contraindre();
    appliquer(anime);
  }
  const centre = () => [scene.clientWidth / 2, scene.clientHeight / 2];

  function ouvrir() {
    image.src = apercu.currentSrc || apercu.src;
    largeurNat = 1080;
    hauteurNat = 1350;
    image.style.width = `${largeurNat}px`;
    image.style.height = `${hauteurNat}px`;
    vue.showModal();
    document.documentElement.style.overflow = "hidden";
    ajuster();
    // Chargement à la demande de la version HD, qui remplace l'aperçu.
    if (urlHD && image.dataset.hd !== "1") {
      const hd = new Image();
      hd.decoding = "async";
      hd.onload = () => {
        if (!vue.open) return;
        image.src = urlHD;
        image.dataset.hd = "1";
      };
      hd.src = urlHD;
    } else if (urlHD) {
      image.src = urlHD;
    }
  }

  function fermer() { if (vue.open) vue.close(); }

  vue.addEventListener("close", () => {
    document.documentElement.style.overflow = "";
    lien.focus(); // le focus revient à la carte
  });

  lien.addEventListener("click", (evenement) => {
    if (evenement.metaKey || evenement.ctrlKey || evenement.shiftKey) return;
    evenement.preventDefault();
    ouvrir();
  });

  vue.addEventListener("click", (evenement) => {
    const bouton = evenement.target.closest("button[data-zoom]");
    if (bouton) {
      const [cx, cy] = centre();
      if (bouton.dataset.zoom === "plus") zoomer(1.6, cx, cy, true);
      if (bouton.dataset.zoom === "moins") zoomer(1 / 1.6, cx, cy, true);
      if (bouton.dataset.zoom === "fermer") fermer();
      return;
    }
    // Un clic sur le fond (pas sur l'image, et sans glisser) ferme la vue.
    if (!aBouge && evenement.target !== image) fermer();
  });

  vue.addEventListener("keydown", (evenement) => {
    const [cx, cy] = centre();
    if (evenement.key === "+" || evenement.key === "=") { zoomer(1.6, cx, cy, true); evenement.preventDefault(); }
    if (evenement.key === "-" || evenement.key === "_") { zoomer(1 / 1.6, cx, cy, true); evenement.preventDefault(); }
    const pas = 80;
    const fleches = { ArrowLeft: [pas, 0], ArrowRight: [-pas, 0], ArrowUp: [0, pas], ArrowDown: [0, -pas] };
    if (fleches[evenement.key]) {
      x += fleches[evenement.key][0];
      y += fleches[evenement.key][1];
      contraindre();
      appliquer(true);
      evenement.preventDefault();
    }
  });

  scene.addEventListener("wheel", (evenement) => {
    evenement.preventDefault();
    const rect = scene.getBoundingClientRect();
    const facteur = Math.exp(-evenement.deltaY * (evenement.deltaMode === 1 ? 0.05 : 0.0018));
    zoomer(facteur, evenement.clientX - rect.left, evenement.clientY - rect.top);
  }, { passive: false });

  // Double-clic : zoom rapide sur le point visé, ou retour à la vue entière.
  scene.addEventListener("dblclick", (evenement) => {
    const rect = scene.getBoundingClientRect();
    if (echelle > echelleMin * 1.05) { echelle = echelleMin; contraindre(); appliquer(true); }
    else zoomer(3, evenement.clientX - rect.left, evenement.clientY - rect.top, true);
  });

  // Glisser pour déplacer, pincer pour zoomer (pointer events natifs).
  scene.addEventListener("pointerdown", (evenement) => {
    scene.setPointerCapture(evenement.pointerId);
    pointeurs.set(evenement.pointerId, { x: evenement.clientX, y: evenement.clientY });
    aBouge = false;
    if (pointeurs.size === 1) {
      deplacement = { x0: evenement.clientX, y0: evenement.clientY, x, y };
      scene.classList.add("glisse");
    } else if (pointeurs.size === 2) {
      const [a, b] = [...pointeurs.values()];
      pincement = { distance: Math.hypot(a.x - b.x, a.y - b.y), echelle };
      deplacement = null;
    }
  });

  scene.addEventListener("pointermove", (evenement) => {
    if (!pointeurs.has(evenement.pointerId)) return;
    pointeurs.set(evenement.pointerId, { x: evenement.clientX, y: evenement.clientY });
    if (pincement && pointeurs.size === 2) {
      const [a, b] = [...pointeurs.values()];
      const rect = scene.getBoundingClientRect();
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      const cible = pincement.echelle * (distance / pincement.distance);
      zoomer(cible / echelle, (a.x + b.x) / 2 - rect.left, (a.y + b.y) / 2 - rect.top);
      aBouge = true;
    } else if (deplacement) {
      const dx = evenement.clientX - deplacement.x0;
      const dy = evenement.clientY - deplacement.y0;
      if (Math.abs(dx) + Math.abs(dy) > 4) aBouge = true;
      x = deplacement.x + dx;
      y = deplacement.y + dy;
      contraindre();
      appliquer();
    }
  });

  function relacher(evenement) {
    pointeurs.delete(evenement.pointerId);
    if (pointeurs.size < 2) pincement = null;
    if (pointeurs.size === 0) { deplacement = null; scene.classList.remove("glisse"); }
  }
  scene.addEventListener("pointerup", relacher);
  scene.addEventListener("pointercancel", relacher);

  window.addEventListener("resize", () => { if (vue.open) ajuster(); });
}

// Flèches ← → : feuille précédente ou suivante (hors vue zoom et champs).
function preparerFeuilletage() {
  document.addEventListener("keydown", (evenement) => {
    if (evenement.defaultPrevented || evenement.altKey || evenement.ctrlKey
        || evenement.metaKey || evenement.shiftKey) return;
    if (document.querySelector("dialog[open]")) return;
    if (evenement.target.closest("input, textarea, select, [contenteditable]")) return;
    const cible = document.querySelector(`.feuilletage [data-touche="${evenement.key}"]`);
    if (cible) window.location.href = cible.href;
  });
}
