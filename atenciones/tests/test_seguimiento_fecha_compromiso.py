"""HU06 · Fecha de compromiso con historial y HU07 · Resaltado de vencidas.
SCRUM-78 a SCRUM-81."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from atenciones.models import Actividad, ActividadHistorial
from core.models import Auditoria

from .utiles_seguimiento import RAPIDO, EscenarioSolicitudesMixin

MOTIVO = "Se reprogramó por lluvias en el sector"


def hoy():
    return timezone.localdate()


@RAPIDO
class FechaCompromisoTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.a = self.crear_actividad()
        self.client.force_authenticate(self.usuario_ana)

    def fijar(self, actividad, fecha, **extra):
        return self.client.post(
            self.url(actividad, "fecha-compromiso"),
            {"fecha_compromiso": str(fecha), **extra},
            format="json",
        )

    def test_fijar_la_fecha_registra_historial_y_auditoria(self):
        fecha = hoy() + timedelta(days=5)
        r = self.fijar(self.a, fecha)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.a.refresh_from_db()
        self.assertEqual(self.a.fecha_compromiso, fecha)
        h = ActividadHistorial.objects.get(actividad=self.a)
        self.assertEqual(
            (h.campo, h.valor_anterior, h.valor_nuevo, h.usuario),
            ("fecha_compromiso", None, fecha.isoformat(), self.usuario_ana),
        )
        self.assertTrue(
            Auditoria.objects.filter(evento="fecha_compromiso", entidad_id=self.a.pk).exists()
        )

    def test_cada_cambio_conserva_el_valor_anterior(self):
        f1, f2, f3 = (hoy() + timedelta(days=d) for d in (5, 8, 12))
        for f in (f1, f2, f3):
            self.assertEqual(self.fijar(self.a, f).status_code, 200)
        filas = ActividadHistorial.objects.filter(actividad=self.a).order_by("id_historial")
        self.assertEqual(
            [(h.valor_anterior, h.valor_nuevo) for h in filas],
            [(None, str(f1)), (str(f1), str(f2)), (str(f2), str(f3))],
        )

    def test_no_acepta_fecha_pasada_ni_la_misma_fecha_ni_formato_invalido(self):
        r = self.fijar(self.a, hoy() - timedelta(days=1))
        self.assertEqual((r.status_code, r.data["campo"]), (400, "fecha_compromiso"))
        self.fijar(self.a, hoy() + timedelta(days=2))
        r = self.fijar(self.a, hoy() + timedelta(days=2))
        self.assertEqual((r.status_code, r.data["campo"]), (400, "fecha_compromiso"))
        r = self.fijar(self.a, "mañana")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "fecha_compromiso"))
        self.assertEqual(ActividadHistorial.objects.filter(actividad=self.a).count(), 1)

    def test_hoy_es_valido(self):
        self.assertEqual(self.fijar(self.a, hoy()).status_code, 200)

    def test_postergar_una_vencida_exige_motivo(self):
        a = self.vencida()
        r = self.fijar(a, hoy() + timedelta(days=7))
        self.assertEqual((r.status_code, r.data["campo"]), (400, "motivo_atraso"))
        r = self.fijar(a, hoy() + timedelta(days=7), motivo_atraso=MOTIVO)
        self.assertEqual(r.status_code, 200, r.data)
        a.refresh_from_db()
        self.assertEqual(a.motivo_atraso, MOTIVO)
        self.assertFalse(a.esta_vencida)
        self.assertEqual(
            set(ActividadHistorial.objects.filter(actividad=a).values_list("campo", flat=True)),
            {"fecha_compromiso", "motivo_atraso"},
        )

    def test_solicitud_realizada_no_cambia_de_fecha(self):
        self.a.estado = "Realizado"
        self.a.save()
        r = self.fijar(self.a, hoy() + timedelta(days=3))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_permisos_por_rol_y_delegacion(self):
        fecha = hoy() + timedelta(days=3)
        self.client.force_authenticate(self.usuario_luis)  # ni autor ni responsable
        self.assertEqual(self.fijar(self.a, fecha).status_code, 403)
        self.client.force_authenticate(self.delegado_norte)
        self.assertEqual(self.fijar(self.a, fecha).status_code, 403)
        self.client.force_authenticate(self.delegado)
        self.assertEqual(self.fijar(self.a, fecha).status_code, 200)


@RAPIDO
class VencidasTests(EscenarioSolicitudesMixin, APITestCase):
    """HU07: una solicitud está vencida si su compromiso ya pasó y no está Realizada."""

    def setUp(self):
        self.preparar_escenario()
        self.client.force_authenticate(self.usuario_ana)
        self.vencida_ = self.vencida(dias=4)
        self.hoy_ = self.crear_actividad(fecha_compromiso=hoy())
        self.futura = self.crear_actividad(fecha_compromiso=hoy() + timedelta(days=2))
        self.sin_fecha = self.crear_actividad()
        self.cerrada = self.vencida(dias=10, estado="Realizado")

    def test_propiedad_vencida_y_dias_de_atraso(self):
        self.assertTrue(self.vencida_.esta_vencida)
        self.assertEqual(self.vencida_.dias_atraso, 4)
        for a in (self.hoy_, self.futura, self.sin_fecha, self.cerrada):
            self.assertFalse(a.esta_vencida, a.pk)
        self.assertEqual((self.hoy_.dias_atraso, self.sin_fecha.dias_atraso), (0, 0))

    def test_realizada_con_atraso_cuenta_los_dias_hasta_el_cierre(self):
        a = self.vencida(dias=6)
        ahora = timezone.now()
        a.estado, a.fecha_estado = "Realizado", ahora - timedelta(days=2)
        a.save()
        self.assertEqual(a.dias_atraso, 4)

    def test_la_api_marca_la_solicitud_vencida(self):
        r = self.client.get(self.url(self.vencida_))
        self.assertTrue(r.data["vencida"])
        self.assertEqual(r.data["dias_atraso"], 4)
        self.assertFalse(self.client.get(self.url(self.cerrada)).data["vencida"])

    def test_filtro_vencida_true_y_false(self):
        r = self.client.get("/api/actividades/?vencida=true")
        self.assertEqual({f["id_actividad"] for f in r.data["results"]}, {self.vencida_.pk})
        r = self.client.get("/api/actividades/?vencida=false")
        self.assertEqual(
            {f["id_actividad"] for f in r.data["results"]},
            {self.hoy_.pk, self.futura.pk, self.sin_fecha.pk, self.cerrada.pk},
        )

    def test_orden_por_fecha_de_compromiso(self):
        r = self.client.get("/api/actividades/?ordering=fecha_compromiso&vencida=false")
        fechas = [f["fecha_compromiso"] for f in r.data["results"] if f["fecha_compromiso"]]
        self.assertEqual(fechas, sorted(fechas))

    def test_resumen_cuenta_estados_y_vencidas(self):
        r = self.client.get("/api/actividades/resumen/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["total"], 5)
        self.assertEqual(r.data["vencidas"], 1)
        self.assertEqual(r.data["por_estado"]["Realizado"], 1)
        self.assertEqual(r.data["por_estado"]["Ingresado"], 4)

    def test_resumen_respeta_el_alcance(self):
        self.client.force_authenticate(self.usuario_pedro)
        self.assertEqual(self.client.get("/api/actividades/resumen/").data["total"], 0)
