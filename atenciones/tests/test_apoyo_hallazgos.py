"""Pruebas de apoyo (sin código CP) de las revisiones de SCRUM-62, SCRUM-123 y SCRUM-60.

Cubren casos negativos y de seguridad: alcance global por rol, verificación, evidencias, búsqueda
de vecinos, admin de Django y configuración. Solo datos ficticios.
"""

import os
import runpy
from pathlib import Path
from unittest import mock

from django.contrib import admin
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from rest_framework import status

from core.models import Auditoria, Rol
from personas.models import Funcionario, Usuario

from ..admin import ActividadAdmin
from ..models import Actividad, Evidencia
from .test_actividad import URL, hora
from .test_verificacion import PNG, VerificacionBase, archivo_png

SETTINGS = Path(__file__).resolve().parents[2] / "config" / "settings.py"


class AlcanceGlobalPorRolTests(VerificacionBase):
    """Apoyo H07: la delegación vacía no da acceso global a Delegado, Encargado ni Funcionario."""

    def sin_delegacion(self, usuario):
        usuario.delegacion = None
        usuario.save()
        return usuario

    def test_delegado_encargado_y_funcionario_sin_delegacion_no_ven_nada(self):
        for usuario in (self.delegado_a, self.encargado_a, self.user_a):
            self.sin_delegacion(usuario)
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(URL).status_code, 403, usuario.rol)
            self.assertEqual(self.client.get("/api/evidencias/").status_code, 403)
            self.assertEqual(self.client.get("/api/vecinos/buscar/?rut=1-9").status_code, 403)

    def test_verificador_con_delegacion_nula_no_verifica(self):
        self.sin_delegacion(self.delegado_a)
        self.assertEqual(self.verificar(self.delegado_a, "aprobar").status_code, 403)
        self.assertEqual(self.estado(), "pendiente")

    def test_alcaldesa_y_superusuario_ven_todo(self):
        self.crear_en_bd(self.func_b, hora(18, 9))
        alcaldesa = self.crear_global("alcaldesa", Rol.ALCALDESA)
        super_usuario = Usuario.objects.create_superuser(
            email="super.apoyo@terriia.cl", rut=self.nuevo_rut(), password="PruebaSegura123!"
        )
        for usuario in (alcaldesa, super_usuario):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(URL).data["count"], 2)

    def test_alcaldesa_no_verifica_ni_sube_evidencias(self):
        alcaldesa = self.crear_global("alcaldesa", Rol.ALCALDESA)
        self.assertEqual(self.verificar(alcaldesa, "aprobar").status_code, 403)
        self.assertEqual(self.subir(alcaldesa).status_code, 403)


class VerificacionNegativasTests(VerificacionBase):
    """Apoyo: entradas inválidas y transiciones no permitidas."""

    def test_accion_invalida_o_ausente_da_400(self):
        for accion in ("borrar", "", None, 5):
            r = self.verificar(self.delegado_a, accion)
            self.assertEqual(r.status_code, 400, accion)
        self.assertEqual(self.estado(), "pendiente")

    def test_observacion_que_no_es_texto_da_400(self):
        self.client.force_authenticate(self.delegado_a)
        for valor in (123, ["a"], {"x": 1}):
            r = self.client.post(
                f"{URL}{self.actividad.pk}/verificar/",
                {"accion": "aprobar", "observacion": valor},
                format="json",
            )
            self.assertEqual(r.status_code, 400, valor)
            self.assertEqual(r.data["campo"], "observacion")

    def test_antecedentes_no_pasa_directo_a_aprobada(self):
        self.verificar(self.delegado_a, "antecedentes", "Falta el acta")
        self.assertEqual(self.verificar(self.delegado_a, "aprobar").status_code, 409)
        self.assertEqual(self.estado(), "antecedentes")

    def test_edicion_por_no_autor_de_la_misma_delegacion_da_403(self):
        for usuario in (self.otro_func_a, self.delegado_a, self.encargado_a):
            self.assertEqual(self.editar(usuario, descripcion="x").status_code, 403)

    def test_historial_de_otra_delegacion_no_se_lee(self):
        self.client.force_authenticate(self.delegado_b)
        self.assertEqual(self.client.get(f"{URL}{self.actividad.pk}/historial/").status_code, 404)

    def test_funcionario_sin_ficha_activa_no_crea_ni_edita(self):
        self.func_a.estado = Funcionario.INACTIVO
        self.func_a.save()
        self.client.force_authenticate(self.user_a)
        r = self.client.post(URL, self.datos(), format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.editar(self.user_a, descripcion="x").status_code, 403)


