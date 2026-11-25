"""HU03 · Cambiar estado con historial y HU05 · Motivo de atraso obligatorio.
SCRUM-72 a SCRUM-77."""

from rest_framework import status
from rest_framework.test import APITestCase

from atenciones.models import Actividad, ActividadHistorial
from core.models import Auditoria

from .utiles_seguimiento import RAPIDO, EscenarioSolicitudesMixin

MOTIVO = "Faltó personal por licencias médicas"


@RAPIDO
class CambiarEstadoTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.a = self.crear_actividad()
        self.client.force_authenticate(self.usuario_ana)

    def cambiar(self, estado, actividad=None, **extra):
        return self.client.post(
            self.url(actividad or self.a, "cambiar-estado"),
            {"estado": estado, **extra},
            format="json",
        )

    def test_cambio_guarda_fecha_usuario_historial_y_auditoria(self):
        r = self.cambiar("En proceso")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estado, "En proceso")
        self.assertEqual(self.a.usuario_cambio, self.usuario_ana)
        self.assertIsNotNone(self.a.fecha_estado)
        h = ActividadHistorial.objects.get(actividad=self.a)
        self.assertEqual(
            (h.campo, h.valor_anterior, h.valor_nuevo, h.usuario),
            ("estado", "Ingresado", "En proceso", self.usuario_ana),
        )
        self.assertTrue(
            Auditoria.objects.filter(evento="cambiar_estado", entidad_id=self.a.pk).exists()
        )

    def test_flujo_completo_deja_un_registro_por_cambio(self):
        for estado in ("Pendiente", "En proceso", "Pendiente", "Realizado"):
            self.assertEqual(self.cambiar(estado).status_code, 200, estado)
        filas = list(ActividadHistorial.objects.filter(actividad=self.a).order_by("id_historial"))
        self.assertEqual(
            [(f.valor_anterior, f.valor_nuevo) for f in filas],
            [
                ("Ingresado", "Pendiente"),
                ("Pendiente", "En proceso"),
                ("En proceso", "Pendiente"),
                ("Pendiente", "Realizado"),
            ],
        )

    def test_transiciones_invalidas(self):
        r = self.cambiar("Ingresado")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "estado"))  # mismo estado
        self.cambiar("En proceso")
        r = self.cambiar("Ingresado")  # nunca se vuelve a Ingresado
        self.assertEqual((r.status_code, r.data["campo"]), (400, "estado"))
        r = self.cambiar("Inventado")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "estado"))
        self.assertEqual(ActividadHistorial.objects.filter(actividad=self.a).count(), 1)

    def test_realizado_es_final(self):
        self.cambiar("Realizado")
        r = self.cambiar("En proceso")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "estado"))

    def test_historial_se_lista_con_usuario_y_fechas(self):
        self.cambiar("Pendiente")
        r = self.client.get(self.url(self.a, "historial-seguimiento"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["campo_nombre"], "Estado")
        self.assertEqual(r.data[0]["usuario_nombre"], "ana@terriia.cl")

    def test_responsable_y_delegado_pueden_cambiar_estado_otros_no(self):
        self.a.responsable = self.luis
        self.a.save()
        self.client.force_authenticate(self.usuario_luis)
        self.assertEqual(self.cambiar("Pendiente").status_code, 200)
        self.client.force_authenticate(self.delegado)
        self.assertEqual(self.cambiar("En proceso").status_code, 200)
        self.client.force_authenticate(self.delegado_norte)
        self.assertEqual(self.cambiar("Realizado").status_code, 403)  # otra delegación
        self.client.force_authenticate(self.usuario_pedro)
        self.assertEqual(self.cambiar("Realizado").status_code, 403)
        self.a.responsable = None
        self.a.save()
        self.client.force_authenticate(self.usuario_luis)  # misma delegación, no participa
        self.assertEqual(self.cambiar("Realizado").status_code, 403)
        self.client.force_authenticate(self.alcaldesa)
        self.assertEqual(self.cambiar("Realizado").status_code, 403)

    def test_sin_estado_en_la_peticion(self):
        r = self.client.post(self.url(self.a, "cambiar-estado"), {}, format="json")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "estado"))


