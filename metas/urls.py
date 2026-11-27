from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    DashboardDelegacionView,
    DashboardEjecutivoView,
    DashboardFuncionarioView,
    ItemViewSet,
    MetaDelegacionViewSet,
    MetaIndividualViewSet,
    PeriodoViewSet,
    RecalibracionMetaViewSet,
    FelicitacionReclamoViewSet,
)

router = DefaultRouter()
router.register(r"periodos", PeriodoViewSet, basename="periodo")
router.register(r"items", ItemViewSet, basename="item")
router.register(r"metas-delegacion", MetaDelegacionViewSet, basename="meta-delegacion")
router.register(r"metas", MetaIndividualViewSet, basename="meta")
router.register(r"recalibraciones-meta", RecalibracionMetaViewSet, basename="recalibracion-meta")
router.register(
    r"felicitaciones-reclamos", FelicitacionReclamoViewSet, basename="felicitacion-reclamo"
)


urlpatterns = router.urls + [
    path(
        "dashboard/funcionario/<int:funcionario_id>/",
        DashboardFuncionarioView.as_view(),
        name="dashboard-funcionario",
    ),
    path(
        "dashboard/delegacion/<int:delegacion_id>/",
        DashboardDelegacionView.as_view(),
        name="dashboard-delegacion",
    ),
    path(
        "dashboard/ejecutivo/",
        DashboardEjecutivoView.as_view(),
        name="dashboard-ejecutivo",
    ),
]
