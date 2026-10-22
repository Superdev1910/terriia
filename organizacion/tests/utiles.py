"""Ayudas compartidas por las pruebas de organizacion."""

from core.models import Rol
from core.validators import calcular_dv
from personas.models import Usuario


def rut_valido(cuerpo):
    return f"{cuerpo}-{calcular_dv(cuerpo)}"


def crear_usuario(email, cuerpo_rut, rol=Rol.FUNCIONARIO):
    return Usuario.objects.create_user(
        email=email,
        rut=rut_valido(cuerpo_rut),
        password="ClaveSegura#2026",
        rol=Rol.objects.get(nombre=rol),
    )


def crear_admin():
    return crear_usuario("admin@terriia.cl", 11111111, Rol.ADMINISTRADOR)


def crear_funcionario():
    return crear_usuario("func@terriia.cl", 12345678, Rol.FUNCIONARIO)
