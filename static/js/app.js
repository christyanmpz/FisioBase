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
});