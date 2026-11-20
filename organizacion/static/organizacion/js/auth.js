// Pantallas de acceso: ingresar, recuperar y cambiar contraseña (reales).
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const cookie = n => { const m = document.cookie.match('(?:^|; )' + n + '=([^;]*)'); return m ? decodeURIComponent(m[1]) : ''; };

  // ---- Ayudas de validación visual (mensaje junto al campo) ----
  function fallo(input, mensaje) {
    const campo = input.closest('.campo');
    campo.classList.add('invalido');
    campo.querySelector('.error').textContent = mensaje;
    input.setAttribute('aria-invalid', 'true');
    return false;
  }
  function limpiar(form) {
    $$('.campo.invalido', form).forEach(c => c.classList.remove('invalido'));
    $$('[aria-invalid]', form).forEach(i => i.removeAttribute('aria-invalid'));
  }
  function requeridos(form) {
    let primero = null;
    $$('[required]', form).forEach(i => {
      const vacio = i.type === 'checkbox' ? !i.checked : !i.value.trim();
      if (vacio) { fallo(i, 'Campo obligatorio'); primero = primero || i; }
    });
    if (primero) primero.focus();
    return !primero;
  }
  function claveValida(nueva, confirmar) {
    if (nueva.value.length < 8) { nueva.focus(); return fallo(nueva, 'Usa al menos 8 caracteres.'); }
    if (nueva.value !== confirmar.value) { confirmar.focus(); return fallo(confirmar, 'Las contraseñas no coinciden.'); }
    return true;
  }
  function alerta(texto) {
    const a = $('#alerta');
    if (!a) return;
    a.querySelector('span').textContent = texto;
    a.hidden = !texto;
  }

  // ---- Llamada a la API (JSON). Devuelve {ok, datos}; los errores traen {error, campo} ----
  async function api(url, cuerpo) {
    try {
      const r = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
        body: JSON.stringify(cuerpo)
      });
      const datos = await r.json().catch(() => ({}));
      if (r.status === 429) return { ok: false, datos: { error: 'Demasiados intentos. Espera un minuto e intenta de nuevo.' } };
      return { ok: r.ok, datos };
    } catch (_) {
      return { ok: false, datos: { error: 'No hay conexión con el servidor.' } };
    }
  }
  function ocupado(boton, si, texto) {
    boton.disabled = si;
    const t = boton.querySelector('span');
    if (t && texto) t.textContent = texto;
  }

  // ---- Mostrar / ocultar contraseña ----
  $$('[data-toggle-clave]').forEach(boton => boton.addEventListener('click', () => {
    const input = document.getElementById(boton.dataset.toggleClave);
    const oculta = input.type === 'password';
    input.type = oculta ? 'text' : 'password';
    boton.setAttribute('aria-label', oculta ? 'Ocultar contraseña' : 'Mostrar contraseña');
    boton.querySelector('i').className = 'bi ' + (oculta ? 'bi-eye-slash' : 'bi-eye');
  }));

  // ---- Medidor de seguridad de la contraseña ----
  const TEXTOS = ['Muy débil', 'Débil', 'Aceptable', 'Buena', 'Muy buena'];
  function nivel(c) {
    let p = 0;
    if (c.length >= 8) p++;
    if (/[a-z]/.test(c) && /[A-Z]/.test(c)) p++;
    if (/\d/.test(c)) p++;
    if (/[^A-Za-z0-9]/.test(c)) p++;
    return p;
  }
  $$('[data-medidor]').forEach(input => {
    const caja = document.getElementById(input.dataset.medidor);
    input.addEventListener('input', () => {
      const n = input.value ? nivel(input.value) : 0;
      const barra = caja.querySelector('.barra i');
      barra.style.width = (n * 25) + '%';
      barra.className = 'n' + n;
      caja.querySelector('small').textContent = input.value ? 'Seguridad: ' + TEXTOS[n] : 'Usa 8 o más caracteres, mayúsculas, números y símbolos.';
    });
  });

  // ---- Ingresar: inicia sesión de verdad con la API de core ----
  const login = $('#formLogin');
  if (login) {
    login.addEventListener('submit', async e => {
      e.preventDefault();
      limpiar(login); alerta('');
      if (!requeridos(login)) return;
      const boton = $('button[type=submit]', login), texto = boton.querySelector('span');
      boton.disabled = true; texto.textContent = 'Ingresando…';
      try {
        const r = await fetch('/api/auth/login/', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cookie('csrftoken') },
          body: JSON.stringify({ email: $('#email').value, password: $('#password').value })
        });
        const datos = await r.json().catch(() => ({}));
        if (r.ok) {
            const inicioPorRol = {
              Administrador: '/organizacion/',
              'Delegado territorial': '/territorio/territorios/',
              Funcionario: '/personas/mi-perfil/',
            };
            window.location.href = login.dataset.siguiente || inicioPorRol[datos.rol] || '/';
          return;
        }
        alerta(datos.error || 'No se pudo iniciar sesión. Intenta de nuevo.');
      } catch (_) {
        alerta('No hay conexión con el servidor.');
      }
      boton.disabled = false; texto.textContent = 'Ingresar';
    });
  }

  // ---- Cambiar contraseña (real: pide la clave actual) ----
  const cambiar = $('#formCambiar');
  if (cambiar) {
    cambiar.addEventListener('submit', async e => {
      e.preventDefault();
      limpiar(cambiar);
      if (!requeridos(cambiar)) return;
      if (!claveValida($('#claveNueva'), $('#claveNueva2'))) return;
      if ($('#claveNueva').value === $('#claveActual').value) {
        $('#claveNueva').focus();
        return fallo($('#claveNueva'), 'La nueva contraseña debe ser distinta de la actual.');
      }
      const boton = $('button[type=submit]', cambiar);
      ocupado(boton, true, 'Guardando…');
      const { ok, datos } = await api('/api/auth/cambiar-clave/', {
        actual: $('#claveActual').value, nueva: $('#claveNueva').value
      });
      ocupado(boton, false, 'Guardar contraseña');
      if (!ok) {
        const campo = { actual: '#claveActual', nueva: '#claveNueva' }[datos.campo];
        if (campo) { $(campo).focus(); return fallo($(campo), datos.error); }
        return Swal.fire({ icon: 'error', title: 'No se pudo cambiar', text: datos.error || 'Intenta de nuevo.', confirmButtonColor: '#ad0000' });
      }
      Swal.fire({
        icon: 'success', title: 'Contraseña actualizada',
        text: 'Tu nueva contraseña ya está activa.',
        confirmButtonText: 'Volver al inicio', confirmButtonColor: '#ad0000'
      }).then(() => { window.location.href = '/'; });
    });
  }

  // ---- Recuperar contraseña: correo → código de 6 dígitos → nueva contraseña (real) ----
  const flujo = $('#flujoRecuperar');
  if (flujo) {
    const celdas = $$('.codigo-celda', flujo), btnReenviar = $('#btnReenviar');
    let reloj = null, correo = '';
    const codigo = () => celdas.map(c => c.value).join('');

    function mostrar(n) {
      $$('[data-paso]', flujo).forEach(s => { s.hidden = Number(s.dataset.paso) !== n; });
      $('#indicador').hidden = n > 3;
      $('#pasoTexto').textContent = 'Paso ' + Math.min(n, 3) + ' de 3';
      $$('.pasos li', flujo).forEach((li, i) => li.classList.toggle('hecho', i < n));
      const primero = $('[data-paso]:not([hidden]) input, [data-paso]:not([hidden]) a.btn', flujo);
      if (primero) primero.focus();
    }
    function cuenta() {
      let seg = 60;
      clearInterval(reloj);
      btnReenviar.disabled = true;
      const pintar = () => { btnReenviar.textContent = seg > 0 ? 'Reenviar código en ' + seg + ' s' : 'Reenviar código'; };
      pintar();
      reloj = setInterval(() => { seg--; pintar(); if (seg <= 0) { clearInterval(reloj); btnReenviar.disabled = false; } }, 1000);
    }

    async function pedirCodigo(boton) {
      ocupado(boton, true);
      const { ok, datos } = await api('/api/auth/recuperar/solicitar/', { email: correo });
      ocupado(boton, false);
      if (!ok && datos.campo !== 'email') { alerta(datos.error || 'No se pudo enviar el código.'); return false; }
      if (!ok) { fallo($('#correoRecuperar'), datos.error); return false; }
      return true;
    }

    $('#formCorreo').addEventListener('submit', async e => {
      e.preventDefault();
      limpiar(e.target); alerta('');
      if (!requeridos(e.target)) return;
      correo = $('#correoRecuperar').value.trim().toLowerCase();
      if (!(await pedirCodigo($('button[type=submit]', e.target)))) return;
      $('#correoDestino').textContent = correo;
      celdas.forEach(c => { c.value = ''; });
      mostrar(2); cuenta();
    });

    celdas.forEach((celda, i) => {
      celda.addEventListener('input', () => {
        celda.value = celda.value.replace(/\D/g, '').slice(0, 1);
        $('#errorCodigo').textContent = '';
        if (celda.value && celdas[i + 1]) celdas[i + 1].focus();
      });
      celda.addEventListener('keydown', e => {
        if (e.key === 'Backspace' && !celda.value && celdas[i - 1]) celdas[i - 1].focus();
      });
      celda.addEventListener('paste', e => {
        e.preventDefault();
        const digitos = (e.clipboardData.getData('text') || '').replace(/\D/g, '').slice(0, 6);
        digitos.split('').forEach((d, k) => { if (celdas[k]) celdas[k].value = d; });
        (celdas[Math.min(digitos.length, 5)] || celdas[5]).focus();
      });
    });
    $('#formCodigo').addEventListener('submit', async e => {
      e.preventDefault();
      if (celdas.some(c => !c.value)) { $('#errorCodigo').textContent = 'Ingresa los 6 dígitos del código.'; return; }
      const boton = $('button[type=submit]', e.target);
      ocupado(boton, true);
      const { ok, datos } = await api('/api/auth/recuperar/verificar/', { email: correo, codigo: codigo() });
      ocupado(boton, false);
      if (!ok) { $('#errorCodigo').textContent = datos.error || 'No se pudo verificar el código.'; return; }
      mostrar(3);
    });
    btnReenviar.addEventListener('click', async () => {
      $('#errorCodigo').textContent = '';
      if (!(await pedirCodigo(btnReenviar))) return;
      celdas.forEach(c => { c.value = ''; });
      celdas[0].focus(); cuenta();
      $('#msgReenvio').textContent = 'Te enviamos un código nuevo.';
    });
    $('#cambiarCorreo').addEventListener('click', () => { clearInterval(reloj); mostrar(1); });

    $('#formNueva').addEventListener('submit', async e => {
      e.preventDefault();
      limpiar(e.target);
      if (!requeridos(e.target)) return;
      if (!claveValida($('#claveNueva'), $('#claveNueva2'))) return;
      const boton = $('button[type=submit]', e.target);
      ocupado(boton, true);
      const { ok, datos } = await api('/api/auth/recuperar/confirmar/', {
        email: correo, codigo: codigo(), password: $('#claveNueva').value
      });
      ocupado(boton, false);
      if (!ok && datos.campo === 'password') { $('#claveNueva').focus(); return fallo($('#claveNueva'), datos.error); }
      if (!ok) { mostrar(2); $('#errorCodigo').textContent = datos.error || 'No se pudo cambiar la contraseña.'; return; }
      mostrar(4);
    });
  }
})();
