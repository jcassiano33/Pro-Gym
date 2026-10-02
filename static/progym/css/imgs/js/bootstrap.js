// Navegação entre telas do Pro Gym.
// O Bootstrap (bootstrap.bundle.min.js) é carregado antes, no base.html,
// e cuida do menu lateral (offcanvas). Aqui só trocamos de tela.

document.addEventListener("DOMContentLoaded", () => {
  const telas = document.querySelectorAll(".pg-tela");
  const menu = document.getElementById("menuLateral");

  function mostrarTela(nome) {
    telas.forEach((t) => { t.hidden = t.id !== "tela-" + nome; });
    window.scrollTo(0, 0);
  }

  // Qualquer elemento com data-tela="nome" leva para a tela correspondente
  document.querySelectorAll("[data-tela]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      mostrarTela(el.dataset.tela);

      // Fecha o menu lateral se estiver aberto
      const aberto = bootstrap.Offcanvas.getInstance(menu);
      if (aberto) aberto.hide();
    });
  });

  mostrarTela("inicio");
});