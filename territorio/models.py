"""Modelos territoriales alineados con el modelo físico MySQL v2.4."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.validators import validar_rut
from organizacion.models import Delegacion


class Vecino(models.Model):
    ACTIVO, INACTIVO = "activo", "inactivo"
    ESTADOS = [(ACTIVO, "Activo"), (INACTIVO, "Inactivo")]

    id_vecino = models.AutoField(primary_key=True)
    rut = models.CharField(max_length=12, unique=True, validators=[validar_rut])
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20, blank=True, default="")
    direccion = models.CharField(max_length=255, blank=True, default="")
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ACTIVO)
    delegacion = models.ForeignKey(
        Delegacion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_delegacion",
        related_name="vecinos",
    )

    class Meta:
        db_table = "vecino"
        ordering = ["apellidos", "nombres"]

    def __str__(self):
        return f"{self.nombres} {self.apellidos} ({self.rut})"


class Territorio(models.Model):
    ACTIVO, INACTIVO = "activo", "inactivo"
    ESTADOS = [(ACTIVO, "Activo"), (INACTIVO, "Inactivo")]

    id_territorio = models.AutoField(primary_key=True)
    delegacion = models.ForeignKey(
        Delegacion,
        on_delete=models.PROTECT,
        db_column="id_delegacion",
        related_name="territorios",
    )
    nombre = models.CharField(max_length=150)
    es_formal = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "territorio"
        ordering = ["delegacion__codigo", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["delegacion", "nombre"], name="uq_territorio_delegacion_nombre"
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.delegacion.codigo})"


class JuntaVecinos(models.Model):
    ACTIVA, INACTIVA = "activa", "inactiva"
    ESTADOS = [(ACTIVA, "Activa"), (INACTIVA, "Inactiva")]

    id_junta_vecinos = models.AutoField(primary_key=True)
    territorio = models.ForeignKey(
        Territorio,
        on_delete=models.PROTECT,
        db_column="id_territorio",
        related_name="juntas_vecinos",
    )
    numero_registro = models.CharField(max_length=30, unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=150)
    direccion = models.CharField(max_length=255, blank=True, default="")
    presidente = models.CharField(max_length=150, blank=True, default="")
    telefono = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(max_length=150, blank=True, default="")
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = "junta_vecinos"
        ordering = ["numero_registro"]

    def __str__(self):
        return f"{self.numero_registro} · {self.nombre}"


class MiembroJunta(models.Model):
    """Membresía de un vecino en una junta (incluye la dirigencia mediante el cargo).

    Las dos FK son PROTECT como en el resto del proyecto: juntas y vecinos se desactivan,
    no se borran, y así no se pierde el historial de membresías.
    MariaDB 10.5 (servidor) no soporta UniqueConstraint con condition, por eso las reglas
    de unicidad de membresías activas se validan en clean() y en el serializer.
    """

    ACTIVO, INACTIVO = "activo", "inactivo"
    ESTADOS = [(ACTIVO, "Activo"), (INACTIVO, "Inactivo")]
    SOCIO, PRESIDENTE, VICEPRESIDENTE = "socio", "presidente", "vicepresidente"
    SECRETARIO, TESORERO, DIRECTOR = "secretario", "tesorero", "director"
    CARGOS = [
        (SOCIO, "Socio"),
        (PRESIDENTE, "Presidente"),
        (VICEPRESIDENTE, "Vicepresidente"),
        (SECRETARIO, "Secretario"),
        (TESORERO, "Tesorero"),
        (DIRECTOR, "Director"),
    ]
    CARGOS_UNICOS = (PRESIDENTE, VICEPRESIDENTE, SECRETARIO, TESORERO)

    id_miembro_junta = models.AutoField(primary_key=True)
    junta = models.ForeignKey(
        JuntaVecinos,
        on_delete=models.PROTECT,
        db_column="id_junta_vecinos",
        related_name="miembros",
    )
    vecino = models.ForeignKey(
        Vecino,
        on_delete=models.PROTECT,
        db_column="id_vecino",
        related_name="membresias",
    )
    cargo = models.CharField(max_length=15, choices=CARGOS, default=SOCIO)
    fecha_ingreso = models.DateField(default=timezone.localdate)
    fecha_salida = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ACTIVO)

    class Meta:
        db_table = "miembro_junta"
        ordering = ["junta_id", "-estado", "vecino__apellidos", "vecino__nombres"]
        indexes = [models.Index(fields=["junta", "estado"], name="ix_miembro_junta_estado")]

    def __str__(self):
        return f"{self.vecino} · {self.get_cargo_display()} ({self.junta})"

    def errores_reglas(self):
        """Devuelve {campo: mensaje} con las reglas de negocio incumplidas."""
        errores = {}
        if self.fecha_ingreso and self.fecha_salida and self.fecha_salida < self.fecha_ingreso:
            errores["fecha_salida"] = "La fecha de salida no puede ser anterior a la de ingreso."
        if self.estado == self.INACTIVO and not self.fecha_salida:
            errores["fecha_salida"] = "Un miembro inactivo requiere fecha de salida."
        if self.estado != self.ACTIVO:
            return errores
        if self.vecino_id and self.vecino.estado != Vecino.ACTIVO:
            errores["vecino"] = "Solo se puede agregar a un vecino activo."
        otros = MiembroJunta.objects.filter(junta_id=self.junta_id, estado=self.ACTIVO)
        if self.pk:
            otros = otros.exclude(pk=self.pk)
        if otros.filter(vecino_id=self.vecino_id).exists():
            errores["vecino"] = "El vecino ya es miembro activo de esta junta."
        if self.cargo in self.CARGOS_UNICOS and otros.filter(cargo=self.cargo).exists():
            errores["cargo"] = f"La junta ya tiene un {self.get_cargo_display().lower()} activo."
        return errores

    def clean(self):
        errores = self.errores_reglas()
        if errores:
            raise ValidationError(errores)
