"""Pruebas de las pantallas HTML de personas (usuarios y funcionarios). Datos ficticios."""

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from core.models import Rol
from personas.models import Usuario

PANTALLAS = [
    ("personas_usuarios", "usuarios"),
    ("personas_funcionarios", "funcionarios"),
]


def crear_usuario(email, rut, rol):
    return Usuario.objects.create_user(
        email=email, rut=rut, password="ClaveSegura#2026", rol=Rol.objects.get(nombre=rol)
    )


class PantallasPersonasTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario("admin@terriia.cl", "11111111-1", Rol.ADMINISTRADOR)

    def test_anonimo_es_enviado_al_login(self):
        for nombre, _ in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_usuario_sin_rol_administrador_recibe_403(self):
        usuarios = [
            crear_usuario("func@terriia.cl", "12345678-5", Rol.FUNCIONARIO),
            crear_usuario("jefe@terriia.cl", "22222222-2", Rol.JEFE_DELEGACIONES),
        ]
        for usuario in usuarios:
            self.client.force_login(usuario)
            for nombre, _ in PANTALLAS:
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 403, f"{usuario.email} {nombre}")

    def test_administrador_entra_a_las_dos_pantallas(self):
        self.client.force_login(self.admin)
        for nombre, entidad in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertTemplateUsed(r, "personas/mantenedor.html")
            self.assertTemplateUsed(r, "organizacion/base.html")
            esperado = f'<script id="entidad" type="application/json">"{entidad}"</script>'
            self.assertContains(r, esperado, html=False)
            self.assertIn("csrftoken", r.cookies)

    def test_mantenedor_trae_los_controles_exigidos(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("personas_usuarios")).content.decode()
        for esperado in [
            'id="buscar"',
            'id="paginador"',
            'id="tamPagina"',
            'id="cabeceraTabla"',  # el orden por columna se pinta aquí
            "Exportar a Excel",
            "sweetalert2@11.",
            "xlsx@0.18.5",
            'id="formulario"',
            "Campo obligatorio",
            "personas/js/mantenedor.js",
        ]:
            self.assertIn(esperado, html, esperado)
        self.assertIsNotNone(finders.find("personas/js/mantenedor.js"))

    def test_roles_van_en_la_pagina_de_usuarios(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("personas_usuarios"))
        roles = [rol["nombre"] for rol in r.context["roles"]]
        self.assertEqual(roles, Rol.TODOS)
        self.assertContains(r, '<script id="roles" type="application/json">')
        # Su propia cuenta: la pantalla no le ofrece desactivarla.
        actual = f'<script id="idUsuarioActual" type="application/json">{self.admin.pk}</script>'
        self.assertContains(r, actual)
        # La de funcionarios no necesita roles.
        r = self.client.get(reverse("personas_funcionarios"))
        self.assertNotContains(r, '<script id="roles"')

    def test_menu_lateral_igual_en_todas_las_pantallas(self):
        self.client.force_login(self.admin)
        for nombre in ["personas_usuarios", "territorio_vecinos", "org_delegaciones"]:
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertIn('href="/personas/usuarios/"', html, nombre)
            self.assertIn('href="/personas/funcionarios/"', html, nombre)
            self.assertIn('href="/territorio/vecinos/"', html, nombre)
            self.assertIn('href="/organizacion/cargos/"', html, nombre)

    def test_menu_marca_la_pantalla_activa(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("personas_funcionarios")).content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)
        self.assertIn("Personas", html)  # título de la sección del menú
