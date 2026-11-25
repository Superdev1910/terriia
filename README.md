# TerriIA

Sistema de gestión de tareas de las delegaciones de la Municipalidad de La Serena.
Proyecto Integrado Inacap · equipo SuperDev.

## Versiones

| Componente | Versión | Fuente |
|---|---|---|
| Python | 3.13 en desarrollo local; la integración continua usa 3.14 | `.github/workflows/pruebas.yml` |
| Django | 5.2.18 (LTS; Django 6 exige MariaDB 10.6+ y el servidor tiene 10.5) | `requirements.txt` |
| Django REST Framework | 3.16.1 | `requirements.txt` |
| django-filter / python-dotenv | 25.2 / 1.2.4 | `requirements.txt` |
| Base de datos | MariaDB 10.5 / MySQL en el servidor (`mysqlclient` 2.2.7); SQLite en local | `requirements-servidor.txt`, `config/settings.py` |
| Servidor de aplicación | Gunicorn 23.0.0 detrás de Nginx | `requirements-servidor.txt`, `deploy/` |
| Formato | black (línea de 100) | `pyproject.toml` |

## Estructura del repositorio

```
terriia/
├── config/          settings, urls y wsgi del proyecto
├── core/            roles, auditoría, permisos, validadores, login y recuperación de clave
├── personas/        usuario (login por email) y funcionario
├── organizacion/    delegación, área, cargo + sitio público y pantalla de inicio
├── territorio/      vecino, territorio, junta de vecinos
├── metas/           período, ítem, metas por delegación e individuales, recalibraciones
├── atenciones/      catálogos de atención, actividades, verificación y evidencias
├── deploy/          gunicorn.service, nginx-terriia.conf, actualizar.sh, respaldo.sh, restaurar.sh
├── docs/            modelo de datos (SQL), guías y planes
├── requirements.txt / requirements-servidor.txt
└── .env.example     plantilla de variables de entorno
```

## Correr en tu computador

```bash
git clone <url-del-repo>
cd terriia
git checkout develop
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows  (Linux/Mac: cp .env.example .env)
# En el .env agrega DJANGO_DEBUG=True (solo desarrollo; por defecto el sitio corre con DEBUG=False)
python manage.py migrate
python manage.py createsuperuser # pide email, RUT y clave
python manage.py runserver
```

- Sitio público: http://127.0.0.1:8000/ · ingreso: http://127.0.0.1:8000/ingresar/
- API: http://127.0.0.1:8000/api/
- Admin de Django: http://127.0.0.1:8000/admin/
- Login de la API: `POST /api/auth/login/` con `{"email": "...", "password": "..."}`
- Correo real para «¿Olvidaste tu contraseña?» (opcional): sigue [docs/LEEME-correo.md](docs/LEEME-correo.md).
  Sin eso, el código sale en la consola del servidor.
- Las variables del `.env` están explicadas, por secciones, en [`.env.example`](.env.example). Por seguridad `DJANGO_DEBUG` vale
  `False` si no se define, y entonces `DJANGO_SECRET_KEY` es obligatoria (sin ella Django no arranca). Para correr las pruebas
  fuera de tu `.env` define al menos `DJANGO_SECRET_KEY` (GitHub Actions ya lo hace).

## Cómo correr las pruebas

```bash
python manage.py check
python manage.py makemigrations --check --dry-run   # las migraciones deben estar al día
python manage.py test                               # toda la suite
python manage.py test atenciones                    # solo una app
black --check .                                     # formato (lo exige GitHub Actions)
```

Las pruebas usan SQLite y un `MEDIA_ROOT` temporal para las evidencias (no dejan archivos). GitHub Actions
(`.github/workflows/pruebas.yml`) corre black, las migraciones y las pruebas en cada Pull Request.

## Módulos, rutas y pantallas

La API vive bajo `/api/` y las pantallas HTML bajo el prefijo de cada app. Los permisos reales se validan siempre en el
servidor; ocultar un ítem del menú no es una medida de seguridad.

