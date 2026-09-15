document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-password-toggle]").forEach((toggle) => {
    const input = document.getElementById(toggle.dataset.passwordToggle);
    if (!input) return;

    toggle.addEventListener("click", () => {
      const shouldShow = input.type === "password";
      input.type = shouldShow ? "text" : "password";
      toggle.textContent = shouldShow ? "Ocultar" : "Mostrar";
      toggle.setAttribute("aria-label", shouldShow ? "Ocultar senha" : "Mostrar senha");
      toggle.setAttribute("aria-pressed", String(shouldShow));
    });
  });

  // Avisos flutuantes somem sozinhos; erros ficam até o usuário sair da tela.
  const avisos = document.querySelector("[data-toast-stack]");
  if (avisos) {
    avisos.querySelectorAll(".flash").forEach((aviso) => {
      if (aviso.classList.contains("flash--error")) return;
      window.setTimeout(() => {
        aviso.classList.add("flash--saindo");
        window.setTimeout(() => aviso.remove(), 320);
      }, 4000);
    });
  }

  // O motivo só aparece quando a situação escolhida é falta justificada.
  document.querySelectorAll("[data-justificativa-de]").forEach((campo) => {
    const select = document.getElementById(campo.dataset.justificativaDe);
    if (!select) return;

    const atualizar = () => {
      const precisa = select.value === "FALTA_JUSTIFICADA";
      campo.style.display = precisa ? "" : "none";
      campo.required = precisa;
    };

    atualizar();
    select.addEventListener("change", atualizar);
  });

  // Busca dentro de um select longo: o campo filtra as opções pelo texto.
  // Sem JavaScript, o select continua completo e utilizável.
  document.querySelectorAll("[data-busca-de]").forEach((busca) => {
    const select = document.getElementById(busca.dataset.buscaDe);
    if (!select) return;

    busca.hidden = false;

    const filtrar = () => {
      const termo = busca.value.trim().toLowerCase();
      let visiveis = 0;

      Array.from(select.options).forEach((opcao) => {
        if (!opcao.value) return;
        const combina = !termo || opcao.text.toLowerCase().includes(termo);
        opcao.hidden = !combina;
        opcao.disabled = !combina;
        if (combina) visiveis += 1;
      });

      const escolhida = select.selectedOptions[0];
      if (escolhida && escolhida.hidden) select.value = "";

      busca.setAttribute(
        "aria-label",
        visiveis === 1 ? "1 resultado" : visiveis + " resultados"
      );
    };

    busca.addEventListener("input", filtrar);
    filtrar();
  });
});