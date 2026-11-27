import django.db.models.deletion
from django.db import migrations, models


def asignar_delegacion_por_actividad(apps, schema_editor):
    """Cada vecino con actividades toma la delegación del funcionario de su actividad más reciente."""
    Vecino = apps.get_model("territorio", "Vecino")
    Actividad = apps.get_model("atenciones", "Actividad")
    for vecino in Vecino.objects.filter(delegacion__isnull=True):
        ultima = (
            Actividad.objects.filter(vecino_id=vecino.pk, funcionario__delegacion__isnull=False)
            .order_by("-fecha", "-pk")
            .select_related("funcionario")
            .first()
        )
        if ultima is not None:
            vecino.delegacion_id = ultima.funcionario.delegacion_id
            vecino.save(update_fields=["delegacion"])


class Migration(migrations.Migration):

    dependencies = [
        ("organizacion", "0001_initial"),
        ("atenciones", "0003_actividad"),
        ("territorio", "0002_miembro_junta"),
    ]

    operations = [
        migrations.AddField(
            model_name="vecino",
            name="delegacion",
            field=models.ForeignKey(
                blank=True,
                db_column="id_delegacion",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vecinos",
                to="organizacion.delegacion",
            ),
        ),
        migrations.RunPython(asignar_delegacion_por_actividad, migrations.RunPython.noop),
    ]
