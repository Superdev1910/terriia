from django.contrib import admin

from .models import Usuario, Funcionario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ["email", "rut", "first_name", "last_name", "rol", "delegacion", "estado"]
    list_filter = ["estado", "rol", "delegacion"]
    search_fields = ["email", "rut", "first_name", "last_name"]
    exclude = ["password", "groups", "user_permissions"]


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["identificador_inst", "nombre", "cargo", "delegacion", "estado"]
    list_filter = ["estado", "delegacion", "cargo"]
    search_fields = ["identificador_inst", "nombre"]