| Módulo | API | Pantallas | Quién |
|---|---|---|---|
| Acceso (`core`) | `/api/auth/login/`, `logout/`, `yo/`, `recuperar/solicitar|verificar|confirmar/`, `cambiar-clave/` | `/ingresar/`, `/recuperar/`, `/cambiar-clave/` | Todos |
| Roles (`core`) | `/api/roles/` | `/core/roles/` | Administrador |
| Personas | `/api/usuarios/`, `/api/funcionarios/`, `/api/mi-perfil/` | `/personas/usuarios/`, `/personas/funcionarios/`, `/personas/mi-perfil/` | Administrador; Delegado (funcionarios de su delegación); Funcionario (su perfil) |
| Organización | `/api/delegaciones/`, `/api/areas/`, `/api/cargos/`, `/api/organizacion/resumen/` | `/organizacion/` (inicio), `delegaciones/`, `areas/`, `cargos/` | Administrador |
| Territorio | `/api/vecinos/`, `/api/territorios/`, `/api/juntas-vecinos/` | `/territorio/vecinos/`, `territorios/`, `juntas-vecinos/` | Administrador; Delegado (territorios y juntas de su delegación) |
| Metas | `/api/periodos/`, `/api/items/`, `/api/metas-delegacion/`, `/api/metas/`, `/api/recalibraciones-meta/` | `/metas/periodos/`, `items/`, `metas-delegacion/`, `metas-individuales/` | Administrador; Delegado (metas de su delegación) |
| Catálogos de atención | `/api/tipos-atencion/`, `/api/sub-atenciones/` | `/atenciones/tipos-atencion/`, `/atenciones/sub-atenciones/` | Administrador |
| Actividades | `/api/actividades/` (GET, POST, PUT/PATCH solo el autor; sin DELETE), `/api/actividades/opciones/`, `/api/vecinos/buscar/?rut=` | `/atenciones/registrar/` (Registrar actividad), `/atenciones/mis-registros/` (Mis registros) | Registran: Funcionario, Encargado de área, Delegado, Administrador. Consultan por API (con su alcance): Jefe de delegaciones y Alcaldesa |
| Verificación | `POST /api/actividades/<id>/verificar/`, `GET /api/actividades/<id>/historial/` | `/atenciones/verificacion/` | Delegado, Encargado de área (su delegación); Jefe de delegaciones y Administrador (todas) |
| Seguimiento | `POST /api/actividades/<id>/{asignar,cambiar-estado,fecha-compromiso,motivo-atraso}/`, `GET/POST .../comentarios/`, `GET .../historial-seguimiento/`, `GET /api/actividades/?vencida=true` | `/atenciones/seguimiento/` (Seguimiento) | Asignar: Delegado (su delegación) y Administrador. Estado, fecha, motivo y comentarios: ellos más el autor y el responsable. Ver `docs/LEEME-seguimiento-actividades.md` |
| Evidencias | `/api/evidencias/` (subir, listar, borrar), `GET /api/evidencias/<id>/archivo/` | Dentro de «Mis registros» y de la ficha de «Verificación» | Autor y verificadores con alcance |

### Actividades y gestión social

- Una sola tabla (`tipo_registro`: actividad o gestión social). El código se genera solo: `<COD_DELEGACION>-<AAAA>-<5 dígitos>`.
- Reglas (en `atenciones/reglas.py`): máximo 7 por funcionario al día; no se acepta fecha futura; la semana (lunes a domingo)
  se cierra al terminar el domingo más `SEMANA_CIERRE_DIAS_GRACIA` días (a confirmar con el cliente); el ítem debe ser del cargo del
  funcionario y el área, territorio y vecino de su delegación. `pondera` y `motivo_no_pondera` los calcula el servidor.
- Verificación: `pendiente → aprobada | rechazada | antecedentes`; `antecedentes → pendiente` cuando el autor edita. Aprobada y
  rechazada son finales y una actividad aprobada no se modifica (ni por API ni por el admin de Django). Nadie verifica lo propio.
- Evidencias: solo JPG, PNG o PDF de hasta 5 MB (se valida el tipo real por la firma del archivo). No tienen URL pública: se
  descargan por la API con control de delegación; en producción nginx las entrega con `X-Accel-Redirect`
  (`EVIDENCIAS_X_ACCEL_PREFIX=/media`).
- Modelo de datos y cambios: [docs/modelo-fisico-mysql-terriia-v2.6-delta.sql](docs/modelo-fisico-mysql-terriia-v2.6-delta.sql).

## Perfiles (roles) y qué puede hacer cada uno

Los 6 roles del sistema están en `core/models.py` y no se pueden renombrar ni desactivar.

| Rol | Alcance | Qué puede hacer |
|---|---|---|
| Administrador | Global | Todos los mantenedores y catálogos; crear cuentas y asignar roles; ver todas las actividades; verificar (no las propias). |
| Jefe de delegaciones | Global | Consultar actividades de todas las delegaciones y verificarlas. |
| Delegado territorial | Su delegación | Territorios, juntas, funcionarios y metas de su delegación; registrar actividades (si tiene ficha de funcionario); ver y verificar las actividades de su delegación. Catálogos globales en solo lectura. |
| Encargado de área | Su delegación | Registrar actividades (con ficha de funcionario), ver y verificar las de su delegación. |
| Funcionario | Lo propio | Ver su ficha y metas en `/personas/mi-perfil/`; registrar actividades y gestiones sociales, editarlas mientras estén pendientes o con antecedentes solicitados, subir evidencias, ver «Mis registros» y dar seguimiento (estado, fecha de compromiso, motivo de atraso y comentarios) a las que escribió o le asignaron. |
| Alcaldesa | Global | Consulta de actividades por API; hoy no tiene pantallas propias en el menú. |

