"""Migración semilla: tipos de atención ficticios del área Social y una sub atención.

Datos de ejemplo para la demo (reunión 28-08, guía SGR §8.1). Se puede revertir con
`python manage.py migrate atenciones 0001`: solo borra lo que cargó esta semilla.
"""

from django.db import migrations

AREA = "Social"
TIPOS = ["Informe social", "Gestión de subsidio", "Derivación", "Otras gestiones"]
SUB_ATENCIONES = {"Otras gestiones": ["Orientación social"]}


def cargar_semilla(apps, schema_editor):
    TipoAtencion = apps.get_model("atenciones", "TipoAtencion")
    SubAtencion = apps.get_model("atenciones", "SubAtencion")
    for nombre in TIPOS:
        tipo, _ = TipoAtencion.objects.get_or_create(area=AREA, nombre=nombre)
        for sub in SUB_ATENCIONES.get(nombre, []):
            SubAtencion.objects.get_or_create(tipo_atencion=tipo, nombre=sub)


def quitar_semilla(apps, schema_editor):
    TipoAtencion = apps.get_model("atenciones", "TipoAtencion")
    SubAtencion = apps.get_model("atenciones", "SubAtencion")
    for tipo, subs in SUB_ATENCIONES.items():
        SubAtencion.objects.filter(
            tipo_atencion__area=AREA, tipo_atencion__nombre=tipo, nombre__in=subs
        ).delete()
    # Un tipo que ya tenga otras sub atenciones queda (PROTECT); solo se quitan los vacíos.
    TipoAtencion.objects.filter(area=AREA, nombre__in=TIPOS, sub_atenciones__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("atenciones", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(cargar_semilla, quitar_semilla),
    ]
