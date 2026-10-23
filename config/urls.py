from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/", include("personas.urls")),
    # Cada integrante agrega aquí la línea de su app cuando tenga su urls.py:
    path("api/", include("organizacion.urls")),
    path("api/", include("territorio.urls")),
    path("organizacion/", include("organizacion.urls_pantallas")),  # pantallas HTML (Brian)
    path("territorio/", include("territorio.urls_pantallas")),
    path("personas/", include("personas.urls_pantallas")),
    path("api/", include("metas.urls")),
    path("metas/", include("metas.urls_pantallas")),
    path("api/", include("atenciones.urls")),
    path("atenciones/", include("atenciones.urls_pantallas")),
    path("api-auth/", include("rest_framework.urls")),  # login de la API navegable
    path("", include("organizacion.urls_publico")),  # sitio público + acceso (Brian)
]
