from django.urls import path

from . import pantallas

urlpatterns = [
    path("", pantallas.inicio, name="org_inicio"),
    path("delegaciones/", pantallas.delegaciones, name="org_delegaciones"),
    path("areas/", pantallas.areas, name="org_areas"),
    path("cargos/", pantallas.cargos, name="org_cargos"),
]
