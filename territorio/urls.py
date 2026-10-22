from rest_framework.routers import DefaultRouter

from .views import JuntaVecinosViewSet, TerritorioViewSet, VecinoViewSet

router = DefaultRouter()
router.register("vecinos", VecinoViewSet, basename="vecino")
router.register("territorios", TerritorioViewSet, basename="territorio")
router.register("juntas-vecinos", JuntaVecinosViewSet, basename="junta-vecinos")

urlpatterns = router.urls
