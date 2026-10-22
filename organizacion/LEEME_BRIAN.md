# Parte de Brian · app `organizacion` (SCRUM-13 · HU17)

Mantenedores: **delegación**, **área** y **cargo**, con su interfaz (diseño municipal),
pruebas unitarias y pruebas de integración / funcionales.

## Cómo usarlo
1. Copia la carpeta `organizacion/` sobre la de tu repo y, en `config/urls.py`, **agrega** estas 3 líneas
   dentro de `urlpatterns` (no reemplaces el archivo entero: otros integrantes pueden haber agregado las suyas):
   ```python
   path("api/", include("organizacion.urls")),
   path("organizacion/", include("organizacion.urls_pantallas")),
   path("", include("organizacion.urls_publico")),  # sitio público + acceso
   ```
2. `python manage.py migrate` (la migración `0001_initial` ya viene hecha).
3. `black .` y `python manage.py test organizacion` antes de hacer commit.
4. Abre http://127.0.0.1:8000/ (sitio público) o entra con un usuario Administrador a http://127.0.0.1:8000/organizacion/ (panel)

## Campos respecto del SQL v2.3
- `delegacion`: `nombre`, `ambito` y `estado` como en el SQL; **extras** `codigo`, `direccion`, `comuna` (directorio y pantallas).
- `area`: `nombre` (ENUM de 4 valores) y `prioridad` como en el SQL; **extra** `estado` (para desactivar en vez de borrar).
- `cargo`: como en el SQL; **extra** `descripcion`.
- Los extras quedan documentados en el modelo físico v2.4 (delta).
- Directorio público: sin nombres de funcionarios (solo cargo y teléfono de oficina), por la ley de datos personales.

## Rutas
| Qué | URL |
|---|---|
| Pantallas | `/organizacion/`, `/organizacion/delegaciones/`, `/organizacion/areas/`, `/organizacion/cargos/` |
| API | `/api/delegaciones/`, `/api/areas/`, `/api/cargos/` |
| API extra | `/api/delegaciones/<id>/detalle/` (áreas y cargos), `/api/organizacion/resumen/` (cifras del inicio) |
| Parámetros de listado | `search`, filtros, `page`, `page_size` (10/20/50; máx. 100), `ordering` (ej. `-nombre`) |

## Reglas implementadas
- delegación: código y nombre únicos (sin distinguir mayúsculas); al crearla nacen sus 4 áreas.
- área: las 4 del cliente (Social, DISERCO, Seguridad y Organización Comunitaria; campo `nombre` como en el SQL v2.3), una de cada una por delegación; prioridad 1 a 4 sin repetir dentro de la delegación. Como las 4 áreas nacen
  con las 4 prioridades, **cambiar una prioridad a una ya usada las intercambia** (la otra área recibe la
  prioridad anterior, en una sola transacción y con auditoría de las dos). Al crear un área o moverla a otra
  delegación, una prioridad repetida se rechaza.
- cargo: sin área = transversal; vigente / no vigente; nombre único dentro del área.
- Nunca se borra: DELETE desactiva. Solo Administrador (validado en el servidor). Auditoría automática.
- **Desactivar en cadena (CAT-06):** al desactivar una delegación se desactivan sus áreas y los cargos de
  esas áreas; al desactivar un área, sus cargos quedan no vigentes. La pantalla avisa cuántos registros se
  afectan antes de confirmar y cada registro arrastrado queda en auditoría. Los cargos transversales no se
  tocan. **Reactivar no reactiva a los dependientes**: se reactivan en orden (delegación → área → cargo).
- **Relaciones inactivas (CAT-05):** no se crea un área en una delegación inactiva ni un cargo en un área
  inactiva (o de delegación inactiva); tampoco se activa un área con su delegación inactiva ni se marca
  vigente un cargo con su área inactiva. Se valida en el servidor, con mensaje junto al campo.

## Pantalla
Ordenar por columna (clic en el encabezado), selector de 10/20/50 filas, texto buscado resaltado, atajo `/`
para ir al buscador, panel lateral con las 4 áreas y los cargos de cada delegación (con enlaces a sus cargos
y a «Nuevo cargo» con el área ya elegida), estado vacío con botón de acción, foco atrapado y devuelto al
cerrar formularios y panel (UX-05) e inicio con cifras reales. SweetAlert2 y los iconos van con versión fija.

## Pruebas
- `test_cascada.py`: desactivación en cadena, auditoría de lo arrastrado y relaciones inactivas (CAT-05/06).
- `test_listados.py`: tamaño de página, orden, detalle, resumen y consultas por listado (UX-02/03, REN-01).
- `test_delegacion.py`, `test_area.py`, `test_cargo.py`: unitarias (crear, editar, duplicado/inválido, desactivar, acceso denegado, listado). `test_area.py` incluye el intercambio de prioridades.
- `test_integracion.py`: flujo delegación → áreas → cargo, desactivación en cadena, auditoría, seguridad.
- `test_pantallas.py`: pruebas funcionales de cada pantalla (HTML, controles y versiones de librerías).
- `test_publico.py`: sitio público y pantallas de acceso.

