from rest_framework.routers import DefaultRouter

from .views import SubAtencionViewSet, TipoAtencionViewSet

router = DefaultRouter()
router.register("tipos-atencion", TipoAtencionViewSet, basename="tipo-atencion")
router.register("sub-atenciones", SubAtencionViewSet, basename="sub-atencion")

urlpatterns = router.urls
