from decimal import Decimal

from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from metas.cumplimiento import calcular_cumplimiento

from .datos_base import DatosMetasMixin


class ReglasDeCumplimientoTests(SimpleTestCase):
    def test_porcentaje_simple(self):
        r = calcular_cumplimiento(40, 30)
        self.assertEqual(r["porcentaje"], Decimal("75.00"))
        self.assertFalse(r["cumplida"])

    def test_umbral_80_marca_cumplida(self):
        r = calcular_cumplimiento(40, 32)
        self.assertEqual(r["porcentaje"], Decimal("80.00"))
        self.assertTrue(r["cumplida"])

    def test_justo_bajo_el_umbral_no_cumple(self):
        r = calcular_cumplimiento(Decimal("100"), Decimal("79.99"))
        self.assertEqual(r["porcentaje"], Decimal("79.99"))
        self.assertFalse(r["cumplida"])

    def test_puede_superar_el_100(self):
        self.assertEqual(calcular_cumplimiento(40, 50)["porcentaje"], Decimal("125.00"))

    def test_tope_150(self):
        r = calcular_cumplimiento(40, 100)
        self.assertEqual(r["porcentaje"], Decimal("150.00"))
        self.assertTrue(r["cumplida"])

    def test_sin_avance(self):
        r = calcular_cumplimiento(40, 0)
        self.assertEqual(r["porcentaje"], Decimal("0.00"))
        self.assertFalse(r["cumplida"])

    def test_cumplimiento_ponderado(self):
        # ponderador 40% × 125% de cumplimiento = 50.00
        self.assertEqual(
            calcular_cumplimiento(40, 50, ponderador=40)["ponderado"], Decimal("50.00")
        )
        # el tope también limita el ponderado: 40% × 150% = 60.00
        self.assertEqual(
            calcular_cumplimiento(40, 100, ponderador=40)["ponderado"], Decimal("60.00")
        )

    def test_sin_ponderador_no_calcula_ponderado(self):
        self.assertNotIn("ponderado", calcular_cumplimiento(40, 30))

    def test_meta_invalida(self):
        with self.assertRaises(ValueError):
            calcular_cumplimiento(0, 10)

    def test_avance_negativo(self):
        with self.assertRaises(ValueError):
            calcular_cumplimiento(40, -1)


class RecalibracionYCumplimientoTests(DatosMetasMixin, APITestCase):
    def test_recalibrar_cambia_el_cumplimiento_con_las_mismas_reglas(self):
        self.preparar_datos()
        md = self.crear_meta_delegacion("100.00")
        meta = self.crear_meta(md, self.ana, "40.00")
        self.crear_meta(md, self.luis, "60.00")
        avance = Decimal("30")

        antes = calcular_cumplimiento(meta.valor_objetivo, avance)
        self.assertEqual(antes["porcentaje"], Decimal("75.00"))
        self.assertFalse(antes["cumplida"])

        r = self.client.post(
            f"/api/metas/{meta.pk}/recalibrar/",
            {"valor_objetivo_nuevo": "25.00", "motivo": "Crisis del gas"},
        )
        self.assertEqual(r.status_code, 201, r.data)

        meta.refresh_from_db()
        despues = calcular_cumplimiento(meta.valor_objetivo, avance)
        self.assertEqual(despues["porcentaje"], Decimal("120.00"))
        self.assertTrue(despues["cumplida"])
        # el valor original sigue en el historial
        self.assertEqual(meta.recalibraciones.get().valor_objetivo_anterior, Decimal("40.00"))
