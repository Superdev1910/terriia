from django.urls import path

from . import pantallas

urlpatterns = [
    path("mi-perfil/", pantallas.mi_perfil, name="personas_mi_perfil"),
    path("usuarios/", pantallas.usuarios, name="personas_usuarios"),
    path("funcionarios/", pantallas.funcionarios, name="personas_funcionarios"),
]
