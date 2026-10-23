from django.urls import path

from . import pantallas

urlpatterns = [
    path("tipos-atencion/", pantallas.tipos_atencion, name="atenciones_tipos"),
    path("sub-atenciones/", pantallas.sub_atenciones, name="atenciones_sub_atenciones"),
]
