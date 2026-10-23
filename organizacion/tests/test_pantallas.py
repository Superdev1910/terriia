"""Pruebas funcionales por pantalla de organizacion (HTML de los 3 mantenedores)."""

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from organizacion.models import Delegacion

from .utiles import crear_admin, crear_funcionario

PANTALLAS = [
    ("org_inicio", "Organización"),
    ("org_delegaciones", "delegaciones"),
    ("org_areas", "areas"),
    ("org_cargos", "cargos"),
]


class PantallasOrganizacionTests(TestCase):
    def test_anonimo_es_enviado_al_login(self):
        for nombre, _ in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertIn("next=", r["Location"])

    def test_funcionario_recibe_403(self):
        self.client.force_login(crear_funcionario())
        for nombre, _ in PANTALLAS:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_administrador_ve_las_cuatro_pantallas(self):
        self.client.force_login(crear_admin())
        for nombre, _ in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertTemplateUsed(r, "organizacion/base.html")

    def test_cabecera_muestra_contexto_usuario_y_rol(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_delegaciones")).content.decode()
        self.assertIn("Municipalidad de La Serena", html)
        self.assertIn("Administrador", html)  # rol
        self.assertIn("admin@terriia.cl", html)  # nombre de usuario (sin nombre cargado)
        self.assertIn("Acceso global", html)  # distintivo con texto (no solo color)

    def test_cabecera_muestra_delegacion_del_usuario(self):
        admin = crear_admin()
        admin.delegacion = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        admin.save()
        self.client.force_login(admin)
        html = self.client.get(reverse("org_delegaciones")).content.decode()
        self.assertIn("CEN · Centro", html)
        self.assertNotIn("Acceso global", html)

    def test_mantenedor_trae_los_controles_exigidos(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_cargos")).content.decode()
        for esperado in [
            'id="buscar"',  # búsqueda
            "Exportar a Excel",
            'id="paginador"',
            'id="total"',
            "sweetalert2",
            'id="formulario"',
            "Campo obligatorio",
            "Saltar al contenido",
        ]:
            self.assertIn(esperado, html, esperado)

    def test_entidad_correcta_en_cada_pantalla(self):
        self.client.force_login(crear_admin())
        for nombre, entidad in PANTALLAS[1:]:
            html = self.client.get(reverse(nombre)).content.decode()
            esperado = f'<script id="entidad" type="application/json">"{entidad}"</script>'
            self.assertIn(esperado, html)

    def test_menu_marca_la_pantalla_activa(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_areas")).content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)

    def test_identidad_visual_municipal(self):
        css = finders.find("organizacion/css/terriia.css")
        self.assertIsNotNone(css)
        texto = open(css, encoding="utf-8").read().lower()
        self.assertIn("#ad0000", texto)  # rojo institucional
        self.assertIn("arial", texto)  # tipografía de las normas gráficas
        self.assertIsNotNone(finders.find("organizacion/js/mantenedor.js"))

    def test_inicio_trae_las_cifras_y_el_script(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_inicio")).content.decode()
        for esperado in ["cifrasDelegaciones", "cifrasAreas", "cifrasCargos", "inicio.js"]:
            self.assertIn(esperado, html, esperado)
        self.assertIsNotNone(finders.find("organizacion/js/inicio.js"))

    def test_mantenedor_trae_orden_tamano_de_pagina_y_panel_de_detalle(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_delegaciones")).content.decode()
        for esperado in [
            'id="tamPagina"',
            'id="panelDetalle"',
            'role="dialog"',
            'aria-modal="true"',
        ]:
            self.assertIn(esperado, html, esperado)

    def test_librerias_externas_con_version_fija(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_delegaciones")).content.decode()
        self.assertNotIn('sweetalert2@11"', html)  # sin versión fija
        self.assertRegex(html, r"sweetalert2@11\.\d+\.\d+")
        self.assertRegex(html, r"bootstrap-icons@\d+\.\d+\.\d+")
        self.assertRegex(html, r"xlsx@\d+\.\d+\.\d+")
