/* Tatronics — navegación accesible y solicitud de servicio sin backend. */
(() => {
  'use strict';
  const menuButton = document.getElementById('menu-toggle');
  const menu = document.getElementById('main-menu');
  const setMenu = (isOpen) => {
    menu.classList.toggle('is-open', isOpen);
    menuButton.classList.toggle('is-open', isOpen);
    menuButton.setAttribute('aria-expanded', String(isOpen));
    menuButton.setAttribute('aria-label', isOpen ? 'Cerrar menú' : 'Abrir menú');
  };

  if (menuButton && menu) {
    menuButton.addEventListener('click', () => setMenu(!menu.classList.contains('is-open')));
    menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => setMenu(false)));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setMenu(false); });
    document.addEventListener('click', (e) => {
      if (menu.classList.contains('is-open') && !menu.contains(e.target) && !menuButton.contains(e.target)) setMenu(false);
    });
    window.matchMedia('(min-width: 1081px)').addEventListener('change', e => { if (e.matches) setMenu(false); });
  }

  const serviceSelect = document.getElementById('quote-service');
  document.querySelectorAll('[data-service]').forEach(link => {
    link.addEventListener('click', () => {
      if (serviceSelect) serviceSelect.value = link.dataset.service;
    });
  });

  const form = document.getElementById('quote-form');
  form?.addEventListener('submit', e => {
    e.preventDefault();
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    const name = String(data.get('nombre') || '').trim();
    const company = String(data.get('empresa') || '').trim();
    const service = String(data.get('servicio') || '').trim();
    const message = String(data.get('mensaje') || '').trim();
    if (!name || !service || !message) return;
    const text = [
      'Hola, Tatronics Perú. Quisiera solicitar una cotización.',
      '', `Nombre: ${name}`,
      ...(company ? [`Empresa: ${company}`] : []),
      `Servicio: ${service}`, `Detalle: ${message}`,
      '', 'Agradecería que me contacten para coordinar.'
    ].join('\n');
    const url = `https://wa.me/51963727835?text=${encodeURIComponent(text)}`;
    const opened = window.open(url, '_blank', 'noopener,noreferrer');
    if (!opened) window.location.assign(url);
  });

  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());
})();
