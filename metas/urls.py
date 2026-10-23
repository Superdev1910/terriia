from rest_framework.routers import DefaultRouter
from .views import (
    ItemViewSet,
    PeriodoViewSet,
    MetaDelegacionViewSet,
    MetaIndividualViewSet,
    RecalibracionMetaViewSet,
)

router = DefaultRouter()
router.register(r"periodos", PeriodoViewSet, basename="periodo")
router.register(r"items", ItemViewSet, basename="item")
router.register(r"metas-delegacion", MetaDelegacionViewSet, basename="meta-delegacion")
router.register(r"metas", MetaIndividualViewSet, basename="meta")
router.register(r"recalibraciones-meta", RecalibracionMetaViewSet, basename="recalibracion-meta")

urlpatterns = router.urls
