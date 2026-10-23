# Valentina: periodo, item (SCRUM-22 HU09, SCRUM-32 HU29).
# Fernando: meta_delegacion, meta (SCRUM-25 HU12). Ver README.
from django.db import models
from django.conf import settings
from organizacion.models import Delegacion, Cargo
from django.utils import timezone


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


class MetaDelegacion(models.Model):
    id_meta_delegacion = models.AutoField(primary_key=True)
    item = models.ForeignKey(
        Item, on_delete=models.PROTECT, db_column="id_item", related_name="metas_delegacion"
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion",
        on_delete=models.PROTECT,
        db_column="id_delegacion",
        related_name="metas_delegacion",
    )
    periodo = models.ForeignKey(
        Periodo, on_delete=models.PROTECT, db_column="id_periodo", related_name="metas_delegacion"
    )
    valor_objetivo_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "meta_delegacion"
        ordering = ["-periodo", "delegacion", "item"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "delegacion", "periodo"], name="uq_meta_delegacion"
            )
        ]

    def __str__(self):
        return f"{self.item.nombre} · {self.delegacion.nombre} · período {self.periodo_id}"


class MetaIndividual(models.Model):
    id_meta = models.AutoField(primary_key=True)
    meta_delegacion = models.ForeignKey(
        MetaDelegacion,
        on_delete=models.PROTECT,
        db_column="id_meta_delegacion",
        related_name="metas_individuales",
    )
    funcionario = models.ForeignKey(
        "personas.Funcionario",
        on_delete=models.PROTECT,
        db_column="id_funcionario",
        related_name="metas",
    )
    valor_objetivo = models.DecimalField(max_digits=10, decimal_places=2)
    unidad = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = "meta"
        ordering = ["meta_delegacion", "funcionario"]
        constraints = [
            models.UniqueConstraint(
                fields=["meta_delegacion", "funcionario"], name="uq_meta_funcionario"
            )
        ]

    def __str__(self):
        return f"Meta {self.id_meta} · funcionario {self.funcionario_id}"


class RecalibracionMeta(models.Model):

    id_recalibracion = models.AutoField(primary_key=True)
    meta = models.ForeignKey(
        MetaIndividual,
        on_delete=models.PROTECT,
        db_column="id_meta",
        related_name="recalibraciones",
    )
    valor_objetivo_anterior = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    valor_objetivo_nuevo = models.DecimalField(max_digits=10, decimal_places=2)
    motivo = models.CharField(max_length=255)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        db_column="usuario_id",
        related_name="recalibraciones_meta",
    )
    fecha = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        db_table = "recalibracion_meta"
        ordering = ["-fecha", "-id_recalibracion"]

    def __str__(self):
        return f"Recalibración {self.id_recalibracion} de la meta {self.meta_id}"
