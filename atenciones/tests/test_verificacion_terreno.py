"""HU29 · Verificación en terreno (SCRUM-32) de las solicitudes del Tubo (`ingreso_a_tubo`)."""

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from atenciones.models import Actividad, ActividadHistorial, VisitaTerreno
from core.models import Auditoria

from .utiles_seguimiento import (
    PNG,
    RAPIDO,
    EscenarioSolicitudesMixin,
    MediaTemporalMixin,
)


@RAPIDO
class VisitaTerrenoBase(MediaTemporalMixin, EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.preparar_escenario()
        self.a = self.crear_actividad(ingreso_a_tubo=True)
        # Ana (autora, Funcionario) no es la responsable; Luis sí.
        self.a.responsable = self.luis
        self.a.save(update_fields=["responsable"])

    def visita(self, usuario, tipo="inicial", resultado="conforme", actividad=None, **extra):
        self.client.force_authenticate(usuario)
        datos = {"tipo": tipo, "resultado": resultado, **extra}
        return self.client.post(
            self.url(actividad or self.a, "visitas-terreno"), datos, format="multipart"
        )

    def estado(self, usuario, nuevo, actividad=None):
        self.client.force_authenticate(usuario)
        return self.client.post(
            self.url(actividad or self.a, "cambiar-estado"), {"estado": nuevo}, format="json"
        )

    def inicial_conforme(self):
        r = self.visita(self.usuario_luis)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def cierre_conforme(self):
        r = self.visita(self.usuario_luis, tipo="cierre")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)


class SinMarcaTests(VisitaTerrenoBase):
    def test_sin_la_marca_todo_funciona_como_antes(self):
        b = self.crear_actividad()
        self.assertEqual(self.estado(self.usuario_ana, "En proceso", b).status_code, 200)
        self.assertEqual(self.estado(self.usuario_ana, "Realizado", b).status_code, 200)

    def test_sin_la_marca_no_se_registran_visitas(self):
        b = self.crear_actividad()
        r = self.visita(self.delegado, actividad=b)
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def test_campos_de_terreno_en_la_actividad(self):
        b = self.crear_actividad()
        self.client.force_authenticate(self.delegado)
        d = self.client.get(self.url(b)).data
        self.assertEqual(
            (d["requiere_terreno"], d["terreno_inicial"], d["terreno_cierre"]),
            (False, None, None),
        )
        self.assertFalse(d["puede_registrar_visita"])


class FlujoTests(VisitaTerrenoBase):
    def test_avanzar_sin_inicial_conforme_da_409(self):
        for nuevo in ("Pendiente", "En proceso", "Realizado"):
            r = self.estado(self.usuario_ana, nuevo)
            self.assertEqual(r.status_code, status.HTTP_409_CONFLICT, nuevo)
        self.assertIn("verificación en terreno conforme", str(r.data))

    def test_inicial_no_conforme_no_deja_avanzar(self):
        r = self.visita(self.usuario_luis, resultado="no_conforme", observacion="No está el vecino")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(self.estado(self.usuario_ana, "En proceso").status_code, 409)
        self.client.force_authenticate(self.delegado)
        self.assertEqual(self.client.get(self.url(self.a)).data["terreno_inicial"], "no_conforme")

    def test_avanza_tras_inicial_conforme(self):
        self.inicial_conforme()
        self.assertEqual(self.estado(self.usuario_ana, "En proceso").status_code, 200)

    def test_asignar_se_permite_en_ingresado(self):
        self.client.force_authenticate(self.delegado)
        r = self.client.post(
            self.url(self.a, "asignar"),
            {
                "area": self.area_social_centro.pk,
                "prioridad": "alta",
                "responsable": self.ana.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_realizado_exige_cierre_conforme(self):
        self.inicial_conforme()
        self.estado(self.usuario_ana, "En proceso")
        r = self.estado(self.usuario_ana, "Realizado")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("verificación de cierre conforme", str(r.data))
        self.cierre_conforme()
        r = self.estado(self.usuario_ana, "Realizado")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, Actividad.REALIZADO)

    def test_cierre_no_conforme_mantiene_abierta(self):
        self.inicial_conforme()
        self.estado(self.usuario_ana, "En proceso")
        r = self.visita(self.usuario_luis, "cierre", "no_conforme", observacion="Quedó pendiente")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(self.estado(self.usuario_ana, "Realizado").status_code, 409)

    def test_cierre_anterior_a_una_nueva_inicial_no_vale(self):
        self.inicial_conforme()
        self.estado(self.usuario_ana, "En proceso")
        self.cierre_conforme()
        self.inicial_conforme()  # una inicial conforme posterior invalida ese cierre
        self.assertEqual(self.estado(self.usuario_ana, "Realizado").status_code, 409)
        self.client.force_authenticate(self.delegado)
        self.assertIsNone(self.client.get(self.url(self.a)).data["terreno_cierre"])

    def test_cierre_exige_inicial_previa(self):
        r = self.visita(self.usuario_luis, tipo="cierre")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(VisitaTerreno.objects.count(), 0)

    def test_cierre_en_ingresado_da_409(self):
        self.inicial_conforme()
        self.assertEqual(self.visita(self.usuario_luis, tipo="cierre").status_code, 409)

    def test_no_conforme_exige_observacion(self):
        r = self.visita(self.usuario_luis, resultado="no_conforme")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "observacion")

    def test_visita_sobre_realizada_da_409(self):
        self.a.estado = Actividad.REALIZADO
        self.a.save(update_fields=["estado"])
        self.assertEqual(self.visita(self.usuario_luis).status_code, 409)

    def test_estado_visible_en_la_actividad(self):
        self.inicial_conforme()
        self.estado(self.usuario_ana, "En proceso")
        self.cierre_conforme()
        self.client.force_authenticate(self.usuario_luis)
        d = self.client.get(self.url(self.a)).data
        self.assertEqual((d["terreno_inicial"], d["terreno_cierre"]), ("conforme", "conforme"))
        self.assertTrue(d["requiere_terreno"])
        self.assertTrue(d["puede_registrar_visita"])


