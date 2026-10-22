from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AreaViewSet, CargoViewSet, DelegacionViewSet, ResumenView

router = DefaultRouter()
router.register("delegaciones", DelegacionViewSet, basename="delegacion")
router.register("areas", AreaViewSet, basename="area")
router.register("cargos", CargoViewSet, basename="cargo")

urlpatterns = [
    path("organizacion/resumen/", ResumenView.as_view(), name="org_resumen"),
] + router.urls
