"""Pruebas del registro de felicitaciones y reclamos, HU26 (feature/felicitacion_reclamo)."""

from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from metas.cumplimiento import ajuste_felicitaciones_reclamos, cumplimiento_ponderado_total
from metas.models import FelicitacionReclamo, Periodo
from personas.models import Funcionario, Usuario

from .datos_base import DatosMetasMixin

URL = "/api/felicitaciones-reclamos/"


class FelicitacionReclamoTests(DatosMetasMixin, APITestCase):
    def setUp(self):
        self.preparar_datos()  # self.periodo = 2026-01-01 a 2026-03-31
        self.periodo2 = Periodo.objects.create(
            fecha_inicio="2026-04-01", fecha_termino="2026-06-30", estado=Periodo.CERRADO
        )
        self.datos = {
            "funcionario": self.ana.pk,
            "tipo": "felicitacion",
            "fecha": "2026-02-10",
            "motivo": "Atención destacada a vecinos",
        }

    def _registrar(self, tipo="felicitacion", fecha="2026-02-10", funcionario=None):
        return FelicitacionReclamo.objects.create(
            funcionario=funcionario or self.ana,
            tipo=tipo,
            fecha=fecha,
            motivo="Motivo",
            usuario_autoriza=self.admin,
        )

    # 1. crear: queda con fecha, motivo y usuario (trazabilidad)
    def test_crear_felicitacion(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["impacto_pct"], "10.00")
        self.assertEqual(r.data["usuario_email"], "admin@terriia.cl")
        fr = FelicitacionReclamo.objects.get()
        self.assertEqual(fr.usuario_autoriza, self.admin)
        self.assertEqual(str(fr.fecha), "2026-02-10")
        self.assertEqual(fr.motivo, "Atención destacada a vecinos")
        self.assertTrue(
            Auditoria.objects.filter(
                evento="crear", entidad="felicitacion_reclamo", entidad_id=fr.pk
            ).exists()
        )

    def test_crear_reclamo(self):
        self.datos.update(tipo="reclamo", motivo="Reclamo por demora")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["impacto_pct"], "-20.00")

    def test_el_impacto_no_lo_define_el_usuario(self):
        self.datos["impacto_pct"] = "99.00"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.data["impacto_pct"], "10.00")

    def test_fecha_por_defecto_es_hoy(self):
        hoy = timezone.localdate()
        Periodo.objects.create(
            fecha_inicio=hoy.replace(year=hoy.year - 1),
            fecha_termino=hoy.replace(year=hoy.year + 1),
            estado=Periodo.VIGENTE,
        )
        del self.datos["fecha"]
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["fecha"], hoy.isoformat())

    # 3. inválido
    def test_motivo_obligatorio(self):
        self.datos["motivo"] = "   "
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "motivo")

    def test_funcionario_inactivo(self):
        Funcionario.objects.filter(pk=self.ana.pk).update(estado=Funcionario.INACTIVO)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "funcionario")

    def test_fecha_futura_rechazada(self):
        self.datos["fecha"] = "2999-01-01"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "fecha")

    def test_fecha_sin_periodo_rechazada(self):
        self.datos["fecha"] = "2025-05-05"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "fecha")

    def test_tipo_invalido(self):
        self.datos["tipo"] = "premio"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "tipo")

    # tope de 3 felicitaciones por trimestre y funcionario
    def test_tope_de_tres_felicitaciones_por_trimestre(self):
        for dia in ("2026-01-10", "2026-02-10", "2026-03-10"):
            self.datos["fecha"] = dia
            self.assertEqual(self.client.post(URL, self.datos).status_code, 201)
        self.datos["fecha"] = "2026-03-20"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "tipo")
        self.assertEqual(FelicitacionReclamo.objects.count(), 3)

    def test_el_tope_no_afecta_a_otro_trimestre_ni_a_otro_funcionario_ni_a_reclamos(self):
        for dia in ("2026-01-10", "2026-02-10", "2026-03-10"):
            self._registrar(fecha=dia)
        # otro trimestre
        self.datos["fecha"] = "2026-04-15"
        self.assertEqual(self.client.post(URL, self.datos).status_code, 201)
        # otro funcionario
        self.datos.update(fecha="2026-03-20", funcionario=self.luis.pk)
        self.assertEqual(self.client.post(URL, self.datos).status_code, 201)
        # un reclamo no cuenta para el tope
        self.datos.update(funcionario=self.ana.pk, tipo="reclamo", motivo="Reclamo")
        self.assertEqual(self.client.post(URL, self.datos).status_code, 201)

    # 2 y 4. no se edita ni se borra (la tabla no tiene estado; queda como historial)
    def test_no_se_edita_ni_se_borra(self):
        fr = self._registrar()
        url = f"{URL}{fr.pk}/"
        self.assertEqual(self.client.patch(url, {"motivo": "otro"}).status_code, 405)
        self.assertEqual(self.client.put(url, self.datos).status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)
        self.assertTrue(FelicitacionReclamo.objects.filter(pk=fr.pk).exists())

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        func = Usuario.objects.create_user(
            email="f@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        self.client.force_authenticate(func)
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", r.data)
        self.assertFalse(FelicitacionReclamo.objects.exists())

    # listado: búsqueda y filtros
    def test_listado_busqueda_y_filtros(self):
        self._registrar("felicitacion", "2026-01-10", self.ana)
        self._registrar("reclamo", "2026-02-10", self.ana)
        self._registrar("felicitacion", "2026-03-10", self.luis)
        r = self.client.get(URL, {"funcionario": self.ana.pk})
        self.assertEqual(r.data["count"], 2)
        r = self.client.get(URL, {"tipo": "reclamo"})
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(URL, {"fecha__gte": "2026-02-01"})
        self.assertEqual(r.data["count"], 2)
        r = self.client.get(URL, {"search": "Rojas"})
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(URL, {"funcionario__delegacion": self.norte.pk})
        self.assertEqual(r.data["count"], 0)

    # HU26: el ajuste entra al cumplimiento ponderado total
    def test_ajuste_del_periodo(self):
        self._registrar("felicitacion", "2026-01-10")
        self._registrar("felicitacion", "2026-02-10")
        self._registrar("reclamo", "2026-03-01")
        self._registrar("felicitacion", "2026-04-10")  # otro período: no cuenta
        self.assertEqual(ajuste_felicitaciones_reclamos(self.ana, self.periodo), Decimal("0.00"))
        self.assertEqual(ajuste_felicitaciones_reclamos(self.luis, self.periodo), Decimal("0"))

    def test_cumplimiento_total_con_ajuste(self):
        self._registrar("felicitacion", "2026-01-10")
        self._registrar("reclamo", "2026-03-01")
        ajuste = ajuste_felicitaciones_reclamos(self.ana, self.periodo)  # +10 - 20 = -10
        self.assertEqual(ajuste, Decimal("-10.00"))
        # actividades: 50.00 + 40.00 = 90.00; con el ajuste queda en 80.00
        total = cumplimiento_ponderado_total([Decimal("50.00"), Decimal("40.00")], ajuste)
        self.assertEqual(total, Decimal("80.00"))