El acceso global (todas las delegaciones) lo dan solo los roles Administrador, Jefe de delegaciones y Alcaldesa. Un Delegado, Encargado o Funcionario sin delegación asignada no ve nada de actividades (403). La creación de cuentas y la asignación de roles son
exclusivas del Administrador.

## Estado de cada módulo

Según el código actual del repositorio.

| Módulo | Estado | Observaciones |
|---|---|---|
| Acceso, roles y auditoría (`core`) | Hecho | Login por sesión, roles, auditoría de mantenedores, recuperación de contraseña por código y cambio de clave. |
| Usuarios y funcionarios (`personas`) | Hecho | Mantenedores con alcance por delegación y «Mis datos y metas» del funcionario. |
| Organización (`organizacion`) | Hecho | Delegaciones (crean sus 4 áreas), áreas, cargos, sitio público e inicio. |
| Territorio (`territorio`) | Parcial | Vecinos, territorios y juntas listos. El vecino no tiene delegación propia (se deduce de sus actividades; `TODO(Pamela)`). |
| Metas (`metas`) | Parcial | Períodos, ítems, metas por delegación e individuales y recalibraciones con mantenedores. No hay dashboard, semáforo ni cálculo del 120 % (`TODO(Valentina)`). |
| Catálogos de atención (`atenciones`) | Hecho | Tipos de atención y sub atenciones (semilla de ejemplo del área Social). |
| Actividades y gestión social (`atenciones`) | Hecho | Ingreso, reglas de negocio, edición del autor, «Registrar actividad» y «Mis registros» con Excel. |
| Seguimiento de actividades (`atenciones`) | Hecho (pendiente prueba en MariaDB y servidor) | Asignar a un área, estado, fecha de compromiso con historial, motivo de atraso, vencidas resaltadas y comentarios (HU02 a HU08). Pantalla «Seguimiento». |
| Verificación y evidencias (`atenciones`) | Hecho (pendiente prueba manual en navegador) | Transiciones, historial, bandeja y ficha, subida y descarga protegida. Falta la prueba manual de las pantallas en navegador y configurar nginx en el servidor. |
| Tubo y búsqueda | No iniciado | `ingreso_a_tubo` solo se guarda como dato (`TODO(Brian)`); `id_hito` es un entero sin modelo Hito. |
| Reportes y protocolo | No iniciado | `TODO(Pamela)`. |
| Felicitaciones y ausencias | No iniciado | `TODO(Fernando)`. |
| Usuarios de demostración (`DEMO_CLAVE`) | No iniciado | La variable está documentada en `.env.example` pero ningún código la lee todavía. |

## Reparto de apps

| App | Responsable | Tablas |
|---|---|---|
| `core` | Patricio | base común: rol, auditoria, codigo_recuperacion, permisos, validadores |
| `personas` | Patricio / Fernando | usuario / funcionario |
| `organizacion` | Brian | delegacion, area, cargo |
| `territorio` | Pamela | vecino, territorio, junta_vecinos |
| `metas` | Valentina / Fernando | periodo, item / meta_delegacion, meta, recalibracion_meta |
| `atenciones` | Patricio | tipo_atencion, sub_atencion, actividad, contador_codigo_actividad, historial_verificacion, evidencia; seguimiento (Brian): actividad_historial, comentario |

**Trabaja solo en tu app.** Si necesitas cambiar `core` o `config`, avisa a Patricio.

## Estándar de codificación (igual para todos)

Cada mantenedor ocupa los mismos archivos de su app: `models.py`, `serializers.py`,
`views.py`, `urls.py` y `tests/test_<tabla>.py`. El modelo de referencia completo es
`personas` (usuario): cópialo.

| Tema | Cómo se hace |
|---|---|
| Modelo | `db_table = "<tabla>"` y los nombres del SQL v2.4 y sus deltas v2.5 y v2.6. PK explícita: `id_delegacion = models.AutoField(primary_key=True)` |
| Llaves foráneas | `delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, db_column="id_delegacion")` |
| Vista | Hereda de `core.views.MantenedorViewSet` (trae permisos, auditoría y desactivar) |
| Permisos | Por defecto `IsAdministrador`. Los mantenedores operativos pueden declarar alcance por delegación en el backend; nunca basta ocultar opciones en el menú. |
| Borrado | Nunca DELETE físico. Indica `campo_estado` (`estado`, `activo`, `vigente`, `activa`) |
| Auditoría | Automática; no se escribe a mano |
| Validaciones | En el serializer (`validate_<campo>` / `validate`). RUT con `core.validators` |
| URLs | `/api/<tabla en plural>/` registrada con `DefaultRouter` en `urls.py` de tu app |
| Errores | Formato único automático: `{"error": "mensaje", "campo": "nombre"}` |
| Pruebas | `APITestCase` con 5 casos: crear, editar, duplicado/inválido, desactivar, acceso denegado |
| Estilo | PEP 8, nombres en español sin tildes, `black .` antes de cada commit |

