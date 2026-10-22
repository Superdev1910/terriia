from django.urls import path

from . import pantallas

urlpatterns = [
    path("vecinos/", pantallas.vecinos, name="territorio_vecinos"),
    path("territorios/", pantallas.territorios, name="territorio_territorios"),
    path("juntas-vecinos/", pantallas.juntas, name="territorio_juntas"),
]
