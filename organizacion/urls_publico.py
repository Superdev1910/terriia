from django.urls import path

from . import publico

urlpatterns = [
    path("", publico.portada, name="pub_inicio"),
    path("delegaciones/", publico.delegaciones, name="pub_delegaciones"),
    path("servicios/", publico.servicios, name="pub_servicios"),
    path("contacto/", publico.contacto, name="pub_contacto"),
    path("ingresar/", publico.ingresar, name="pub_ingresar"),
    path("recuperar/", publico.recuperar, name="pub_recuperar"),
    path("cambiar-clave/", publico.cambiar_clave, name="pub_cambiar_clave"),
]