class EvidenciasNegativasTests(VerificacionBase):
    """Apoyo: quién puede subir, tamaño, tope y nombre de descarga."""

    def test_delegado_de_otra_delegacion_no_sube(self):
        self.assertEqual(self.subir(self.delegado_b).status_code, 403)

    def test_otro_funcionario_no_sube_ni_borra(self):
        self.assertEqual(self.subir(self.otro_func_a).status_code, 403)
        evidencia = self.subir(self.user_a).data
        self.client.force_authenticate(self.otro_func_a)
        r = self.client.delete(f"/api/evidencias/{evidencia['id_evidencia']}/")
        self.assertEqual(r.status_code, 403)

    def test_archivo_vacio_da_400(self):
        vacio = SimpleUploadedFile("vacio.png", b"", content_type="image/png")
        r = self.subir(self.user_a, vacio)
        self.assertEqual(r.status_code, 400)

    @override_settings(EVIDENCIAS_MAX_POR_ACTIVIDAD=2)
    def test_tope_de_evidencias_por_actividad(self):
        self.assertEqual(self.subir(self.user_a).status_code, 201)
        self.assertEqual(self.subir(self.user_a).status_code, 201)
        r = self.subir(self.user_a)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "actividad")
        self.assertEqual(Evidencia.objects.count(), 2)

    def test_descarga_no_usa_el_nombre_original(self):
        raro = SimpleUploadedFile('x";\r\nSet-Cookie: a=b.png', PNG, content_type="image/png")
        evidencia = self.subir(self.user_a, raro).data
        self.client.force_authenticate(self.user_a)
        r = self.client.get(f"/api/evidencias/{evidencia['id_evidencia']}/archivo/")
        self.assertEqual(r.status_code, 200)
        codigo = evidencia["codigo_verificador"]
        self.assertEqual(r["Content-Disposition"], f'attachment; filename="{codigo}.png"')

    def test_quitar_evidencia_de_aprobada_da_409_y_nunca_500(self):
        evidencia = self.subir(self.user_a).data
        self.verificar(self.delegado_a, "aprobar")
        self.client.force_authenticate(self.delegado_a)
        r = self.client.delete(f"/api/evidencias/{evidencia['id_evidencia']}/")
        self.assertEqual(r.status_code, 409)


class ActividadNegativasTests(VerificacionBase):
    """Apoyo: reglas de entrada del alta de actividades."""

    def test_origen_delegado_exige_solicitante_delegado(self):
        r = self.registrar(origen="delegado")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "delegado_solicitante")
        r = self.registrar(origen="delegado", delegado_solicitante=self.user_a.pk)
        self.assertEqual(r.status_code, 400)
        r = self.registrar(origen="delegado", delegado_solicitante=self.delegado_a.pk)
        self.assertEqual(r.status_code, 201, r.data)

    def test_vecino_e_item_inactivos_se_rechazan(self):
        self.vecino.estado = "inactivo"
        self.vecino.save()
        r = self.registrar()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "vecino")
        self.assertNotIn("otra delegación", r.data["error"])  # mensaje genérico
        self.item.activo = False
        self.item.save()
        r = self.registrar(vecino=None)
        self.assertEqual(r.data["campo"], "item")

    def test_mensaje_no_revela_que_el_vecino_es_de_otra_delegacion(self):
        self.registrar(usuario=self.user_b)
        r = self.registrar(usuario=self.user_a)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["error"], "El vecino no es válido para tu delegación.")


class BuscarVecinoSeguridadTests(VerificacionBase):
    """Apoyo H01: la búsqueda no entrega datos personales de vecinos ajenos o libres."""

    def setUp(self):
        super().setUp()
        cache.clear()  # el freno por intentos usa la caché
        self.addCleanup(cache.clear)

    def buscar(self, usuario, rut=None):
        self.client.force_authenticate(usuario)
        return self.client.get("/api/vecinos/buscar/", {"rut": rut or self.vecino.rut})

    def test_vecino_libre_no_se_muestra_a_la_delegacion(self):
        self.assertEqual(self.buscar(self.user_a).status_code, 404)  # sin actividades
        self.registrar(usuario=self.user_a)
        self.assertEqual(self.buscar(self.user_a).status_code, 200)
        self.assertEqual(self.buscar(self.user_b).status_code, 404)

    def test_acceso_global_si_ve_al_vecino(self):
        self.assertEqual(self.buscar(self.admin).status_code, 200)

    def test_solo_roles_que_registran(self):
        self.assertEqual(self.buscar(self.jefe).status_code, 403)
        self.assertEqual(
            self.buscar(self.crear_global("alcaldesa", Rol.ALCALDESA)).status_code, 403
        )

    def test_freno_por_intentos(self):
        self.client.force_authenticate(self.user_a)
        codigos = [
            self.client.get("/api/vecinos/buscar/", {"rut": self.nuevo_rut()}).status_code
            for _ in range(32)
        ]
        self.assertEqual(codigos[0], 404)
        self.assertIn(429, codigos)


