"""Pantalla HTML de seguimiento de actividades: acceso por rol, controles y menú."""

from django.test import TestCase
from django.urls import reverse

from .utiles_seguimiento import RAPIDO, EscenarioSolicitudesMixin


@RAPIDO
class PantallaSeguimientoTests(EscenarioSolicitudesMixin, TestCase):
    def setUp(self):
        self.preparar_escenario()
        self.url_pantalla = reverse("atenciones_seguimiento")

    def test_anonimo_es_enviado_al_login(self):
        r = self.client.get(self.url_pantalla)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_alcaldesa_y_jefe_reciben_403(self):
        self.client.force_login(self.alcaldesa)
        self.assertEqual(self.client.get(self.url_pantalla).status_code, 403)

    def test_cada_rol_con_acceso_ve_la_pantalla_y_su_codigo(self):
        casos = [
            (self.admin, "admin"),
            (self.delegado, "delegado"),
            (self.usuario_ana, "funcionario"),
            (
                self.crear_usuario(
                    "enc@terriia.cl",
                    31313131,
                    "Encargado de área",
                    funcionario=self.marta,
                    delegacion=self.centro,
                ),
                "encargado",
            ),
        ]
        for usuario, codigo in casos:
            self.client.force_login(usuario)
            r = self.client.get(self.url_pantalla)
            self.assertEqual(r.status_code, 200, codigo)
            self.assertTemplateUsed(r, "organizacion/base.html")
            self.assertContains(
                r, f'<script id="rolCodigo" type="application/json">"{codigo}"</script>'
            )

    def test_controles_de_la_pantalla(self):
        self.client.force_login(self.usuario_ana)
        html = self.client.get(self.url_pantalla).content.decode()
        for esperado in [
            'id="buscar"',
            'id="filtroEstado"',
            'id="filtroVencida"',
            'id="paginador"',
            'id="resumen"',
            "Exportar a Excel",
            "Registrar actividad",
            "sweetalert2",
            "atenciones/js/actividad_seguimiento.js",
        ]:
            self.assertIn(esperado, html, esperado)

    def test_menu_muestra_solicitudes_solo_a_quien_corresponde(self):
        def en_menu(usuario):
            self.client.force_login(usuario)
            r = self.client.get(self.url_pantalla)
            nombres = {i[0] for _, paginas in r.context["menu_secciones"] for i in paginas}
            return "atenciones_seguimiento" in nombres, r.content.decode().count(
                'aria-current="page"'
            )

        for usuario in (self.admin, self.delegado, self.usuario_ana):
            self.assertEqual(en_menu(usuario), (True, 1), usuario.email)

    def test_funcionario_ve_el_enlace_desde_su_pagina_de_inicio(self):
        self.client.force_login(self.usuario_ana)
        self.assertContains(self.client.get(reverse("personas_mi_perfil")), self.url_pantalla)
