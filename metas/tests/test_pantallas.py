"""Pruebas de acceso a las pantallas HTML de metas (períodos, ítems y metas)."""

from django.test import TestCase
from django.urls import reverse

from core.models import Rol
from personas.models import Usuario

PANTALLAS = [
    ("metas_periodos", "periodos"),
    ("metas_items", "items"),
    ("metas_delegacion", "metas-delegacion"),
    ("metas_individuales", "metas"),
]


def crear_usuario(email, rut, rol):
    return Usuario.objects.create_user(
        email=email, rut=rut, password="ClaveSegura#2026", rol=Rol.objects.get(nombre=rol)
    )


class PantallasMetasTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario("admin@terriia.cl", "11.111.111-1", Rol.ADMINISTRADOR)
        self.funcionario = crear_usuario("func@terriia.cl", "12.345.678-5", Rol.FUNCIONARIO)

    def test_administrador_ve_cada_pantalla(self):
        self.client.force_login(self.admin)
        for nombre, entidad in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertTemplateUsed(r, "metas/mantenedor.html")
            esperado = f'<script id="entidad" type="application/json">"{entidad}"</script>'
            self.assertContains(r, esperado)

    def test_no_administrador_recibe_403(self):
        self.client.force_login(self.funcionario)
        for nombre, _ in PANTALLAS:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_anonimo_es_enviado_al_login(self):
        for nombre, _ in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_pantalla_trae_busqueda_paginador_excel_y_sweetalert(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("metas_items")).content.decode()
        for esperado in [
            'id="buscar"',
            'id="paginador"',
            "Exportar a Excel",
            "xlsx",
            "sweetalert2",
        ]:
            self.assertIn(esperado, html, esperado)

    def test_menu_lateral_lleva_a_metas_desde_todas_las_pantallas(self):
        self.client.force_login(self.admin)
        metas = self.client.get(reverse("metas_periodos")).content.decode()
        territorio = self.client.get(reverse("territorio_vecinos")).content.decode()
        organizacion = self.client.get(reverse("org_cargos")).content.decode()
        for html in (metas, territorio, organizacion):
            for nombre, _ in PANTALLAS:
                self.assertIn(f'href="{reverse(nombre)}"', html, nombre)
            self.assertIn(f'href="{reverse("org_cargos")}"', html)
        self.assertEqual(metas.count('aria-current="page"'), 1)