Plantilla de vista:

```python
from core.views import MantenedorViewSet
from .models import Delegacion
from .serializers import DelegacionSerializer

class DelegacionViewSet(MantenedorViewSet):
    queryset = Delegacion.objects.all()
    serializer_class = DelegacionSerializer
    search_fields = ["nombre"]
    filterset_fields = ["estado"]
    campo_estado = "estado"
```

## Flujo de trabajo en Git

- `main`: lo que está en el servidor AWS. Solo Patricio une `develop` → `main`.
- `develop`: integración. **Nadie hace push directo**: todo entra por Pull Request.

1. `git checkout develop && git pull`
2. `git checkout -b feature/<tabla>` (ej. `feature/territorio`)
3. Commits con el código de Jira: `SCRUM-31 crea mantenedor territorio`
4. `python manage.py makemigrations <tu_app>`, `python manage.py test` y `black .`
5. `git push -u origin feature/<tabla>` y abre un Pull Request hacia **develop**
6. GitHub corre las pruebas solo. Patricio revisa y aprueba; recién ahí se une.
7. Al unir, la subtarea pasa a Finalizada en Jira.

Reglas:
- No edites migraciones de otras apps ni borres migraciones ya subidas.
- Nunca subas el `.env` ni `db.sqlite3` (ya están en `.gitignore`).

## Despliegue

### AWS (producción)

EC2 Amazon Linux 2023 · Nginx :80 → Gunicorn 127.0.0.1:8000 → MariaDB local.

1. Instalar Python, MariaDB, Nginx y Git; clonar el repo en `/var/www/terriia`; crear el `venv` y
   `pip install -r requirements-servidor.txt`.
2. Crear el `.env` desde `.env.example` con `DB_ENGINE=mysql`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` y claves reales
   (solo en el servidor), el correo SMTP y **`EVIDENCIAS_X_ACCEL_PREFIX=/media`**.
3. `python manage.py migrate` y `python manage.py collectstatic --noinput` (deja los estáticos en `static/`).
4. Gunicorn: copiar `deploy/gunicorn.service` a `/etc/systemd/system/` y `sudo systemctl enable --now gunicorn`.
5. Nginx: copiar `deploy/nginx-terriia.conf` a `/etc/nginx/conf.d/terriia.conf` y `sudo nginx -t && sudo systemctl reload nginx`.
   Sirve `/static/` desde `STATIC_ROOT` y deja `/media/` como `internal` (solo accesible vía `X-Accel-Redirect` desde Django:
   las evidencias nunca tienen URL pública).
6. Actualizar con lo último de `main`: `bash deploy/actualizar.sh`.
7. Respaldos diarios con cron (en `/var/backups/terriia/`, fuera del proyecto): ver [docs/respaldo-recuperacion.md](docs/respaldo-recuperacion.md).
8. **HTTPS: hoy el servidor atiende solo por HTTP y falta el certificado.** Cuando exista, activar el bloque 443 de nginx (hay un
   ejemplo comentado en `deploy/nginx-terriia.conf`) y poner `DJANGO_HTTPS=True` en el `.env`: activa cookies de sesión y CSRF
   `Secure`, la redirección a https y HSTS. No activarlo antes (el sitio dejaría de funcionar).

### PythonAnywhere (pruebas / demostración)

Aplicación web con el `venv` del proyecto, `.env` en la carpeta del proyecto y `DB_ENGINE=sqlite` (o la base MySQL de la cuenta).
Define los archivos estáticos en la pestaña *Web* (`/static/` → carpeta `static/` tras `collectstatic`) y deja
`EVIDENCIAS_X_ACCEL_PREFIX` vacío (no hay nginx propio: Django entrega la evidencia). Tras cada cambio, pulsa **Reload**. Cuidado con la
sangría del archivo WSGI (ver incidencias).

## Más documentación

- [docs/LEEME-modelo-datos.md](docs/LEEME-modelo-datos.md): reglas del modelo de datos (SQL v2.4, deltas v2.5 y v2.6).
- [docs/LEEME-correo.md](docs/LEEME-correo.md): correo real en local para recuperar la contraseña.
- [docs/respaldo-recuperacion.md](docs/respaldo-recuperacion.md): respaldos, restauración y prueba de restauración.
- [docs/incidencias-configuracion.md](docs/incidencias-configuracion.md): problemas de entorno ya vividos y su solución.
- [deploy/](deploy/): `gunicorn.service`, `nginx-terriia.conf`, `actualizar.sh`, `respaldo.sh`, `restaurar.sh`.
