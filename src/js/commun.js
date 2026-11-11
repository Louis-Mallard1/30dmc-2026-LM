// Commun à toutes les pages : la flèche du nord, qui ramène en haut.
// Elle n'apparaît qu'après un écran de défilement. Sans JavaScript, c'est un
// simple lien vers le contenu, masqué par le CSS.

const nord = document.querySelector("[data-nord]");
if (nord) {
  const reduit = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let attente = false;

  const mettreAJour = () => {
    attente = false;
    nord.classList.toggle("visible", window.scrollY > window.innerHeight);
  };
  window.addEventListener("scroll", () => {
    if (!attente) { attente = true; requestAnimationFrame(mettreAJour); }
  }, { passive: true });
  mettreAJour();

  nord.addEventListener("click", (evenement) => {
    evenement.preventDefault();
    // Le focus clavier repart lui aussi du haut de la page, sans rien
    // afficher : on le pose sur la page elle-même, pas sur le lien
    // « Aller au contenu » (qui, lui, n'apparaît qu'en navigant au clavier).
    // Il est posé une fois arrivé en haut, pour ne pas gêner le défilement.
    let fait = false;
    const poserFocus = () => {
      if (fait) return;
      fait = true;
      const page = document.body;
      page.setAttribute("tabindex", "-1");
      page.focus({ preventScroll: true });
      page.addEventListener("blur", () => page.removeAttribute("tabindex"), { once: true });
    };
    window.addEventListener("scrollend", poserFocus, { once: true });
    setTimeout(poserFocus, 1500); // navigateurs sans l'événement « scrollend »
    window.scrollTo({ top: 0, behavior: reduit ? "auto" : "smooth" });
  });
}
