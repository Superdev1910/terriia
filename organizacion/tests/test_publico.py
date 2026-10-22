"""Pruebas del sitio público de la Municipalidad y de las pantallas de acceso."""

from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from .utiles import crear_admin, crear_funcionario

PUBLICAS = ["pub_inicio", "pub_delegaciones", "pub_servicios", "pub_contacto"]
ACCESO = ["pub_ingresar", "pub_recuperar"]


class SitioPublicoTests(TestCase):
    def test_paginas_publicas_abren_sin_iniciar_sesion(self):
        for nombre in PUBLICAS + ACCESO:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)

    def test_menu_publico_marca_solo_la_pagina_activa(self):
        for nombre in PUBLICAS:
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertEqual(html.count('aria-current="page"'), 1, nombre)
            for destino in PUBLICAS:
                self.assertIn(reverse(destino), html, destino)

    def test_anonimo_ve_ingresar_y_no_hay_registro_publico(self):
        html = self.client.get(reverse("pub_inicio")).content.decode()
        self.assertIn(reverse("pub_ingresar"), html)
        self.assertNotIn("/registro/", html)
        self.assertNotIn("data-cerrar-sesion", html)

    def test_usuario_con_sesion_ve_salir_y_cambiar_clave(self):
        self.client.force_login(crear_funcionario())
        html = self.client.get(reverse("pub_inicio")).content.decode()
        self.assertIn("data-cerrar-sesion", html)
        self.assertIn(reverse("pub_cambiar_clave"), html)
        self.assertNotIn("bi-speedometer2", html)  # el funcionario no ve el botón Panel

    def test_administrador_ve_el_enlace_al_panel(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("pub_inicio")).content.decode()
        self.assertIn("bi-speedometer2", html)  # botón Panel
        self.assertIn('href="/organizacion/"', html)

    def test_directorio_muestra_las_delegaciones(self):
        html = self.client.get(reverse("pub_delegaciones")).content.decode()
        for esperado in [
            "Las Compañías",
            "Carlos E. Rojas Poblete",
            "Información de la Delegación",
        ]:
            self.assertIn(esperado, html, esperado)
        self.assertEqual(html.count('class="tarjeta-del"'), 6)
        self.assertRegex(html, r"leaflet@\d+\.\d+\.\d+")

    def test_mapas_reciben_referer_para_que_openstreetmap_los_entregue(self):
        r = self.client.get(reverse("pub_delegaciones"))
        self.assertEqual(r["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertIn("referrerPolicy", r.content.decode())

    def test_mapa_solo_se_dibuja_con_coordenadas_reales(self):
        html = self.client.get(reverse("pub_delegaciones")).content.decode()
        self.assertEqual(html.count("data-lat="), 6)  # las 6 delegaciones tienen coordenadas
        self.assertEqual(html.count("Ubicación por confirmar"), 0)
        self.assertIn('data-lat="-29.883"', html)  # sin coma decimal (es-CL)

    def test_servicios_y_contacto_traen_su_contenido(self):
        self.assertIn(
            "Registro Social de Hogares", self.client.get(reverse("pub_servicios")).content.decode()
        )
        self.assertIn(
            "lascompanias@laserena.cl", self.client.get(reverse("pub_contacto")).content.decode()
        )

    def test_imagenes_y_estilos_del_sitio_existen(self):
        for ruta in [
            "organizacion/img/playa.jpg",
            "organizacion/img/municipalidad.jpg",
            "organizacion/css/publico.css",
            "organizacion/js/auth.js",
            "organizacion/js/sesion.js",
        ]:
            self.assertIsNotNone(finders.find(ruta), ruta)

    def test_librerias_externas_con_version_fija(self):
        for nombre in PUBLICAS + ACCESO:
            html = self.client.get(reverse(nombre)).content.decode()
            self.assertRegex(html, r"sweetalert2@11\.\d+\.\d+", nombre)
            self.assertRegex(html, r"bootstrap-icons@\d+\.\d+\.\d+", nombre)


class PantallasDeAccesoTests(TestCase):
    def test_ingresar_trae_el_formulario_y_los_enlaces(self):
        html = self.client.get(reverse("pub_ingresar")).content.decode()
        for esperado in [
            'id="formLogin"',
            reverse("pub_recuperar"),
            "data-toggle-clave",
            "auth.js",
        ]:
            self.assertIn(esperado, html, esperado)

    def test_ingresar_pone_la_cookie_csrf(self):
        r = self.client.get(reverse("pub_ingresar"))
        self.assertIn("csrftoken", r.cookies)

    def test_ingresar_solo_acepta_volver_a_paginas_del_mismo_sitio(self):
        ok = self.client.get(reverse("pub_ingresar"), {"next": "/organizacion/areas/"})
        self.assertIn('data-siguiente="/organizacion/areas/"', ok.content.decode())
        for malo in ["https://malo.example/", "//malo.example/", "javascript:alert(1)"]:
            html = self.client.get(reverse("pub_ingresar"), {"next": malo}).content.decode()
            self.assertIn('data-siguiente=""', html, malo)

    def test_iniciar_sesion_con_la_api_de_core_funciona_desde_la_pantalla(self):
        crear_admin()
        r = self.client.post(
            "/api/auth/login/",
            {"email": "admin@terriia.cl", "password": "ClaveSegura#2026"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["rol"], "Administrador")
        self.assertEqual(self.client.get(reverse("org_inicio")).status_code, 200)

    def test_credenciales_malas_devuelven_el_mensaje_que_muestra_la_pantalla(self):
        r = self.client.post(
            "/api/auth/login/",
            {"email": "nadie@terriia.cl", "password": "x"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("incorrectos", r.json()["error"])

    def test_cerrar_sesion_con_la_api_de_core(self):
        self.client.force_login(crear_admin())
        self.assertEqual(self.client.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.client.get(reverse("org_inicio")).status_code, 302)

    def test_paneles_protegidos_mandan_al_nuevo_login(self):
        r = self.client.get(reverse("org_delegaciones"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(reverse("pub_ingresar") + "?next="))

    def test_no_existe_registro_publico(self):
        self.assertEqual(self.client.get("/registro/").status_code, 404)

    def test_recuperar_trae_los_cuatro_pasos_y_el_codigo_de_seis_digitos(self):
        html = self.client.get(reverse("pub_recuperar")).content.decode()
        for paso in range(1, 5):
            self.assertIn(f'data-paso="{paso}"', html)
        self.assertEqual(html.count('class="codigo-celda"'), 6)
        self.assertIn('id="btnReenviar"', html)

    def test_cambiar_clave_pide_iniciar_sesion(self):
        r = self.client.get(reverse("pub_cambiar_clave"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("next=", r["Location"])

    def test_cambiar_clave_con_sesion_muestra_el_formulario(self):
        self.client.force_login(crear_funcionario())
        html = self.client.get(reverse("pub_cambiar_clave")).content.decode()
        self.assertIn('id="formCambiar"', html)
        self.assertIn('id="claveActual"', html)

    def test_panel_trae_boton_salir_y_enlace_al_sitio(self):
        self.client.force_login(crear_admin())
        html = self.client.get(reverse("org_inicio")).content.decode()
        self.assertIn("data-cerrar-sesion", html)
        self.assertIn(reverse("pub_inicio"), html)
        self.assertEqual(html.count('aria-current="page"'), 1)
