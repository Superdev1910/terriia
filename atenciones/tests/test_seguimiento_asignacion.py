"""HU02 · Asignar a un área (con prioridad y responsable). SCRUM-70 / SCRUM-71."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria

from .utiles_seguimiento import RAPIDO, EscenarioSolicitudesMixin


@RAPIDO
class AsignarAreaTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.a = self.crear_actividad()
        self.client.force_authenticate(self.delegado)

    def asignar(self, **datos):
        return self.client.post(self.url(self.a, "asignar"), datos, format="json")

    def test_delegado_asigna_area_prioridad_y_responsable(self):
        r = self.asignar(
            area=self.area_social_centro.pk, prioridad="alta", responsable=self.luis.pk
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.a.refresh_from_db()
        self.assertEqual(
            (self.a.area, self.a.prioridad, self.a.responsable),
            (self.area_social_centro, "alta", self.luis),
        )
        self.assertEqual(r.data["area_nombre"], "Social")
        self.assertEqual(r.data["responsable_nombre"], "Luis Rojas")
        self.assertTrue(Auditoria.objects.filter(evento="asignar", entidad_id=self.a.pk).exists())

    def test_responsable_es_opcional(self):
        r = self.asignar(area=self.area_social_centro.pk, prioridad="media")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertIsNone(r.data["responsable"])

    def test_se_puede_reasignar(self):
        self.asignar(area=self.area_social_centro.pk, prioridad="alta", responsable=self.luis.pk)
        r = self.asignar(area=self.area_seg_centro.pk, prioridad="baja")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.a.refresh_from_db()
        self.assertEqual(
            (self.a.area, self.a.prioridad, self.a.responsable),
            (self.area_seg_centro, "baja", None),
        )

    def test_area_y_prioridad_son_obligatorias(self):
        self.assertEqual(self.asignar(prioridad="alta").data["campo"], "area")
        self.assertEqual(self.asignar(area=self.area_social_centro.pk).data["campo"], "prioridad")
        self.assertEqual(
            self.asignar(area=self.area_social_centro.pk, prioridad="urgente").data["campo"],
            "prioridad",
        )

    def test_area_de_otra_delegacion_se_rechaza(self):
        r = self.asignar(area=self.area_social_norte.pk, prioridad="alta")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "area"))

    def test_area_inactiva_se_rechaza(self):
        self.area_social_centro.estado = "inactiva"
        self.area_social_centro.save()
        r = self.asignar(area=self.area_social_centro.pk, prioridad="alta")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "area"))

    def test_responsable_debe_ser_de_la_delegacion_activo_y_del_area(self):
        r = self.asignar(
            area=self.area_social_centro.pk, prioridad="alta", responsable=self.pedro.pk
        )
        self.assertEqual((r.status_code, r.data["campo"]), (400, "responsable"))
        # Marta es inspectora (área Seguridad): no corresponde al área Social.
        r = self.asignar(
            area=self.area_social_centro.pk, prioridad="alta", responsable=self.marta.pk
        )
        self.assertEqual((r.status_code, r.data["campo"]), (400, "responsable"))
        self.luis.estado = "inactivo"
        self.luis.save()
        r = self.asignar(
            area=self.area_social_centro.pk, prioridad="alta", responsable=self.luis.pk
        )
        self.assertEqual((r.status_code, r.data["campo"]), (400, "responsable"))

    def test_cargo_transversal_puede_ser_responsable_de_cualquier_area(self):
        admin_central = self.crear_funcionario(
            "F-0009", "Rosa Vera", self.cargo_transversal, self.centro
        )
        r = self.asignar(
            area=self.area_seg_centro.pk, prioridad="alta", responsable=admin_central.pk
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_el_area_debe_coincidir_con_el_tipo_de_atencion(self):
        self.a.tipo_atencion = self.tipo  # tipo del área Social
        self.a.save()
        r = self.asignar(area=self.area_seg_centro.pk, prioridad="alta")
        self.assertEqual((r.status_code, r.data["campo"]), (400, "area"))

    def test_solicitud_realizada_no_se_reasigna(self):
        self.a.estado = "Realizado"
        self.a.save()
        r = self.asignar(area=self.area_social_centro.pk, prioridad="alta")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_funcionario_no_puede_asignar(self):
        self.client.force_authenticate(self.usuario_ana)
        r = self.asignar(area=self.area_social_centro.pk, prioridad="alta")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_delegado_de_otra_delegacion_no_puede_asignar(self):
        self.client.force_authenticate(self.delegado_norte)
        r = self.asignar(area=self.area_social_norte.pk, prioridad="alta")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
