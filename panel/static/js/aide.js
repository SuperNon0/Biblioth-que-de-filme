/* =========================================================================
   cinéthèque — Aide : questions fréquentes en accordéon avec recherche
   (R7). #aide/saison ouvre directement la réponse « aide-saison ».
   ========================================================================= */
"use strict";

$("#aide-q")?.addEventListener("input", (e) => {
  const q = sansAccents(e.target.value.trim());
  const faq = $("#aide-faq");
  let total = 0, groupe = null, nGroupe = 0;
  const fermerGroupe = () => { if (groupe) groupe.hidden = !nGroupe; };
  for (const el of faq.children) {
    if (el.classList.contains("faq-g")) { fermerGroupe(); groupe = el; nGroupe = 0; continue; }
    if (el.tagName !== "DETAILS") continue;
    const ok = !q || sansAccents(el.textContent).includes(q);
    el.hidden = !ok;
    // Une recherche ouvre les réponses trouvées (si elles sont peu nombreuses).
    if (q) el.open = ok && q.length > 2;
    if (ok) { total++; nGroupe++; }
  }
  fermerGroupe();
  $("#aide-rien").hidden = !!total;
  if (q && total > 4) $$("#aide-faq details[open]").forEach((d) => { d.open = false; });
});

Pages.aide = {
  afficher(sous) {
    if (!sous) return;
    const cible = document.getElementById(`aide-${sous}`);
    if (!cible) return;
    const d = cible.tagName === "DETAILS" ? cible : cible.nextElementSibling;
    if (d && d.tagName === "DETAILS") d.open = true;
    requestAnimationFrame(() => cible.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }));
  },
};