class PermisosTests(VisitaTerrenoBase):
    def test_el_responsable_registra(self):
        self.assertEqual(self.visita(self.usuario_luis).status_code, 201)

    def test_quien_verifica_registra(self):
        for usuario in (self.delegado, self.admin):
            self.assertEqual(self.visita(usuario).status_code, 201, usuario.email)

    def test_otro_funcionario_da_403(self):
        # Ana es autora pero no responsable.
        self.assertEqual(self.visita(self.usuario_ana).status_code, 403)

    def test_alcaldesa_da_403(self):
        self.assertEqual(self.visita(self.alcaldesa).status_code, 403)

    def test_otra_delegacion_da_404(self):
        self.assertEqual(self.visita(self.delegado_norte).status_code, 404)
        self.assertEqual(self.visita(self.usuario_pedro).status_code, 404)

    def test_listar_visitas(self):
        self.inicial_conforme()
        self.client.force_authenticate(self.alcaldesa)
        r = self.client.get(self.url(self.a, "visitas-terreno"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.client.force_authenticate(self.delegado_norte)
        self.assertEqual(self.client.get(self.url(self.a, "visitas-terreno")).status_code, 404)


class DatosTests(VisitaTerrenoBase):
    def test_latitud_y_longitud_fuera_de_rango_dan_400(self):
        r = self.visita(self.usuario_luis, latitud="91", longitud="10")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "latitud")
        r = self.visita(self.usuario_luis, latitud="10", longitud="-181")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "longitud")

    def test_coordenadas_validas(self):
        r = self.visita(self.usuario_luis, latitud="-33.456789", longitud="-70.648273")
        self.assertEqual(r.status_code, 201, r.data)

    def test_tipo_de_archivo_invalido_da_400(self):
        falso = SimpleUploadedFile("foto.jpg", b"no soy una imagen", content_type="image/jpeg")
        r = self.visita(self.usuario_luis, archivo=falso)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "archivo")

    def test_archivo_se_guarda_con_nombre_uuid(self):
        r = self.visita(
            self.usuario_luis,
            archivo=SimpleUploadedFile("mi casa.png", PNG, content_type="image/png"),
        )
        self.assertEqual(r.status_code, 201, r.data)
        visita = VisitaTerreno.objects.get()
        self.assertNotIn("mi casa", visita.archivo.name)
        self.assertTrue(visita.archivo.name.endswith(".png"))
        self.assertEqual(visita.tipo_contenido, "image/png")
        self.assertNotIn("archivo", r.data)
        self.assertEqual(r.data["descarga"], f"/api/visitas-terreno/{visita.pk}/archivo/")

    def test_historial_y_auditoria(self):
        self.visita(self.usuario_luis, resultado="no_conforme", observacion="Sin acceso")
        h = ActividadHistorial.objects.get(actividad=self.a, campo="visita_terreno")
        self.assertEqual(h.usuario, self.usuario_luis)
        self.assertIn("No conforme", h.valor_nuevo)
        a = Auditoria.objects.get(evento="visita_terreno")
        self.assertEqual(a.usuario, self.usuario_luis)
        self.assertEqual(a.entidad, "visita_terreno")
        self.assertNotIn("archivo", a.valor_nuevo)


class DescargaTests(VisitaTerrenoBase):
    def subir(self):
        self.visita(
            self.usuario_luis, archivo=SimpleUploadedFile("f.png", PNG, content_type="image/png")
        )
        return VisitaTerreno.objects.get()

    def test_descarga_con_acceso(self):
        v = self.subir()
        for usuario in (self.usuario_luis, self.delegado, self.alcaldesa):
            self.client.force_authenticate(usuario)
            r = self.client.get(f"/api/visitas-terreno/{v.pk}/archivo/")
            self.assertEqual(r.status_code, 200, usuario.email)
            self.assertEqual(r["X-Content-Type-Options"], "nosniff")
            r.close()

    def test_descarga_sin_acceso(self):
        v = self.subir()
        self.client.logout()
        self.client.force_authenticate(None)
        self.assertIn(
            self.client.get(f"/api/visitas-terreno/{v.pk}/archivo/").status_code, (401, 403)
        )
        self.client.force_authenticate(self.delegado_norte)
        self.assertEqual(self.client.get(f"/api/visitas-terreno/{v.pk}/archivo/").status_code, 404)

    def test_sin_url_publica(self):
        v = self.subir()
        self.client.force_authenticate(self.delegado)
        self.assertNotIn("archivo", self.client.get(self.url(self.a, "visitas-terreno")).data[0])
        self.assertEqual(self.client.get(f"/media/{v.archivo.name}").status_code, 404)

    def test_x_accel_redirect(self):
        v = self.subir()
        self.client.force_authenticate(self.delegado)
        with self.settings(EVIDENCIAS_X_ACCEL_PREFIX="/protegido/"):
            r = self.client.get(f"/api/visitas-terreno/{v.pk}/archivo/")
        self.assertEqual(r["X-Accel-Redirect"], f"/protegido/{v.archivo.name}")
