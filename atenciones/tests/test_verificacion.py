"""Pruebas CP-VER-01..14 de verificación y evidencias (SCRUM-123). Solo datos ficticios.

Cada prueba indica el código CP, el requerimiento y el resultado esperado. Los archivos se
guardan en un MEDIA_ROOT temporal que se borra al terminar.
"""

import shutil
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status

from core.models import Auditoria, Rol
from personas.models import Usuario

from ..models import Actividad, Evidencia, HistorialVerificacion
from .test_actividad import URL, ActividadBase, con_ahora, hora

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
MEDIA_TEMPORAL = tempfile.mkdtemp(prefix="terriia-test-media-")


def archivo_png(nombre="foto.png"):
    return SimpleUploadedFile(nombre, PNG, content_type="image/png")


def tearDownModule():
    shutil.rmtree(MEDIA_TEMPORAL, ignore_errors=True)


@override_settings(MEDIA_ROOT=MEDIA_TEMPORAL)
class VerificacionBase(ActividadBase):
    def setUp(self):
        super().setUp()
        _, self.delegado_a = self.crear_autor(self.del_a, "del", rol=Rol.DELEGADO_TERRITORIAL)
        _, self.delegado_b = self.crear_autor(self.del_b, "del", rol=Rol.DELEGADO_TERRITORIAL)
        _, self.encargado_a = self.crear_autor(self.del_a, "enc", rol=Rol.ENCARGADO_AREA)
        _, self.otro_func_a = self.crear_autor(self.del_a, "otro")
        self.jefe = self.crear_global("jefe", Rol.JEFE_DELEGACIONES)
        self.admin = self.crear_global("admin", Rol.ADMINISTRADOR)
        self.actividad = self.crear_en_bd(self.func_a, hora(18, 9))

    def crear_global(self, sufijo, rol):
        return Usuario.objects.create_user(
            email=f"{sufijo}.ver@terriia.cl",
            rut=self.nuevo_rut(),
            password="PruebaSegura123!",
            rol=Rol.objects.get(nombre=rol),
        )

    def verificar(self, usuario, accion, observacion="", actividad=None):
        self.client.force_authenticate(usuario)
        pk = (actividad or self.actividad).pk
        return self.client.post(
            f"{URL}{pk}/verificar/", {"accion": accion, "observacion": observacion}, format="json"
        )

    def editar(self, usuario, **datos):
        self.client.force_authenticate(usuario)
        return self.client.patch(f"{URL}{self.actividad.pk}/", datos, format="json")

    def subir(self, usuario, archivo=None, actividad=None):
        self.client.force_authenticate(usuario)
        return self.client.post(
            "/api/evidencias/",
            {"actividad": (actividad or self.actividad).pk, "archivo": archivo or archivo_png()},
            format="multipart",
        )

    def estado(self):
        return Actividad.objects.get(pk=self.actividad.pk).estado_verificacion