@RAPIDO
class MotivoDeAtrasoTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.client.force_authenticate(self.usuario_ana)

    def cambiar(self, a, estado, **extra):
        return self.client.post(
            self.url(a, "cambiar-estado"), {"estado": estado, **extra}, format="json"
        )

    def test_vencida_exige_motivo_para_cambiar_estado(self):
        a = self.vencida()
        r = self.cambiar(a, "En proceso")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "motivo_atraso"))
        a.refresh_from_db()
        self.assertEqual(a.estado, "Ingresado")
        self.assertFalse(ActividadHistorial.objects.filter(actividad=a).exists())

    def test_motivo_muy_corto_se_rechaza(self):
        a = self.vencida()
        r = self.cambiar(a, "En proceso", motivo_atraso="ok")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "motivo_atraso"))
        r = self.cambiar(a, "En proceso", motivo_atraso="x" * 256)
        self.assertEqual((r.status_code, r.data["campo"]), (400, "motivo_atraso"))

    def test_con_motivo_cambia_y_guarda_ambos_en_historial(self):
        a = self.vencida()
        r = self.cambiar(a, "Realizado", motivo_atraso=f"  {MOTIVO}  ")
        self.assertEqual(r.status_code, 200, r.data)
        a.refresh_from_db()
        self.assertEqual((a.estado, a.motivo_atraso), ("Realizado", MOTIVO))
        campos = set(ActividadHistorial.objects.filter(actividad=a).values_list("campo", flat=True))
        self.assertEqual(campos, {"estado", "motivo_atraso"})

    def test_si_ya_hay_motivo_no_se_pide_de_nuevo(self):
        a = self.vencida(motivo_atraso=MOTIVO)
        self.assertEqual(self.cambiar(a, "En proceso").status_code, 200)

    def test_no_vencida_no_pide_motivo(self):
        a = self.crear_actividad()
        self.assertEqual(self.cambiar(a, "En proceso").status_code, 200)
        a.refresh_from_db()
        self.assertEqual(a.motivo_atraso, "")

    def test_endpoint_motivo_atraso(self):
        a = self.vencida()
        r = self.client.post(self.url(a, "motivo-atraso"), {"motivo_atraso": MOTIVO}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        a.refresh_from_db()
        self.assertEqual(a.motivo_atraso, MOTIVO)
        h = ActividadHistorial.objects.get(actividad=a)
        self.assertEqual(
            (h.campo, h.valor_anterior, h.valor_nuevo), ("motivo_atraso", None, MOTIVO)
        )
        # Repetir el mismo motivo no genera historial.
        r = self.client.post(self.url(a, "motivo-atraso"), {"motivo_atraso": MOTIVO}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_motivo_atraso_solo_si_hay_atraso(self):
        a = self.crear_actividad()
        r = self.client.post(self.url(a, "motivo-atraso"), {"motivo_atraso": MOTIVO}, format="json")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "motivo_atraso"))

    def test_realizada_con_atraso_permite_registrar_el_motivo_despues(self):
        a = self.vencida(motivo_atraso=MOTIVO)
        self.cambiar(a, "Realizado")
        a.refresh_from_db()
        self.assertGreater(a.dias_atraso, 0)
        r = self.client.post(
            self.url(a, "motivo-atraso"),
            {"motivo_atraso": "Se completó tras reponer el material"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Actividad.objects.get(pk=a.pk).estado, "Realizado")


@RAPIDO
class ActividadAprobadaTests(EscenarioSolicitudesMixin, APITestCase):
    """Una actividad aprobada en la verificación no se modifica (regla de SCRUM-123);
    comentar no la modifica y sigue permitido."""

    def setUp(self):
        self.preparar_escenario()
        self.a = self.crear_actividad()
        Actividad.objects.filter(pk=self.a.pk).update(estado_verificacion="aprobada")
        self.client.force_authenticate(self.usuario_ana)

    def test_no_se_cambia_estado_ni_fecha_ni_motivo(self):
        r = self.client.post(self.url(self.a, "cambiar-estado"), {"estado": "Pendiente"})
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        r = self.client.post(
            self.url(self.a, "fecha-compromiso"), {"fecha_compromiso": "2099-01-01"}
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Actividad.objects.get(pk=self.a.pk).estado, "Ingresado")
        self.assertFalse(ActividadHistorial.objects.filter(actividad=self.a).exists())

    def test_el_delegado_tampoco_asigna_una_aprobada(self):
        self.client.force_authenticate(self.delegado)
        r = self.client.post(
            self.url(self.a, "asignar"),
            {"area": self.area_social_centro.pk, "prioridad": "alta"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)

    def test_si_se_puede_comentar(self):
        r = self.client.post(self.url(self.a, "comentarios"), {"texto": "Gracias"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
