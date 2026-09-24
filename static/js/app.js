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
  //
  // Eram 4 segundos, curtos demais para mensagens com números — a da
  // inscrição no grupo diz quantos encontros e quantas sessões o paciente
  // recebeu. Agora: 10 segundos, o relógio para enquanto o mouse está em
  // cima ou o teclado está dentro do aviso, e há um botão para fechar na
  // hora.
  const TEMPO_DO_AVISO = 10000;
  const avisos = document.querySelector("[data-toast-stack]");
  if (avisos) {
    avisos.querySelectorAll(".flash").forEach((aviso) => {
      const fechar = document.createElement("button");
      fechar.type = "button";
      fechar.className = "flash-fechar";
      fechar.setAttribute("aria-label", "Fechar aviso");
      fechar.textContent = "×";

      const sair = () => {
        aviso.classList.add("flash--saindo");
        window.setTimeout(() => aviso.remove(), 320);
      };

      fechar.addEventListener("click", sair);
      aviso.appendChild(fechar);

      // Erro fica na tela até ser fechado no botão.
      if (aviso.classList.contains("flash--error")) return;

      let relogio = window.setTimeout(sair, TEMPO_DO_AVISO);
      const segurar = () => window.clearTimeout(relogio);
      const soltar = () => {
        window.clearTimeout(relogio);
        relogio = window.setTimeout(sair, TEMPO_DO_AVISO);
      };

      aviso.addEventListener("mouseenter", segurar);
      aviso.addEventListener("focusin", segurar);
      aviso.addEventListener("mouseleave", soltar);
      aviso.addEventListener("focusout", soltar);
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

  // Caixa única de busca: o usuário digita e escolhe na lista de sugestões.
  // O campo escondido guarda o id; sem JavaScript, o select continua visível.
  document.querySelectorAll("[data-autocomplete]").forEach((caixa) => {
    const destino = document.getElementById(caixa.dataset.autocomplete);
    const select = document.getElementById(caixa.dataset.selectOriginal);
    if (!destino || !select) return;

    const campo = caixa.closest(".field") || caixa.parentElement;
    const aviso = campo.querySelector("[data-autocomplete-aviso]");
    select.hidden = true;
    select.removeAttribute("required");
    caixa.hidden = false;

    const porTexto = new Map();
    Array.from(select.options).forEach((opcao) => {
      if (opcao.value) porTexto.set(opcao.text.trim(), opcao.value);
    });

    const resolver = () => {
      const id = porTexto.get(caixa.value.trim()) || "";
      const mudou = destino.value !== id;
      destino.value = id;
      if (aviso) {
        aviso.hidden = !caixa.value.trim() || Boolean(id);
      }
      caixa.setCustomValidity(
        !caixa.value.trim() || id ? "" : "Escolha um nome da lista."
      );
      if (mudou) destino.dispatchEvent(new Event("change", { bubbles: true }));
    };

    caixa.addEventListener("input", resolver);
    caixa.addEventListener("change", resolver);
    resolver();
  });
});