## Límites conocidos
- La unicidad del cargo transversal y del nombre sin distinguir mayúsculas se valida en el servidor, no en
  la base: MySQL/MariaDB no permiten esa restricción sin agregar columnas fuera del modelo v2.3.
- Las pruebas de pantalla (`test_pantallas.py`) revisan el HTML y los controles, no el comportamiento del
  JavaScript. El comportamiento (ordenar, paginar, buscar, panel, foco, desactivar en cadena, exportar a
  Excel) se verificó a mano en el navegador; no hay pruebas automáticas en navegador ni pruebas de estrés.

## Pendiente / por confirmar
- Escudo oficial: confirmar que `static/organizacion/img/escudo.png` es el archivo oficial (sin deformarlo ni recolorearlo).
- Login común y plantilla base compartida son de `core` (Patricio): cuando exista, mover `base.html` y `terriia.css` a `core`.
- Cabecera: muestra "Acceso global" hasta que `usuario.delegacion` exista (HU19).
- Prueba `test_delegacion_cargo_funcionario_usuario` (INT-ORG-09) está en *skip* hasta que existan funcionario y usuario.delegacion (Patricio y Fernando). Al activarla hay que escribir su cuerpo: hoy solo tiene `pass`.

## Sitio público y pantallas de acceso (visual)

Menú de la Municipalidad (Inicio, Delegaciones, Servicios, Contacto) más las pantallas de acceso,
en rojo institucional y blanco. Código en `publico.py`, `urls_publico.py` y las plantillas `publico_base.html`,
`portada.html`, `directorio.html`, `servicios.html`, `contacto.html`, `auth_base.html`, `ingresar.html`,
`recuperar.html` y `cambiar_clave.html`; estilos en `css/publico.css`; scripts en `js/auth.js`
y `js/sesion.js`; fotos en `img/playa.jpg` y `img/municipalidad.jpg`.

| Qué | URL |
|---|---|
| Inicio / Delegaciones / Servicios / Contacto | `/`, `/delegaciones/`, `/servicios/`, `/contacto/` |
| Iniciar sesión | `/ingresar/` (acepta `?next=` solo hacia páginas de este sitio) |
| Recuperar contraseña (correo → código de 6 dígitos → nueva contraseña) | `/recuperar/` |
| Cambiar contraseña (requiere sesión) | `/cambiar-clave/` |

- **Iniciar sesión es real**: llama a `POST /api/auth/login/` de `core`. El Administrador entra al panel
  (`/organizacion/`); los demás roles, al inicio. `LOGIN_URL` de las pantallas ahora es `/ingresar/`.
  El botón **Salir** (sitio y panel) llama a `POST /api/auth/logout/`.
- **Recuperar contraseña y cambiar contraseña son reales**: llaman a los endpoints de `core`
  (`/api/auth/recuperar/solicitar/`, `/verificar/`, `/confirmar/` y `/api/auth/cambiar-clave/`). El código se
  envía por correo (en local sale en la consola del servidor) y tiene vencimiento e intentos limitados.
- **No hay registro público**: las cuentas las crea el Administrador en `/api/usuarios/`.
- Los datos de las delegaciones y los servicios están en `datos_directorio.py` y en `SERVICIOS` de `publico.py`
  (solo Las Compañías está completa; las otras 5 dicen "Por completar"; las coordenadas son aproximadas).
- Pruebas: `tests/test_publico.py` (y `core/tests/test_clave.py` para la recuperación).

### Lo que falta en `core` (Patricio)
- `usuario.delegacion` (HU19), para que la cabecera muestre el código y nombre de la delegación activa.

## Estado de los módulos (para el README de la entrega)

| Módulo | Estado | Nota |
|---|---|---|
| Mantenedor Delegaciones (`/organizacion/delegaciones/`) | Operativo | CRUD real con desactivación, búsqueda, paginador, orden, Excel, SweetAlert2 y auditoría |
| Mantenedor Áreas | Operativo | Las 4 áreas nacen con la delegación; reordenar = intercambiar prioridades |
| Mantenedor Cargos | Operativo | Transversal (sin área) y vigente / no vigente |
| Login y cierre de sesión | Operativo | Usa `/api/auth/login/` y `/api/auth/logout/` de `core` |
| Recuperar y cambiar contraseña | Operativo | Endpoints de `core`; correo por consola en local |
| Sitio público (inicio, delegaciones, servicios, contacto) | Operativo (solo lectura) | Datos en `datos_directorio.py`; las coordenadas de 5 delegaciones son aproximadas |
| Cabecera con delegación activa | Pendiente | Muestra «Acceso global» hasta que exista `usuario.delegacion` (HU19) |
| Prueba INT-ORG-09 (delegación → cargo → funcionario → usuario) | Pendiente | Bloqueada: faltan `Funcionario` y `usuario.delegacion` |
| Pruebas de estrés y de navegador | Pendiente | No ejecutadas; no se declaran aprobadas |
