// Botón "Cerrar sesión": llama a la API de core y vuelve a la pantalla de ingreso.
document.querySelectorAll('[data-cerrar-sesion]').forEach(boton => {
  boton.addEventListener('click', async () => {
    const c = document.cookie.match('(?:^|; )csrftoken=([^;]*)');
    try {
      await fetch('/api/auth/logout/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': c ? decodeURIComponent(c[1]) : '' }
      });
    } catch (_) { /* si falla la red igual se vuelve al ingreso */ }
    window.location.href = '/ingresar/';
  });
});