class AdminActividadTests(VerificacionBase):
    """Apoyo H06: el admin de Django no cambia autor ni código y audita sus cambios."""

    def setUp(self):
        super().setUp()
        self.ma = ActividadAdmin(Actividad, admin.site)
        self.request = RequestFactory().get("/admin/")
        self.request.user = Usuario.objects.create_superuser(
            email="super.admin@terriia.cl", rut=self.nuevo_rut(), password="PruebaSegura123!"
        )

    def test_autor_y_codigo_son_de_solo_lectura(self):
        for campo in ("funcionario", "codigo"):
            self.assertIn(campo, self.ma.get_readonly_fields(self.request, self.actividad))

    def test_aprobada_no_se_puede_cambiar(self):
        self.assertTrue(self.ma.has_change_permission(self.request, self.actividad))
        self.verificar(self.delegado_a, "aprobar")
        aprobada = Actividad.objects.get(pk=self.actividad.pk)
        self.assertFalse(self.ma.has_change_permission(self.request, aprobada))

    def test_guardar_desde_el_admin_queda_auditado(self):
        actividad = Actividad.objects.get(pk=self.actividad.pk)
        actividad.descripcion = "Cambio desde el admin"
        self.ma.save_model(self.request, actividad, form=None, change=True)
        registro = Auditoria.objects.get(entidad="actividad", evento="editar")
        self.assertEqual(registro.valor_anterior["descripcion"], "")
        self.assertEqual(registro.valor_nuevo["descripcion"], "Cambio desde el admin")


class ConfiguracionTests(VerificacionBase):
    """Apoyo H02/H03: arranque seguro y HTTPS opcional. Se evalúa settings.py sin tocar el real."""

    def cargar(self, entorno):
        with mock.patch.dict(os.environ, entorno, clear=True), mock.patch("dotenv.load_dotenv"):
            return runpy.run_path(str(SETTINGS))

    def test_sin_clave_y_sin_debug_no_arranca(self):
        with self.assertRaises(ImproperlyConfigured):
            self.cargar({})

    def test_debug_por_defecto_es_falso(self):
        self.assertFalse(self.cargar({"DJANGO_SECRET_KEY": "x"})["DEBUG"])

    def test_en_desarrollo_se_permite_sin_clave(self):
        self.assertTrue(self.cargar({"DJANGO_DEBUG": "True"})["DEBUG"])

    def test_https_activa_cookies_seguras_y_hsts(self):
        https = self.cargar({"DJANGO_SECRET_KEY": "x", "DJANGO_HTTPS": "True"})
        for nombre in ("SESSION_COOKIE_SECURE", "CSRF_COOKIE_SECURE", "SECURE_SSL_REDIRECT"):
            self.assertTrue(https[nombre], nombre)
        self.assertGreater(https["SECURE_HSTS_SECONDS"], 0)
        self.assertEqual(https["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))
        http = self.cargar({"DJANGO_SECRET_KEY": "x"})
        self.assertNotIn("SESSION_COOKIE_SECURE", http)
        self.assertNotIn("SECURE_SSL_REDIRECT", http)


class PantallaSinFichaTests(VerificacionBase):
    """Apoyo H24: sin ficha activa, «Registrar actividad» avisa y deshabilita el formulario."""

    def test_aviso_y_formulario_deshabilitado(self):
        from django.urls import reverse

        self.func_a.estado = Funcionario.INACTIVO
        self.func_a.save()
        self.client.force_login(self.user_a)
        html = self.client.get(reverse("atenciones_registrar")).content.decode()
        self.assertIn("no tiene una ficha de funcionario activa", html)
        self.assertIn('<fieldset class="sin-borde" disabled>', html)
        self.func_a.estado = Funcionario.ACTIVO
        self.func_a.save()
        html = self.client.get(reverse("atenciones_registrar")).content.decode()
        self.assertNotIn("no tiene una ficha de funcionario activa", html)


class UltimaObservacionTests(VerificacionBase):
    """Apoyo U1: el autor ve la observación del verificador; quien está fuera de alcance, no."""

    def test_autor_recibe_la_observacion_y_otra_delegacion_no(self):
        url = f"{URL}{self.actividad.pk}/"
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get(url).data["ultima_observacion"], "")
        self.verificar(self.delegado_a, "antecedentes", "Falta el acta")
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get(url).data["ultima_observacion"], "Falta el acta")
        listado = self.client.get(URL).data["results"][0]
        self.assertEqual(listado["ultima_observacion"], "Falta el acta")
        self.client.force_authenticate(self.user_b)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(URL).data["count"], 0)
        self.editar(self.user_a, descripcion="Con acta")  # vuelve a pendiente: ya no se muestra
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get(url).data["ultima_observacion"], "")
