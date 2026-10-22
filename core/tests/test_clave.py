"""Pruebas de iniciar sesión, recuperar contraseña y cambiar contraseña."""

import re
from datetime import timedelta

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import CodigoRecuperacion, Rol
from personas.models import Usuario

CLAVE = "Clave-Segura-2026"
NUEVA = "Otra-Clave-Mejor-9"


def crear(email="ana@laserena.cl", rut="12.345.678-5", estado="activo"):
    return Usuario.objects.create_user(
        email=email,
        rut=rut,
        password=CLAVE,
        rol=Rol.objects.get(nombre=Rol.FUNCIONARIO),
        estado=estado,
    )


class BaseClave(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia el freno de intentos entre pruebas
        self.usuario = crear()

    def pedir_codigo(self, email="ana@laserena.cl"):
        r = self.client.post("/api/auth/recuperar/solicitar/", {"email": email}, format="json")
        self.assertEqual(r.status_code, 200)
        return r

    def codigo_del_correo(self):
        return re.search(r"código de verificación es: (\d{6})", mail.outbox[-1].body).group(1)


class LoginTests(BaseClave):
    def login(self, email, clave):
        return self.client.post(
            "/api/auth/login/", {"email": email, "password": clave}, format="json"
        )

    def test_login_correcto(self):
        r = self.login("ana@laserena.cl", CLAVE)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["rol"], Rol.FUNCIONARIO)
        self.assertEqual(self.client.get("/api/auth/yo/").status_code, 200)

    def test_login_ignora_mayusculas_y_espacios_del_correo(self):
        self.assertEqual(self.login("  ANA@laserena.cl ", CLAVE).status_code, 200)

    def test_login_clave_incorrecta(self):
        r = self.login("ana@laserena.cl", "mala")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["error"], "Email o contraseña incorrectos.")

    def test_login_usuario_inactivo_no_entra(self):
        crear("baja@laserena.cl", "11.111.111-1", estado="inactivo")
        self.assertEqual(self.login("baja@laserena.cl", CLAVE).status_code, 400)

    def test_login_datos_faltantes_o_mal_formados(self):
        self.assertEqual(self.login("", "").status_code, 400)
        r = self.client.post("/api/auth/login/", {"email": None, "password": 123}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_login_se_frena_tras_muchos_intentos(self):
        codigos = [self.login("ana@laserena.cl", "mala").status_code for _ in range(12)]
        self.assertIn(429, codigos)


class RecuperarTests(BaseClave):
    def test_flujo_completo_cambia_la_clave(self):
        self.pedir_codigo()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@laserena.cl"])
        codigo = self.codigo_del_correo()

        r = self.client.post(
            "/api/auth/recuperar/verificar/",
            {"email": "ana@laserena.cl", "codigo": codigo},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        r = self.client.post(
            "/api/auth/recuperar/confirmar/",
            {"email": "ana@laserena.cl", "codigo": codigo, "password": NUEVA},
            format="json",
        )
        self.assertEqual(r.status_code, 200)

        self.assertEqual(
            self.client.post(
                "/api/auth/login/", {"email": "ana@laserena.cl", "password": CLAVE}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/login/", {"email": "ana@laserena.cl", "password": NUEVA}, format="json"
            ).status_code,
            200,
        )

    def test_el_codigo_sirve_una_sola_vez(self):
        self.pedir_codigo()
        codigo = self.codigo_del_correo()
        datos = {"email": "ana@laserena.cl", "codigo": codigo, "password": NUEVA}
        self.assertEqual(
            self.client.post("/api/auth/recuperar/confirmar/", datos, format="json").status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/auth/recuperar/confirmar/", datos, format="json").status_code,
            400,
        )

    def test_correo_inexistente_responde_igual_y_no_envia(self):
        r = self.pedir_codigo("nadie@laserena.cl")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_usuario_inactivo_no_recibe_codigo(self):
        crear("baja@laserena.cl", "11.111.111-1", estado="inactivo")
        self.pedir_codigo("baja@laserena.cl")
        self.assertEqual(len(mail.outbox), 0)

    def test_codigo_incorrecto_y_bloqueo_tras_5_errores(self):
        self.pedir_codigo()
        bueno = self.codigo_del_correo()
        malo = "000000" if bueno != "000000" else "111111"
        for _ in range(5):
            r = self.client.post(
                "/api/auth/recuperar/verificar/",
                {"email": "ana@laserena.cl", "codigo": malo},
                format="json",
            )
            self.assertEqual(r.status_code, 400)
        # ya gastó los intentos: ni el código bueno sirve
        r = self.client.post(
            "/api/auth/recuperar/verificar/",
            {"email": "ana@laserena.cl", "codigo": bueno},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_codigo_vencido(self):
        self.pedir_codigo()
        codigo = self.codigo_del_correo()
        CodigoRecuperacion.objects.update(vence=timezone.now() - timedelta(minutes=1))
        r = self.client.post(
            "/api/auth/recuperar/verificar/",
            {"email": "ana@laserena.cl", "codigo": codigo},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_clave_debil_se_rechaza_y_el_codigo_sigue_valido(self):
        self.pedir_codigo()
        codigo = self.codigo_del_correo()
        datos = {"email": "ana@laserena.cl", "codigo": codigo, "password": "12345678"}
        r = self.client.post("/api/auth/recuperar/confirmar/", datos, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "password")
        datos["password"] = NUEVA
        self.assertEqual(
            self.client.post("/api/auth/recuperar/confirmar/", datos, format="json").status_code,
            200,
        )

    def test_el_codigo_no_se_guarda_en_claro(self):
        self.pedir_codigo()
        codigo = self.codigo_del_correo()
        self.assertNotIn(codigo, CodigoRecuperacion.objects.get().huella)

    def test_no_se_reenvia_antes_de_60_segundos(self):
        self.pedir_codigo()
        self.pedir_codigo()
        self.assertEqual(len(mail.outbox), 1)

    def test_un_codigo_nuevo_anula_el_anterior(self):
        self.pedir_codigo()
        viejo = self.codigo_del_correo()
        CodigoRecuperacion.objects.update(creado=timezone.now() - timedelta(minutes=2))
        self.pedir_codigo()
        nuevo = self.codigo_del_correo()
        if viejo != nuevo:
            r = self.client.post(
                "/api/auth/recuperar/verificar/",
                {"email": "ana@laserena.cl", "codigo": viejo},
                format="json",
            )
            self.assertEqual(r.status_code, 400)

    def test_correo_invalido(self):
        r = self.client.post(
            "/api/auth/recuperar/solicitar/", {"email": "sin-arroba"}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "email")


class CambiarClaveTests(BaseClave):
    def test_requiere_sesion(self):
        r = self.client.post(
            "/api/auth/cambiar-clave/", {"actual": CLAVE, "nueva": NUEVA}, format="json"
        )
        self.assertIn(r.status_code, (401, 403))

    def test_cambia_y_mantiene_la_sesion(self):
        self.client.force_login(self.usuario)
        r = self.client.post(
            "/api/auth/cambiar-clave/", {"actual": CLAVE, "nueva": NUEVA}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/yo/").status_code, 200)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(NUEVA))

    def test_clave_actual_incorrecta(self):
        self.client.force_login(self.usuario)
        r = self.client.post(
            "/api/auth/cambiar-clave/", {"actual": "mala", "nueva": NUEVA}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "actual")

    def test_nueva_igual_o_debil(self):
        self.client.force_login(self.usuario)
        igual = self.client.post(
            "/api/auth/cambiar-clave/", {"actual": CLAVE, "nueva": CLAVE}, format="json"
        )
        debil = self.client.post(
            "/api/auth/cambiar-clave/", {"actual": CLAVE, "nueva": "123"}, format="json"
        )
        self.assertEqual((igual.status_code, debil.status_code), (400, 400))
