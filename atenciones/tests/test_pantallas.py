"""Pruebas de las pantallas HTML de tipos de atención y sub atenciones."""

from django.test import TestCase
from django.urls import reverse

from .utiles import crear_admin, crear_funcionario

PANTALLAS = [
    ("atenciones_tipos", "tipos-atencion"),
    ("atenciones_sub_atenciones", "sub-atenciones"),
]


class PantallasAtencionesTests(TestCase):
    def test_anonimo_es_enviado_al_login(self):
        for nombre, _ in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_no_administrador_recibe_403(self):
        self.client.force_login(crear_funcionario())
        for nombre, _ in PANTALLAS:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_administrador_ve_las_pantallas(self):
        self.client.force_login(crear_admin())
        for nombre, entidad in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertTemplateUsed(r, "organizacion/base.html")
            html = r.content.decode()
            self.assertIn(
                f'<script id="entidad" type="application/json">"{entidad}"</script>', html
            )
            for esperado in [
                'id="buscar"',
                'id="filtroArea"',
                'id="paginador"',
                "Exportar a Excel",
                "sweetalert2",
                "Organizacion Comunitaria",  # las áreas salen de organizacion.Area.NOMBRES
            ]:
                self.assertIn(esperado, html, f"{nombre}: {esperado}")

    def test_solo_sub_atenciones_filtra_por_tipo(self):
        self.client.force_login(crear_admin())
        self.assertNotIn(
            'id="filtroTipo"', self.client.get(reverse(PANTALLAS[0][0])).content.decode()
        )
        self.assertIn('id="filtroTipo"', self.client.get(reverse(PANTALLAS[1][0])).content.decode())

    def test_menu_igual_en_organizacion_territorio_y_atenciones(self):
        self.client.force_login(crear_admin())
        for pantalla in ["org_delegaciones", "territorio_vecinos", "atenciones_tipos"]:
            html = self.client.get(reverse(pantalla)).content.decode()
            for nombre, _ in PANTALLAS:
                self.assertIn(f'href="{reverse(nombre)}"', html, f"{pantalla}: {nombre}")
        html = self.client.get(reverse("atenciones_sub_atenciones")).content.decode()
        self.assertEqual(html.count('aria-current="page"'), 1)
