from django.contrib import admin

from .models import JuntaVecinos, MiembroJunta, Territorio, Vecino


@admin.register(Vecino)
class VecinoAdmin(admin.ModelAdmin):
    list_display = ["rut", "nombres", "apellidos", "estado"]
    list_filter = ["estado"]
    search_fields = ["rut", "nombres", "apellidos"]


@admin.register(Territorio)
class TerritorioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "delegacion", "es_formal", "activo"]
    list_filter = ["activo", "es_formal", "delegacion"]
    search_fields = ["nombre"]


@admin.register(JuntaVecinos)
class JuntaVecinosAdmin(admin.ModelAdmin):
    list_display = ["numero_registro", "nombre", "territorio", "activa"]
    list_filter = ["activa", "territorio"]
    search_fields = ["numero_registro", "nombre"]


@admin.register(MiembroJunta)
class MiembroJuntaAdmin(admin.ModelAdmin):
    list_display = ["vecino", "junta", "cargo", "fecha_ingreso", "fecha_salida", "estado"]
    list_filter = ["estado", "cargo"]
    search_fields = ["vecino__rut", "vecino__nombres", "vecino__apellidos", "junta__nombre"]
    raw_id_fields = ["vecino"]
