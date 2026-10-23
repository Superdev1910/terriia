from django.urls import path

from . import pantallas

urlpatterns = [
    path("usuarios/", pantallas.usuarios, name="personas_usuarios"),
    path("funcionarios/", pantallas.funcionarios, name="personas_funcionarios"),
]
