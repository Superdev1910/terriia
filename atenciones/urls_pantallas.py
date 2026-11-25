from django.urls import path

from . import pantallas

urlpatterns = [
    path("tipos-atencion/", pantallas.tipos_atencion, name="atenciones_tipos"),
    path("sub-atenciones/", pantallas.sub_atenciones, name="atenciones_sub_atenciones"),
    path("registrar/", pantallas.registrar_actividad, name="atenciones_registrar"),
    path("verificacion/", pantallas.verificacion, name="atenciones_verificacion"),
    path("mis-registros/", pantallas.mis_registros, name="atenciones_mis_registros"),
    path("seguimiento/", pantallas.seguimiento, name="atenciones_seguimiento"),
]
