from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import MiPerfilView, UsuarioViewSet, FuncionarioViewSet

router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")
router.register("funcionarios", FuncionarioViewSet, basename="funcionario")

urlpatterns = [path("mi-perfil/", MiPerfilView.as_view(), name="mi-perfil-api")] + router.urls
