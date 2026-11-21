from django.contrib import admin

from .models import Actividad, SubAtencion, TipoAtencion


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


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    """Solo consulta y edición de actividades no aprobadas: el alta es por la API (código y
    ponderación los calcula el servidor) y una actividad aprobada no se puede tocar."""

    list_display = ["codigo", "funcionario", "tipo_registro", "fecha", "estado_verificacion"]
    list_filter = ["tipo_registro", "estado_verificacion"]
    search_fields = ["codigo", "funcionario__nombre"]
    readonly_fields = ["codigo", "fecha_registro", "estado_verificacion", "pondera"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.estado_verificacion == Actividad.VERIF_APROBADA:
            return False  # solo lectura
        return super().has_change_permission(request, obj)
