"""Catálogos de atención (SCRUM-61, modelo físico v2.5).

Cada área ofrece sus tipos de atención y cada tipo se divide en sub atenciones. La actividad
(T5) apunta a ambos con id_tipo_atencion e id_sub_atencion.
"""

from django.db import models

from organizacion.models import Area


class TipoAtencion(models.Model):
    """Tabla `tipo_atencion`. El nombre no se repite dentro del área (sin importar mayúsculas)."""

    id_tipo_atencion = models.AutoField(primary_key=True)
    # Mismas 4 áreas del ENUM de area.nombre: se reutiliza la lista de organizacion.
    area = models.CharField(max_length=30, choices=Area.NOMBRES)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "tipo_atencion"
        ordering = ["area", "nombre"]
        verbose_name = "tipo de atención"
        verbose_name_plural = "tipos de atención"
        # Las mayúsculas se revisan en el serializer: MariaDB 10.5 no admite índices con
        # Lower("nombre") (Django lo omitiría) y su cotejamiento utf8mb4_unicode_ci ya las ignora.
        constraints = [
            models.UniqueConstraint(fields=["area", "nombre"], name="uq_tipo_atencion_area_nombre")
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_area_display()})"


class SubAtencion(models.Model):
    """Tabla `sub_atencion`. Solo se crea bajo un tipo de atención activo."""

    id_sub_atencion = models.AutoField(primary_key=True)
    tipo_atencion = models.ForeignKey(
        TipoAtencion,
        on_delete=models.PROTECT,
        db_column="id_tipo_atencion",
        related_name="sub_atenciones",
    )
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "sub_atencion"
        ordering = ["tipo_atencion__area", "tipo_atencion__nombre", "nombre"]
        verbose_name = "sub atención"
        verbose_name_plural = "sub atenciones"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_atencion", "nombre"], name="uq_sub_atencion_tipo_nombre"
            )
        ]

    def __str__(self):
        return f"{self.nombre} · {self.tipo_atencion.nombre}"
