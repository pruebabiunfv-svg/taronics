'use strict';
document.querySelectorAll('[data-password-toggle]').forEach(button => {
  button.addEventListener('click', () => {
    const target = document.getElementById(button.dataset.passwordToggle);
    if (!target) return;
    const showing = target.type === 'password';
    target.type = showing ? 'text' : 'password';
    button.textContent = showing ? 'Ocultar' : 'Mostrar';
    button.setAttribute('aria-pressed', String(showing));
    button.setAttribute('aria-label', showing ? 'Ocultar contraseña' : 'Mostrar contraseña');
  });
});
