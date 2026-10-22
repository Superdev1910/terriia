"""Modelos territoriales alineados con el modelo físico MySQL v2.4."""

from django.db import models

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
