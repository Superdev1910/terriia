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
Última verificación local registrada para HU20/HU22: `& .\venv\Scripts\python.exe manage.py test`
completó 545 pruebas, OK en 1189.837 segundos, tras la corrección final de ruta HU22 (2026-11-26).

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
| Metas | `/api/periodos/`, `/api/items/`, `/api/metas-delegacion/`, `/api/metas/`, `/api/recalibraciones-meta/`, `/api/dashboard/ejecutivo/` | `/metas/periodos/`, `items/`, `metas-delegacion/`, `metas-individuales/`, `/metas/dashboard-ejecutivo/` | Mantenedores: Administrador y Delegado (según alcance); dashboard ejecutivo: Alcaldesa y Administrador |
| Catálogos de atención | `/api/tipos-atencion/`, `/api/sub-atenciones/` | `/atenciones/tipos-atencion/`, `/atenciones/sub-atenciones/` | Administrador |
| Actividades | `/api/actividades/` (GET, POST, PUT/PATCH solo el autor; sin DELETE), `/api/actividades/opciones/`, `/api/vecinos/buscar/?rut=` | `/atenciones/registrar/` (Registrar actividad), `/atenciones/mis-registros/` (Mis registros) | Registran: Funcionario, Encargado de área, Delegado, Administrador. Consultan por API (con su alcance): Jefe de delegaciones y Alcaldesa |
| Verificación | `POST /api/actividades/<id>/verificar/`, `GET /api/actividades/<id>/historial/` | `/atenciones/verificacion/` | Delegado, Encargado de área (su delegación); Jefe de delegaciones y Administrador (todas) |
| Seguimiento | `POST /api/actividades/<id>/{asignar,cambiar-estado,fecha-compromiso,motivo-atraso}/`, `GET/POST .../comentarios/`, `GET .../historial-seguimiento/`, `GET /api/actividades/?vencida=true` | `/atenciones/seguimiento/` (Seguimiento) | Asignar: Delegado (su delegación) y Administrador. Estado, fecha, motivo y comentarios: ellos más el autor y el responsable. Ver `docs/LEEME-seguimiento-actividades.md` |
| Reporte histórico (HU20) | `GET /api/reportes/solicitudes-resueltas/` descarga Excel; `GET /api/reportes/solicitudes-resueltas/delegaciones/` | `/atenciones/reportes/solicitudes-resueltas/` | Administrador y Jefe de delegaciones. Ver `docs/reporte-historico-hu20.md` |
| Dashboard ejecutivo (HU22) | `GET /api/dashboard/ejecutivo/` | `/metas/dashboard-ejecutivo/` | Alcaldesa y Administrador; solo promedios globales y por delegación |
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
| Alcaldesa | Global | Consulta de actividades autorizadas y dashboard ejecutivo consolidado; sin exposición de funcionarios, vecinos, áreas ni solicitudes individuales en HU22. |

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
| Metas (`metas`) | Parcial | Mantenedores, cálculos, semáforo y dashboard ejecutivo agregado por delegación. Pendiente completar aspectos restantes del módulo y resolver la unificación del tope 120/150 documentada en el servicio. |
| Catálogos de atención (`atenciones`) | Hecho | Tipos de atención y sub atenciones (semilla de ejemplo del área Social). |
| Actividades y gestión social (`atenciones`) | Hecho | Ingreso, reglas de negocio, edición del autor, «Registrar actividad» y «Mis registros» con Excel. |
| Seguimiento de actividades (`atenciones`) | Hecho (pendiente prueba en MariaDB y servidor) | Asignar a un área, estado, fecha de compromiso con historial, motivo de atraso, vencidas resaltadas y comentarios (HU02 a HU08). Pantalla «Seguimiento». |
| Verificación y evidencias (`atenciones`) | Hecho (pendiente prueba manual en navegador) | Transiciones, historial, bandeja y ficha, subida y descarga protegida. Falta la prueba manual de las pantallas en navegador y configurar nginx en el servidor. |
| Tubo y búsqueda | No iniciado | `ingreso_a_tubo` solo se guarda como dato (`TODO(Brian)`); `id_hito` es un entero sin modelo Hito. |
| Reporte histórico (HU20) | Implementado, validación de navegador pendiente | Filtros, permisos, interfaz local y archivo `.xlsx` OpenXML generado por el servidor; 9 pruebas enfocadas aprobadas. No se verificó la descarga visual en navegador ni apertura en Excel/LibreOffice. Ver `docs/reporte-historico-hu20.md`. |
| Dashboard ejecutivo (HU22) | Implementado y validado en pruebas enfocadas | Pantalla y endpoint Alcaldesa/Administrador, agregados globales y por todas las delegaciones, semáforo del servicio existente y respuesta sin datos individuales; 7 pruebas HU22 aprobadas. Ver `docs/evaluacion3-hu20-hu22.md`. |
| Entregables de Evaluación 3 | Parcial | Anexo de protocolo, indicadores, trazabilidad, resultados esperados/observados y defectos: `docs/evaluacion3-hu20-hu22.md`. El plan de pruebas Excel existente se conserva como documento base. |
| Felicitaciones y ausencias | No iniciado | `TODO(Fernando)`. |
| Usuarios de demostración (`DEMO_CLAVE`) | Hecho | Comando `python manage.py cargar_demo`: carga delegaciones, un usuario por rol (`*.demo@terriia.test`), metas, vecinos y actividades ficticias; la clave sale solo de `DEMO_CLAVE`. Solo para demo o evaluación. Ver Despliegue. |

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
8. Datos de demostración (solo si se necesitan para evaluar): ver «Datos de demostración» más abajo (`DEMO_CLAVE` + `cargar_demo`).
9. **HTTPS: hoy el servidor atiende solo por HTTP y falta el certificado.** Cuando exista, activar el bloque 443 de nginx (hay un
   ejemplo comentado en `deploy/nginx-terriia.conf`) y poner `DJANGO_HTTPS=True` en el `.env`: activa cookies de sesión y CSRF
   `Secure`, la redirección a https y HSTS. No activarlo antes (el sitio dejaría de funcionar).

