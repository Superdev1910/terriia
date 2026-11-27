from django.urls import path

from . import pantallas

urlpatterns = [
    path("periodos/", pantallas.periodos, name="metas_periodos"),
    path("items/", pantallas.items, name="metas_items"),
    path("metas-delegacion/", pantallas.metas_delegacion, name="metas_delegacion"),
    path("metas-individuales/", pantallas.metas_individuales, name="metas_individuales"),
    path("dashboard-ejecutivo/", pantallas.dashboard_ejecutivo, name="metas_dashboard_ejecutivo"),
    path(
        "cumplimiento-delegacion/",
        pantallas.cumplimiento_delegacion,
        name="metas_cumplimiento_delegacion",
    ),
    path("mi-cumplimiento/", pantallas.mi_cumplimiento, name="metas_mi_cumplimiento"),
    path(
        "felicitaciones-reclamos/",
        pantallas.felicitaciones,
        name="metas_felicitaciones",
    ),
]
