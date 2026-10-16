// Pro Gym - pequenos recursos de interface (o Bootstrap é carregado antes, no base.html).

document.addEventListener("DOMContentLoaded", () => {
  // ---- Máscaras de CPF e telefone (campos com data-mask) ----
  const mascaras = {
    cpf(v) {
      v = v.replace(/\D/g, "").slice(0, 11);
      return v
        .replace(/(\d{3})(\d)/, "$1.$2")
        .replace(/(\d{3})(\d)/, "$1.$2")
        .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
    },
    telefone(v) {
      v = v.replace(/\D/g, "").slice(0, 11);
      if (v.length > 10) return v.replace(/(\d{2})(\d{5})(\d{0,4})/, "($1) $2-$3");
      if (v.length > 6) return v.replace(/(\d{2})(\d{4})(\d{0,4})/, "($1) $2-$3");
      if (v.length > 2) return v.replace(/(\d{2})(\d{0,5})/, "($1) $2");
      return v;
    },
  };

  document.querySelectorAll("input[data-mask]").forEach((campo) => {
    const aplicar = mascaras[campo.dataset.mask];
    if (!aplicar) return;
    campo.value = aplicar(campo.value);
    campo.addEventListener("input", () => {
      campo.value = aplicar(campo.value);
    });
  });

  // ---- Mensagens de sucesso somem sozinhas ----
  document.querySelectorAll(".alert-success.alert-dismissible").forEach((alerta) => {
    setTimeout(() => {
      if (window.bootstrap) bootstrap.Alert.getOrCreateInstance(alerta).close();
    }, 6000);
  });
});