### PythonAnywhere (pruebas / demostración)

Aplicación web con el `venv` del proyecto, `.env` en la carpeta del proyecto y `DB_ENGINE=sqlite` (o la base MySQL de la cuenta).
Define los archivos estáticos en la pestaña *Web* (`/static/` → carpeta `static/` tras `collectstatic`) y deja
`EVIDENCIAS_X_ACCEL_PREFIX` vacío (no hay nginx propio: Django entrega la evidencia). Tras cada cambio, pulsa **Reload**. Cuidado con la
sangría del archivo WSGI (ver incidencias). Para la demostración, ver «Datos de demostración» más abajo (`cargar_demo`).

### Datos de demostración (solo demo o evaluación)

No usar en producción real: crea usuarios y datos ficticios (correos `@terriia.test`, funcionarios `DEMO-*`).

1. Define `DEMO_CLAVE` en el `.env` (mínimo 8 caracteres; debe pasar las reglas de contraseña). No se escribe en el código.
2. `python manage.py cargar_demo` (con el `venv` activo). Es idempotente: se puede repetir sin duplicar y nunca cambia la clave de un usuario existente.
3. Todos los usuarios demo (administrador, jefe de delegaciones, alcaldesa, delegado, encargado de área y 3 funcionarios) usan la clave de `DEMO_CLAVE`. Los dashboards quedan con semáforo verde, ámbar y rojo.
4. `python manage.py cargar_demo --borrar` borra solo los datos demo y los vuelve a cargar.

## Más documentación

- [docs/LEEME-modelo-datos.md](docs/LEEME-modelo-datos.md): reglas del modelo de datos (SQL v2.4, deltas v2.5 y v2.6).
- [docs/LEEME-correo.md](docs/LEEME-correo.md): correo real en local para recuperar la contraseña.
- [docs/respaldo-recuperacion.md](docs/respaldo-recuperacion.md): respaldos, restauración y prueba de restauración.
- [docs/incidencias-configuracion.md](docs/incidencias-configuracion.md): problemas de entorno ya vividos y su solución.
- [deploy/](deploy/): `gunicorn.service`, `nginx-terriia.conf`, `actualizar.sh`, `respaldo.sh`, `restaurar.sh`.
