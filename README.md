# TerriIA

Sistema de gestión de tareas de las delegaciones de la Municipalidad de La Serena.
Proyecto Integrado Inacap · equipo SuperDev.

Backend: Django 5.2 LTS + Django REST Framework · Base de datos: MariaDB 10.5 (servidor) / SQLite (local).

## Correr en tu computador

```bash
git clone <url-del-repo>
cd terriia
git checkout develop
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Windows  (Linux/Mac: cp .env.example .env)
python manage.py migrate
python manage.py createsuperuser # pide email, RUT y clave
python manage.py runserver
```

- API: http://127.0.0.1:8000/api/
- Admin de Django: http://127.0.0.1:8000/admin/
- Login de la API: `POST /api/auth/login/` con `{"email": "...", "password": "..."}`

## Reparto de apps

| App | Responsable | Tablas |
|---|---|---|
| `core` | Patricio | base común: rol, auditoria, plantilla, permisos, validadores |
| `personas` | Patricio / Fernando | usuario / funcionario |
| `organizacion` | Brian | delegacion, area, cargo |
| `territorio` | Pamela | vecino, territorio, junta_vecinos |
| `metas` | Valentina / Fernando | periodo, item / meta_delegacion, meta |

**Trabaja solo en tu app.** Si necesitas cambiar `core` o `config`, avisa a Patricio.

## Estándar de codificación (igual para todos)

Cada mantenedor ocupa los mismos archivos de su app: `models.py`, `serializers.py`,
`views.py`, `urls.py` y `tests/test_<tabla>.py`. El modelo de referencia completo es
`personas` (usuario): cópialo.

| Tema | Cómo se hace |
|---|---|
| Modelo | `db_table = "<tabla>"` y los nombres del SQL v2.3. PK explícita: `id_delegacion = models.AutoField(primary_key=True)` |
| Llaves foráneas | `delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, db_column="id_delegacion")` |
| Vista | Hereda de `core.views.MantenedorViewSet` (trae permisos, auditoría y desactivar) |
| Permisos | Ya vienen en la plantilla (`IsAdministrador`); nunca permisos propios |
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

Luego agrega tu app en `config/urls.py` (la línea ya está comentada, solo descoméntala).

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

## Servidor (AWS)

EC2 Amazon Linux 2023 · Nginx :80 → Gunicorn 127.0.0.1:8000 → MariaDB local.
Para actualizar el servidor con lo último de `main`: `bash deploy/actualizar.sh`.
