from django.contrib import admin

from .models import SubAtencion, TipoAtencion


@admin.register(TipoAtencion)
class TipoAtencionAdmin(admin.ModelAdmin):
    list_display = ["nombre", "area", "activo"]
    list_filter = ["area", "activo"]
    search_fields = ["nombre"]


@admin.register(SubAtencion)
class SubAtencionAdmin(admin.ModelAdmin):
    list_display = ["nombre", "tipo_atencion", "activo"]
    list_filter = ["tipo_atencion__area", "activo"]
    search_fields = ["nombre", "tipo_atencion__nombre"]
