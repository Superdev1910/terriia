from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from metas.models import RecalibracionMeta
from personas.models import Usuario

from .datos_base import DatosMetasMixin

URL_META = "/api/metas/"
URL_HISTORIAL = "/api/recalibraciones-meta/"


class RecalibracionMetaTests(DatosMetasMixin, APITestCase):
    def setUp(self):
        self.preparar_datos()
        self.md = self.crear_meta_delegacion("100.00")
        self.meta = self.crear_meta(self.md, self.ana, "40.00")
        self.crear_meta(self.md, self.luis, "60.00")
        self.url = f"{URL_META}{self.meta.pk}/recalibrar/"
        self.datos = {"valor_objetivo_nuevo": "25.00", "motivo": "Crisis del gas"}

    # 1. crear: el ajuste queda con motivo, fecha y usuario
    def test_recalibrar_registra_el_ajuste(self):
        r = self.client.post(self.url, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        rec = RecalibracionMeta.objects.get()
        self.assertEqual(rec.valor_objetivo_anterior, Decimal("40.00"))
        self.assertEqual(rec.valor_objetivo_nuevo, Decimal("25.00"))
        self.assertEqual(rec.motivo, "Crisis del gas")
        self.assertEqual(rec.usuario, self.admin)
        self.assertIsNotNone(rec.fecha)
        self.assertEqual(r.data["usuario_email"], "admin@terriia.cl")
        self.assertTrue(
            Auditoria.objects.filter(
                evento="recalibrar", entidad="meta", entidad_id=self.meta.pk
            ).exists()
        )

    # 2. la meta y el total de la delegación siguen cuadrando
    def test_meta_y_total_se_actualizan_con_la_misma_diferencia(self):
        self.client.post(self.url, self.datos)
        self.meta.refresh_from_db()
        self.md.refresh_from_db()
        self.assertEqual(self.meta.valor_objetivo, Decimal("25.00"))
        self.assertEqual(self.md.valor_objetivo_total, Decimal("85.00"))
        suma = sum(m.valor_objetivo for m in self.md.metas_individuales.all())
        self.assertEqual(suma, self.md.valor_objetivo_total)

    # 3. el historial original no se pierde
    def test_historial_conserva_el_valor_original(self):
        self.client.post(self.url, self.datos)
        self.client.post(self.url, {"valor_objetivo_nuevo": "30.00", "motivo": "Se normaliza"})
        r = self.client.get(URL_HISTORIAL, {"meta": self.meta.pk})
        self.assertEqual(r.data["count"], 2)
        original = RecalibracionMeta.objects.filter(meta=self.meta).order_by("fecha", "pk").first()
        self.assertEqual(original.valor_objetivo_anterior, Decimal("40.00"))

    # 3b. inválido
    def test_motivo_obligatorio(self):
        self.datos["motivo"] = "   "
        r = self.client.post(self.url, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "motivo")
        self.assertFalse(RecalibracionMeta.objects.exists())

    def test_valor_igual_al_actual_rechazado(self):
        self.datos["valor_objetivo_nuevo"] = "40.00"
        r = self.client.post(self.url, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo_nuevo")

    def test_valor_cero_rechazado(self):
        self.datos["valor_objetivo_nuevo"] = "0"
        r = self.client.post(self.url, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo_nuevo")

    # 4. el historial no se edita ni se borra
    def test_historial_solo_lectura(self):
        self.client.post(self.url, self.datos)
        rec = RecalibracionMeta.objects.get()
        url = f"{URL_HISTORIAL}{rec.pk}/"
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(
            self.client.patch(url, {"motivo": "otro"}).status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )
        self.assertEqual(self.client.post(URL_HISTORIAL, {}).status_code, 405)

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        func = Usuario.objects.create_user(
            email="f@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        self.client.force_authenticate(func)
        r = self.client.post(self.url, self.datos)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(URL_HISTORIAL).status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(RecalibracionMeta.objects.exists())
