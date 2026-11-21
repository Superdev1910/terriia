# Incidencias de configuración

Problemas de entorno que ya ocurrieron y cómo se resolvieron, para no repetirlos.

| Fecha | Entorno | Problema | Causa | Solución |
|---|---|---|---|---|
| (fecha a completar) | Local y servidor | Los códigos de «¿Olvidaste tu contraseña?» nunca llegaban por correo: solo aparecían en el log o la consola. | Faltaba `EMAIL_BACKEND` en el `.env`; Django usaba el backend de consola (`django.core.mail.backends.console.EmailBackend`), que imprime el mensaje en vez de enviarlo. | En el servidor definir `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` y los datos SMTP (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`). En local es opcional ([LEEME-correo.md](LEEME-correo.md)). Ya está documentado en `.env.example`. |
| (fecha a completar) | PythonAnywhere | El sitio no arrancaba: error en el archivo WSGI de la aplicación web. | Sangría (indentación) incorrecta al editar el archivo WSGI en el panel de PythonAnywhere (Python no admite mezclar o desalinear la sangría). | Corregir la sangría (usar 4 espacios, sin tabuladores, todo el bloque alineado a la izquierda salvo lo que va dentro de `if`) y pulsar **Reload** en la pestaña *Web*; revisar el *error log* si persiste. |
| (fecha a completar) | AWS Academy (lab) | La instancia dejaba de responder al terminar la sesión del lab: el sitio no estaba disponible al día siguiente. | El lab de AWS Academy detiene los recursos cuando termina la sesión; la instancia EC2 se apaga y, al reiniciarla, puede cambiar su IP pública. | Iniciar el lab y encender la instancia antes de usar el sitio; comprobar la IP pública nueva y actualizar `DJANGO_ALLOWED_HOSTS` / `DJANGO_CSRF_TRUSTED_ORIGINS` si el sitio se accede por IP; verificar que `gunicorn` y `nginx` estén activos (`systemctl status`). Para una disponibilidad estable se necesita un servidor que no dependa del lab. |

Al agregar una incidencia nueva, completa las cinco columnas con la fecha real.
