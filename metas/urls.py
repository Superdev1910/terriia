from rest_framework.routers import DefaultRouter
from .views import ItemViewSet, PeriodoViewSet

router = DefaultRouter()
router.register(r"periodos", PeriodoViewSet, basename="periodo")
router.register(r"items", ItemViewSet, basename="item")

urlpatterns = router.urls
