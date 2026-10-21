"""Migración semilla: carga los 6 roles (tabla de solo lectura, sin mantenedor)."""

from django.db import migrations

ROLES = [
    "Administrador",
    "Jefe de delegaciones",
    "Delegado territorial",
    "Encargado de área",
    "Funcionario",
    "Alcaldesa",
]


def cargar_roles(apps, schema_editor):
    Rol = apps.get_model("core", "Rol")
    for nombre in ROLES:
        Rol.objects.get_or_create(nombre=nombre)


def quitar_roles(apps, schema_editor):
    Rol = apps.get_model("core", "Rol")
    Rol.objects.filter(nombre__in=ROLES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(cargar_roles, quitar_roles),
    ]
