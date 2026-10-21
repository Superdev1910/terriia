from django.conf import settings
from django.db import models


class Rol(models.Model):
    """Tabla de solo lectura. Se carga con la migración semilla (core/migrations/0002)."""

    ADMINISTRADOR = "Administrador"
    JEFE_DELEGACIONES = "Jefe de delegaciones"
    DELEGADO_TERRITORIAL = "Delegado territorial"
    ENCARGADO_AREA = "Encargado de área"
    FUNCIONARIO = "Funcionario"
    ALCALDESA = "Alcaldesa"
    TODOS = [
        ADMINISTRADOR,
        JEFE_DELEGACIONES,
        DELEGADO_TERRITORIAL,
        ENCARGADO_AREA,
        FUNCIONARIO,
        ALCALDESA,
    ]

    id_rol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "rol"
        ordering = ["id_rol"]
        verbose_name_plural = "roles"

    def __str__(self):
        return self.nombre


class Auditoria(models.Model):
    """Registro de cada cambio hecho por un mantenedor. Lo llena MantenedorViewSet."""

    id_auditoria = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="auditorias",
    )
    evento = models.CharField(max_length=100)  # crear, editar, desactivar, generar_reporte
    fecha = models.DateTimeField(auto_now_add=True)
    entidad = models.CharField(max_length=100)
    entidad_id = models.IntegerField()
    valor_anterior = models.JSONField(null=True, blank=True)
    valor_nuevo = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "auditoria"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.evento} {self.entidad}#{self.entidad_id}"
