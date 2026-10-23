from django.conf import settings
from django.db import models


class Rol(models.Model):
    """
    Tabla `rol`. Los 6 roles del sistema (TODOS) se cargan con la migración semilla
    (core/migrations/0003) y los permisos los usan por nombre: se puede editar su descripción,
    pero no renombrarlos ni desactivarlos (lo valida RolSerializer).
    Los roles nuevos se crean, editan y desactivan en el mantenedor /api/roles/.
    """

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
    descripcion = models.CharField(max_length=255, blank=True, default="")
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "rol"
        ordering = ["id_rol"]
        verbose_name_plural = "roles"

    @property
    def es_del_sistema(self):
        return self.nombre in self.TODOS

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


class CodigoRecuperacion(models.Model):
    """Código de 6 dígitos para recuperar la contraseña. Solo se guarda su huella, nunca el código."""

    id_codigo = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="id_usuario",
        related_name="codigos_recuperacion",
    )
    huella = models.CharField(max_length=64)
    creado = models.DateTimeField(auto_now_add=True)
    vence = models.DateTimeField()
    intentos = models.PositiveSmallIntegerField(default=0)
    usado = models.BooleanField(default=False)

    class Meta:
        db_table = "codigo_recuperacion"
        ordering = ["-creado"]
