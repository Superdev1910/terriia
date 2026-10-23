# Valentina: periodo, item (SCRUM-22 HU09, SCRUM-32 HU29).
# Fernando: meta_delegacion, meta (SCRUM-25 HU12). Ver README.
from django.db import models
from organizacion.models import Cargo


class Periodo(models.Model):
    """Tabla `periodo` (SQL v2.4). Solo un periodo vigente a la vez."""

    VIGENTE, CERRADO = "vigente", "cerrado"
    ESTADO_CHOICES = [(VIGENTE, "Vigente"), (CERRADO, "Cerrado")]

    id_periodo = models.AutoField(primary_key=True)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField()
    dias_computables = models.IntegerField(null=True, blank=True)
    estado = models.CharField(max_length=7, choices=ESTADO_CHOICES, default=VIGENTE)
    version_parametros = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "periodo"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Período {self.id_periodo} ({self.fecha_inicio} a {self.fecha_termino})"


class Item(models.Model):
    """Tabla `item` (SQL v2.4). Incluye configuración de verificación previa (HU29)."""

    CONTEO, PORCENTAJE = "conteo", "porcentaje"
    TIPO_META_CHOICES = [
        (CONTEO, "Conteo"),
        (PORCENTAJE, "Porcentaje"),
    ]

    id_item = models.AutoField(primary_key=True)
    cargo = models.ForeignKey(
        Cargo,
        on_delete=models.PROTECT,
        db_column="id_cargo",
        related_name="items",
    )
    nombre = models.CharField(max_length=150)
    tipo_meta = models.CharField(max_length=15, choices=TIPO_META_CHOICES, default=CONTEO)
    ponderador = models.DecimalField(max_digits=5, decimal_places=2)
    activo = models.BooleanField(default=True)
    requiere_verificacion_previa = models.BooleanField(default=False)
    radio_tolerancia_metros = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "item"
        ordering = ["cargo", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.cargo.nombre})"
