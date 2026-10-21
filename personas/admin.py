from django.contrib import admin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ["email", "rut", "first_name", "last_name", "rol", "estado"]
    list_filter = ["estado", "rol"]
    search_fields = ["email", "rut", "first_name", "last_name"]
    exclude = ["password", "groups", "user_permissions"]
