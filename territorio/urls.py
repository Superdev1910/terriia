from rest_framework.routers import DefaultRouter

from .views import (
    JuntaVecinosViewSet,
    MiembroJuntaViewSet,
    TerritorioViewSet,
    VecinoViewSet,
)

router = DefaultRouter()
router.register("vecinos", VecinoViewSet, basename="vecino")
router.register("territorios", TerritorioViewSet, basename="territorio")
router.register("juntas-vecinos", JuntaVecinosViewSet, basename="junta-vecinos")
router.register("miembros-junta", MiembroJuntaViewSet, basename="miembro-junta")

urlpatterns = router.urls
