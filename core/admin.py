from django.contrib import admin

from .models import Auditoria, Rol


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ["id_rol", "nombre", "descripcion", "activo"]

    def has_add_permission(self, request):
        return False  # se crean en el mantenedor (/core/roles/)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.es_del_sistema:
            return ["nombre", "activo"]  # los permisos los usan por nombre
        return []

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ["fecha", "usuario", "evento", "entidad", "entidad_id"]
    list_filter = ["evento", "entidad"]
    readonly_fields = [f.name for f in Auditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
