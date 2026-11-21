from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ActividadViewSet, BuscarVecinoView, SubAtencionViewSet, TipoAtencionViewSet

router = DefaultRouter()
router.register("tipos-atencion", TipoAtencionViewSet, basename="tipo-atencion")
router.register("sub-atenciones", SubAtencionViewSet, basename="sub-atencion")
router.register("actividades", ActividadViewSet, basename="actividad")

urlpatterns = [
    # Antes del router de territorio (ver config/urls.py): no debe leerse como vecinos/<pk>/.
    path("vecinos/buscar/", BuscarVecinoView.as_view(), name="vecino-buscar"),
    *router.urls,
]
