from django.urls import path

from . import pantallas

urlpatterns = [
    path("roles/", pantallas.roles, name="core_roles"),
]
