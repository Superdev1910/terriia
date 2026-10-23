from django.urls import path

from . import pantallas

urlpatterns = [
    path("periodos/", pantallas.periodos, name="metas_periodos"),
    path("items/", pantallas.items, name="metas_items"),
    path("metas-delegacion/", pantallas.metas_delegacion, name="metas_delegacion"),
    path("metas-individuales/", pantallas.metas_individuales, name="metas_individuales"),
]