class VerificacionTests(VerificacionBase):
    def test_cp_ver_01_aprobar(self):
        """CP-VER-01 | Req: verificar actividades | Esperado: el delegado de la misma
        delegación aprueba (200) y la actividad queda aprobada; el jefe de delegaciones y el
        administrador (globales) también pueden verificar."""
        r = self.verificar(self.delegado_a, "aprobar")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(self.estado(), "aprobada")
        for usuario in (self.jefe, self.admin, self.encargado_a):
            otra = self.crear_en_bd(self.func_a, hora(17, 9))
            self.assertEqual(self.verificar(usuario, "aprobar", actividad=otra).status_code, 200)

    def test_cp_ver_02_rechazar_sin_observacion(self):
        """CP-VER-02 | Req: observación obligatoria | Esperado: rechazar o pedir antecedentes
        sin observación da 400 y el estado no cambia."""
        for accion in ("rechazar", "antecedentes"):
            r = self.verificar(self.delegado_a, accion, observacion="  ")
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(r.data["campo"], "observacion")
        self.assertEqual(self.estado(), "pendiente")
        r = self.verificar(self.delegado_a, "rechazar", "No corresponde")
        self.assertEqual(r.status_code, 200)

    def test_cp_ver_03_antecedentes_editar_vuelve_a_pendiente(self):
        """CP-VER-03 | Req: flujo de antecedentes | Esperado: antecedentes -> el autor edita
        (200) -> la actividad vuelve a pendiente y queda en el historial."""
        self.verificar(self.delegado_a, "antecedentes", "Falta el acta")
        self.assertEqual(self.estado(), "antecedentes")
        r = self.editar(self.user_a, descripcion="Se adjunta el acta")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(self.estado(), "pendiente")
        self.assertEqual(self.actividad.historial_verificacion.last().estado_nuevo, "pendiente")

    def test_cp_ver_04_editar_aprobado_409(self):
        """CP-VER-04 | Req: aprobado no editable | Esperado: el autor recibe 409 al editar una
        actividad aprobada y los datos no cambian."""
        self.verificar(self.delegado_a, "aprobar")
        r = self.editar(self.user_a, descripcion="cambio")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.actividad.refresh_from_db()
        self.assertEqual(self.actividad.descripcion, "")

    def test_cp_ver_05_admin_tampoco_edita_aprobado(self):
        """CP-VER-05 | Req: aprobado no editable ni por admin | Esperado: el administrador
        recibe 409 por API y el modelo lanza ValidationError en save() y clean()."""
        self.verificar(self.delegado_a, "aprobar")
        self.assertEqual(self.editar(self.admin, descripcion="x").status_code, 409)
        actividad = Actividad.objects.get(pk=self.actividad.pk)
        actividad.descripcion = "x"
        with self.assertRaises(ValidationError):
            actividad.save()
        with con_ahora(), self.assertRaises(ValidationError):
            actividad.clean()
        self.actividad.refresh_from_db()
        self.assertEqual(self.actividad.descripcion, "")

    def test_cp_ver_06_autoverificacion_rechazada(self):
        """CP-VER-06 | Req: nadie verifica lo propio | Esperado: un delegado (y un
        administrador con ficha) que verifica una actividad propia recibe 403."""
        propia = self.crear_en_bd(self.delegado_a.funcionario, hora(18, 9))
        r = self.verificar(self.delegado_a, "aprobar", actividad=propia)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.admin.funcionario = self.func_a
        self.admin.save()
        self.assertEqual(self.verificar(self.admin, "aprobar").status_code, 403)
        self.assertEqual(self.estado(), "pendiente")

    def test_cp_ver_07_otra_delegacion_403(self):
        """CP-VER-07 | Req: verificación con alcance por delegación | Esperado: el delegado
        de la delegación B recibe 403 (no 404) al verificar o editar una actividad de A."""
        r = self.verificar(self.delegado_b, "aprobar")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.editar(self.delegado_b, descripcion="x").status_code, 403)
        self.assertEqual(self.estado(), "pendiente")
        # Una actividad que no existe sí es 404.
        self.client.force_authenticate(self.delegado_b)
        r = self.client.post(f"{URL}99999/verificar/", {}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_cp_ver_08_funcionario_no_verifica(self):
        """CP-VER-08 | Req: el Funcionario no verifica | Esperado: 403 aunque sea de la
        misma delegación (otro funcionario o el propio autor)."""
        self.assertEqual(self.verificar(self.otro_func_a, "aprobar").status_code, 403)
        self.assertEqual(self.verificar(self.user_a, "aprobar").status_code, 403)
        self.assertEqual(self.estado(), "pendiente")

    def test_cp_ver_09_rechazada_es_final(self):
        """CP-VER-09 | Req: rechazada es estado final | Esperado: rechazada -> aprobada da
        409 y el autor tampoco puede editarla (409)."""
        self.verificar(self.delegado_a, "rechazar", "Sin respaldo")
        self.assertEqual(self.verificar(self.delegado_a, "aprobar").status_code, 409)
        self.assertEqual(self.editar(self.user_a, descripcion="x").status_code, 409)
        self.assertEqual(self.estado(), "rechazada")

    def test_cp_ver_10_evidencia_en_aprobado_409(self):
        """CP-VER-10 | Req: aprobado no cambia evidencias | Esperado: no se puede subir (409)
        ni quitar (409) una evidencia de una actividad aprobada."""
        evidencia = self.subir(self.user_a).data
        self.verificar(self.delegado_a, "aprobar")
        self.assertEqual(self.subir(self.user_a).status_code, status.HTTP_409_CONFLICT)
        self.client.force_authenticate(self.user_a)
        r = self.client.delete(f"/api/evidencias/{evidencia['id_evidencia']}/")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Evidencia.objects.count(), 1)

    def test_cp_ver_11_exe_renombrado_rechazado(self):
        """CP-VER-11 | Req: solo JPG, PNG o PDF reales | Esperado: un .exe renombrado a .png
        (con Content-Type image/png) se rechaza con 400 por su firma; un PDF y un PNG reales
        entran."""
        falso = SimpleUploadedFile("foto.png", b"MZ\x90\x00" + b"0" * 100, content_type="image/png")
        r = self.subir(self.user_a, falso)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "archivo")
        pdf = SimpleUploadedFile(
            "acta.pdf", b"%PDF-1.4 " + b"0" * 50, content_type="application/pdf"
        )
        self.assertEqual(self.subir(self.user_a, pdf).status_code, 201)
        r = self.subir(self.user_a)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertRegex(r.data["codigo_verificador"], r"^[A-Z]{3}[0-9]{3}$")
        self.assertNotIn("archivo", r.data)  # la ruta no se expone

    def test_cp_ver_12_mas_de_5_mb_rechazado(self):
        """CP-VER-12 | Req: máximo 5 MB | Esperado: 6 MB da 400; exactamente 5 MB es válido."""
        grande = SimpleUploadedFile(
            "g.png", PNG + b"0" * (6 * 1024 * 1024), content_type="image/png"
        )
        r = self.subir(self.user_a, grande)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("5 MB", r.data["error"])
        limite = SimpleUploadedFile(
            "l.png", PNG + b"0" * (5 * 1024 * 1024 - len(PNG)), content_type="image/png"
        )
        self.assertEqual(self.subir(self.user_a, limite).status_code, 201)

    def test_cp_ver_13_descarga_otra_delegacion_403(self):
        """CP-VER-13 | Req: evidencias sin URL pública, con control de delegación | Esperado:
        el autor y el delegado de A descargan (200, contenido íntegro); el delegado de B recibe
        403; el anónimo 403; /media/ no se sirve."""
        evidencia = self.subir(self.user_a).data
        url = f"/api/evidencias/{evidencia['id_evidencia']}/archivo/"
        for usuario in (self.user_a, self.delegado_a):
            self.client.force_authenticate(usuario)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(b"".join(r.streaming_content), PNG)
        self.client.force_authenticate(self.delegado_b)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.otro_func_a)  # misma delegación, no es el autor
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 403)
        ruta = Evidencia.objects.get().archivo.name
        self.assertEqual(self.client.get(f"/media/{ruta}").status_code, 404)

    def test_cp_ver_13b_x_accel_redirect(self):
        """Apoyo CP-VER-13: con EVIDENCIAS_X_ACCEL_PREFIX la descarga delega en nginx."""
        evidencia = self.subir(self.user_a).data
        ruta = Evidencia.objects.get().archivo.name
        self.client.force_authenticate(self.user_a)
        with override_settings(EVIDENCIAS_X_ACCEL_PREFIX="/protegido-media/"):
            r = self.client.get(f"/api/evidencias/{evidencia['id_evidencia']}/archivo/")
        self.assertEqual(r["X-Accel-Redirect"], f"/protegido-media/{ruta}")

    def test_cp_ver_14_historial_de_transiciones(self):
        """CP-VER-14 | Req: historial y auditoría de verificación | Esperado: cada cambio
        queda en el historial (quién, de qué a qué, observación, en orden) y en auditoría."""
        self.verificar(self.delegado_a, "antecedentes", "Falta el acta")
        self.editar(self.user_a, descripcion="Con acta")
        self.verificar(self.encargado_a, "aprobar", "Conforme")
        self.client.force_authenticate(self.delegado_a)
        r = self.client.get(f"{URL}{self.actividad.pk}/historial/")
        self.assertEqual(r.status_code, 200)
        pasos = [(h["estado_anterior"], h["estado_nuevo"]) for h in r.data]
        self.assertEqual(
            pasos,
            [
                ("pendiente", "antecedentes"),
                ("antecedentes", "pendiente"),
                ("pendiente", "aprobada"),
            ],
        )
        self.assertEqual(r.data[0]["observacion"], "Falta el acta")
        self.assertEqual(r.data[2]["usuario"], self.encargado_a.pk)
        self.assertEqual(HistorialVerificacion.objects.count(), 3)
        self.assertEqual(
            Auditoria.objects.filter(entidad="actividad", evento="verificar").count(), 2
        )


class PantallaVerificacionTests(VerificacionBase):
    """Apoyo: la pantalla solo la ven los roles que verifican."""

    def test_acceso_por_rol(self):
        from django.urls import reverse

        url = reverse("atenciones_verificacion")
        for usuario in (self.delegado_a, self.encargado_a, self.jefe, self.admin):
            self.client.force_login(usuario)
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertIn("Verificación", r.content.decode())
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
