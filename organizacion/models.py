# Brian: delegacion, area, cargo (SCRUM-13 HU17). Ver README "Estándar de codificación".
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction


class Delegacion(models.Model):
    """Tabla `delegacion`. Al crearla se generan sus 4 áreas (HU17)."""

    ACTIVA, INACTIVA = "activa", "inactiva"
    ESTADOS = [(ACTIVA, "Activa"), (INACTIVA, "Inactiva")]

    id_delegacion = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=10, unique=True)
    nombre = models.CharField(max_length=100, unique=True)
    direccion = models.CharField(max_length=200, blank=True, default="")
    comuna = models.CharField(max_length=80, default="La Serena")
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ACTIVA)

    class Meta:
        db_table = "delegacion"
        ordering = ["codigo"]
        verbose_name_plural = "delegaciones"

    def save(self, *args, **kwargs):
        """HU17: al crear una delegación nacen sus 4 áreas (también desde admin o semillas)."""
        nueva = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if nueva:
                for prioridad, (tipo, _) in enumerate(Area.TIPOS, start=1):
                    Area.objects.create(delegacion=self, tipo=tipo, prioridad=prioridad)

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Area(models.Model):
    """Tabla `area`. Una sola área de cada tipo por delegación; prioridad 1 a 4 sin repetir."""

    SOCIAL, TERRITORIAL, ADMINISTRATIVA, OPERATIVA = (
        "social",
        "territorial",
        "administrativa",
        "operativa",
    )
    # SUPUESTO: los 4 tipos no están en los documentos; confirmar con el SQL v2.3.
    TIPOS = [
        (SOCIAL, "Social"),
        (TERRITORIAL, "Territorial"),
        (ADMINISTRATIVA, "Administrativa"),
        (OPERATIVA, "Operativa"),
    ]
    ACTIVA, INACTIVA = "activa", "inactiva"
    ESTADOS = [(ACTIVA, "Activa"), (INACTIVA, "Inactiva")]

    id_area = models.AutoField(primary_key=True)
    delegacion = models.ForeignKey(
        Delegacion,
        on_delete=models.PROTECT,
        db_column="id_delegacion",
        related_name="areas",
    )
    tipo = models.CharField(max_length=15, choices=TIPOS)
    prioridad = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)]
    )
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ACTIVA)

    class Meta:
        db_table = "area"
        ordering = ["delegacion", "prioridad"]
        constraints = [
            models.UniqueConstraint(fields=["delegacion", "tipo"], name="uq_area_delegacion_tipo"),
            models.UniqueConstraint(
                fields=["delegacion", "prioridad"], name="uq_area_delegacion_prioridad"
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.delegacion.codigo})"


class Cargo(models.Model):
    """Tabla `cargo`. Sin área (id_area NULL) = cargo transversal."""

    id_cargo = models.AutoField(primary_key=True)
    area = models.ForeignKey(
        Area,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_area",
        related_name="cargos",
    )
    nombre = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=255, blank=True, default="")
    vigente = models.BooleanField(default=True)

    class Meta:
        db_table = "cargo"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["area", "nombre"], name="uq_cargo_area_nombre"),
        ]

    def __str__(self):
        return self.nombre
