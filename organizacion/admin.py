from django.contrib import admin

from .models import Area, Cargo, Delegacion


@admin.register(Delegacion)
class DelegacionAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "ambito", "comuna", "estado"]
    list_filter = ["estado"]
    search_fields = ["codigo", "nombre"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["delegacion", "nombre", "prioridad", "estado"]
    list_filter = ["estado", "nombre", "delegacion"]


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "area", "vigente"]
    list_filter = ["vigente"]
    search_fields = ["nombre"]
