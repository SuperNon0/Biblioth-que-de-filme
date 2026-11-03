/* =========================================================================
   cinéthèque — page Comptes / Profils : valider, refuser, bloquer,
   supprimer un compte, « voir en tant que ». Confirmations intégrées (V6),
   jamais de confirm() ni d'alert() du navigateur.
   ========================================================================= */
"use strict";

Couches.init();

const ROUTES_COMPTES = {
  valider: (id) => ["POST", `/api/comptes/${id}/valider`],
  refuser: (id) => ["POST", `/api/comptes/${id}/refuser`],
  bloquer: (id) => ["POST", `/api/comptes/${id}/bloquer`],
  debloquer: (id) => ["POST", `/api/comptes/${id}/debloquer`],
  supprimer: (id) => ["DELETE", `/api/comptes/${id}`],
  impersonate: (id) => ["POST", `/api/comptes/${id}/impersonate`],
  promouvoir: (id) => ["POST", `/api/comptes/${id}/role`, { role: "super_admin" }],
};

/* Les actions lourdes demandent confirmation ; {m} = l'adresse du compte. */
const CONFIRMATIONS = {
  refuser: { titre: "Refuser la demande", message: "Refuser l'accès à {m} ?", ok: "Refuser", danger: true },
  bloquer: { titre: "Bloquer le compte", message: "{m} ne pourra plus se connecter tant que tu ne le débloques pas. Ses données sont gardées.", ok: "Bloquer", danger: true },
  promouvoir: { titre: "Rôle super-admin", message: "{m} pourra tout gérer sur le site, comme toi.", ok: "Donner le rôle" },
  supprimer: { titre: "Supprimer le compte", message: "Supprimer {m} et toutes ses données (bibliothèque, listes, journal) ?", detail: "Action définitive : rien ne peut être récupéré.", ok: "Supprimer", danger: true },
};

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const row = btn.closest(".acct-row");
  const act = btn.dataset.act;
  const route = ROUTES_COMPTES[act];
  if (!row || !route) return;
  const conf = CONFIRMATIONS[act];
  if (conf && !(await confirmer(conf.message.replace("{m}", row.dataset.mail || "ce compte"), conf))) return;
  await occupe(btn, async () => {
    const [method, url, body] = route(row.dataset.id);
    try {
      await api(url, { method, body });
    } catch (err) { toastErr(err); return; }
    if (act === "impersonate") {
      // La page « / » gardée par le service worker est celle de TON compte.
      await purgeShell();
      location.href = "/";
      return;
    }
    location.reload();
  });
});
