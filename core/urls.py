from django.urls import path

from .views import LoginView, LogoutView, YoView
from .views_clave import (
    CambiarClaveView,
    ConfirmarRecuperacionView,
    SolicitarCodigoView,
    VerificarCodigoView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/yo/", YoView.as_view(), name="yo"),
    path("auth/recuperar/solicitar/", SolicitarCodigoView.as_view(), name="recuperar_solicitar"),
    path("auth/recuperar/verificar/", VerificarCodigoView.as_view(), name="recuperar_verificar"),
    path(
        "auth/recuperar/confirmar/", ConfirmarRecuperacionView.as_view(), name="recuperar_confirmar"
    ),
    path("auth/cambiar-clave/", CambiarClaveView.as_view(), name="cambiar_clave"),
]
