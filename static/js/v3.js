/* TASHIL v3.0.0 — présentation uniquement : aucune API, aucun ID applicatif touché. */
(function () {
  "use strict";

  // 1) Splash : il se masque déjà tout seul en CSS ; on retire juste le nœud.
  var splash = document.getElementById("v3-splash");
  if (splash) {
    splash.addEventListener("animationend", function (e) {
      if (e.animationName === "v3-splash-out" && splash.parentNode) splash.parentNode.removeChild(splash);
    });
    setTimeout(function () { if (splash.parentNode) splash.parentNode.removeChild(splash); }, 4000);
  }

  // 2) Halo qui suit le curseur sur les cartes (variables CSS --mx / --my).
  var raf = 0, px = 0, py = 0, target = null;
  document.addEventListener("pointermove", function (e) {
    var t = e.target && e.target.closest ? e.target.closest(".card, .stat-card") : null;
    if (!t) return;
    target = t; px = e.clientX; py = e.clientY;
    if (raf) return;
    raf = requestAnimationFrame(function () {
      raf = 0;
      var r = target.getBoundingClientRect();
      target.style.setProperty("--mx", (px - r.left) + "px");
      target.style.setProperty("--my", (py - r.top) + "px");
    });
  }, { passive: true });
})();
