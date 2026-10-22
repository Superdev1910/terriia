# Valentina: periodo, item (SCRUM-22 HU09, SCRUM-32 HU29).
# Fernando: meta_delegacion, meta (SCRUM-25 HU12). Ver README.
from django.db import models  # noqa: F401


class Periodo(models.Model):
    ESTADO_CHOICES = [
        ("vigente", "Vigente"),
        ("cerrado", "Cerrado"),
        ("programado", "Programado"),
    ]

    id_periodo = models.AutoField(primary_key=True)
    fecha_inicio = models.DateField()
    fecha_termino = models.DateField()
    dias_computables = models.IntegerField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="programado")
    version_parametros = models.CharField(max_length=20)

    class Meta:
        db_table = "periodo"

    def __str__(self):
        return f"Período {self.id_periodo} ({self.fecha_inicio} a {self.fecha_termino})"
