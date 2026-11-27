from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ActividadViewSet,
    BuscarVecinoView,
    EvidenciaViewSet,
    SubAtencionViewSet,
    TipoAtencionViewSet,
    VisitaTerrenoViewSet,
)
from .reportes import ReporteDelegacionesView, ReporteSolicitudesResueltasView

router = DefaultRouter()
router.register("tipos-atencion", TipoAtencionViewSet, basename="tipo-atencion")
router.register("sub-atenciones", SubAtencionViewSet, basename="sub-atencion")
router.register("actividades", ActividadViewSet, basename="actividad")
router.register("evidencias", EvidenciaViewSet, basename="evidencia")
router.register("visitas-terreno", VisitaTerrenoViewSet, basename="visita-terreno")

urlpatterns = [
    # Antes del router de territorio (ver config/urls.py): no debe leerse como vecinos/<pk>/.
    path("vecinos/buscar/", BuscarVecinoView.as_view(), name="vecino-buscar"),
    path(
        "reportes/solicitudes-resueltas/delegaciones/",
        ReporteDelegacionesView.as_view(),
        name="reporte_solicitudes_resueltas_delegaciones",
    ),
    path(
        "reportes/solicitudes-resueltas/",
        ReporteSolicitudesResueltasView.as_view(),
        name="reporte_solicitudes_resueltas",
    ),
    *router.urls,
]
