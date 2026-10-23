# Correo real en local — «¿Olvidaste tu contraseña?»

Esta guía sirve para que **el código de recuperación te llegue de verdad a tu correo** cuando pruebas
TerriIA en tu computador.

> **Es opcional.** Si no haces nada, el sistema igual funciona: el código de 6 números **sale escrito
> en la consola** donde corre `python manage.py runserver`. Para programar eso basta.

## Antes de empezar

- Tienes el proyecto corriendo según el [README](../README.md) (venv, `.env`, `migrate`).
- **Pídele a Patricio la clave de 16 letras del correo `notificacionesterriia@gmail.com` por
  mensaje privado** (WhatsApp, Discord, etc.).
- La clave **nunca** va en GitHub, en Jira ni en un chat grupal. Solo va en tu archivo `.env`,
  que Git ya ignora.

## Paso 1: ponte al día

En la terminal, dentro de la carpeta del proyecto:

```bash
git checkout develop
git pull
```

## Paso 2: abre tu archivo `.env`

Está en la carpeta raíz del proyecto, al lado de `manage.py`.

- **Windows:** `notepad .env`
- **Mac / Linux:** `nano .env`
- O ábrelo desde VS Code.

> ¿No existe? Créalo primero copiando el ejemplo: `copy .env.example .env` (Windows) o
> `cp .env.example .env` (Mac/Linux).

## Paso 3: cambia el bloque de correo

Busca las líneas que empiezan con `EMAIL_` y `DEFAULT_FROM_EMAIL` y **reemplázalas** por estas
(no las dejes repetidas):

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=notificacionesterriia@gmail.com
EMAIL_HOST_PASSWORD=CLAVE
DEFAULT_FROM_EMAIL=TerriIA <notificacionesterriia@gmail.com>
```

## Paso 4: pega la clave

1. Haz **doble clic** sobre la palabra `CLAVE` (solo esa palabra, no el `=`).
2. Pega la clave que te pasó Patricio (**Ctrl + V**).
3. Si Google la muestra en grupos (`abcd efgh ijkl mnop`), **borra los espacios**. Debe quedar
   todo junto, sin comillas:

   ```
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   ```

   (con las letras reales, no estas)

## Paso 5: guarda y cierra

**Ctrl + G** (o **Ctrl + S**) y cierra el editor.

## Paso 6: prueba que el correo sale

Activa el venv y corre esta línea, **cambiando `tu_correo@ejemplo.cl` por tu correo**:

```bash
python manage.py shell -c "from django.core.mail import send_mail; print(send_mail('Prueba TerriIA', 'Funciona el correo', None, ['tu_correo@ejemplo.cl']))"
```

- Si imprime **`1`**: funcionó. Revisa tu bandeja (y **spam / correo no deseado**).
- Si sale un error: mira la tabla de [Si algo falla](#si-algo-falla).

## Paso 7: reinicia el servidor

El servidor lee el `.env` **solo al arrancar**. Si ya estaba corriendo:

1. En su terminal presiona **Ctrl + C**.
2. Vuelve a levantarlo: `python manage.py runserver`

## Paso 8: prueba la pantalla

1. Necesitas un usuario **con tu correo real**. Si no tienes, créalo:
   `python manage.py createsuperuser` (pide email, RUT con guion y contraseña; la contraseña no se ve al escribir, es normal).
2. Abre http://127.0.0.1:8000/recuperar/
3. **Paso 1 de 3:** escribe tu correo y pulsa **Enviar código**.
4. Revisa tu correo: llega «Código para recuperar tu contraseña · TerriIA» con **6 números**.
5. **Paso 2 de 3:** escribe el código.
6. **Paso 3 de 3:** elige tu nueva contraseña.

Reglas del código (para que no te confundas al probar):

| Regla | Valor |
|---|---|
| Vigencia del código | 15 minutos |
| Intentos con un mismo código | 5 |
| Espera para pedir otro código | 60 segundos (antes de eso no se envía otro) |
| Solo vale | el último código pedido |

## Si algo falla

| Lo que ves | Qué significa | Qué hacer |
|---|---|---|
| `SMTPAuthenticationError` o «Username and Password not accepted» | La clave está mal pegada o ya no sirve | Revisa que no quedó `CLAVE`, espacios ni comillas. Si sigue, pídele la clave de nuevo a Patricio |
| `TimeoutError`, `ConnectionRefusedError` o `getaddrinfo failed` | Tu red bloquea el puerto 587 o no hay internet | Prueba con otra red (por ejemplo, los datos del celular) |
| Imprime `1` pero no ves el correo | Llegó a spam o tarda un poco | Revisa **spam / correo no deseado** y espera un minuto |
| El código aparece en la consola en vez de llegar al correo | El servidor sigue con la configuración anterior | Revisa que `EMAIL_BACKEND` diga `smtp` y **reinicia el servidor** (paso 7) |
| «Si el correo está registrado, enviamos un código de 6 dígitos.» pero no llega nada | El correo no es de un usuario **activo** (el sistema no avisa, por seguridad), o pediste otro antes de 60 s | Usa el correo exacto de tu usuario y espera un minuto antes de pedir otro |
| «El código es incorrecto o ya venció.» aunque lo copiaste bien | Venció (15 min), gastaste los 5 intentos o pediste uno más nuevo | Pide un código nuevo y usa **el último** que llegó |

## Volver al modo consola

Si ya no quieres que salgan correos reales, deja en tu `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

y reinicia el servidor. El código vuelve a salir en la consola.

## Seguridad

- El `.env` **nunca se sube** a GitHub (ya está en `.gitignore`). Antes de cada commit, revisa con
  `git status` que no aparezca.
- Si la clave se filtra (la subiste, la pegaste en un grupo, etc.), **avísale a Patricio** para que
  la revoque y genere una nueva. Después, cada uno la reemplaza en su `.env` (paso 4).
