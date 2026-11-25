"""Avance actual y cumplimiento de un funcionario (HU25 + HU10 + HU26)."""

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from atenciones.models import Actividad
from metas.cumplimiento import avance_actual, cumplimiento_funcionario
from metas.models import FelicitacionReclamo, Item, MetaDelegacion, MetaIndividual, Periodo
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario


def _fecha(texto):
    return timezone.make_aware(datetime.fromisoformat(texto))


class AvanceYCumplimientoTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nombre="Territorial Organización Comunitaria")
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1), fecha_termino=date(2026, 3, 31), estado=Periodo.VIGENTE
        )
        self.ana = self._funcionario("F-0001", "Ana Pérez")
        self.luis = self._funcionario("F-0002", "Luis Rojas")
        self.admin = Usuario.objects.create_user(
            email="admin@terriia.cl", rut="11.111.111-1", password="ClaveSegura#2026"
        )
        self.visitas = self._item("Visitas", Item.CONTEO, "40")
        self.talleres = self._item("Talleres", Item.CONTEO, "60")

    def _funcionario(self, identificador, nombre):
        return Funcionario.objects.create(
            identificador_inst=identificador,
            nombre=nombre,
            cargo=self.cargo,
            delegacion=self.centro,
        )

    def _item(self, nombre, tipo, ponderador):
        return Item.objects.create(
            cargo=self.cargo, nombre=nombre, tipo_meta=tipo, ponderador=Decimal(ponderador)
        )

    def _meta(self, funcionario, item, valor):
        md, _ = MetaDelegacion.objects.get_or_create(
            item=item,
            delegacion=self.centro,
            periodo=self.periodo,
            defaults={"valor_objetivo_total": Decimal("1000")},
        )
        return MetaIndividual.objects.create(
            meta_delegacion=md, funcionario=funcionario, valor_objetivo=Decimal(valor)
        )

    def _actividad(self, funcionario, item, fecha="2026-02-10T10:00", **campos):
        datos = {
            "estado_verificacion": Actividad.VERIF_APROBADA,
            "pondera": True,
            "fecha": _fecha(fecha),
        }
        datos.update(campos)
        return Actividad.objects.create(funcionario=funcionario, item=item, **datos)

    # --- avance actual (HU25) -------------------------------------------------------
    def test_cada_actividad_aprobada_suma_uno(self):
        for _ in range(3):
            self._actividad(self.ana, self.visitas)
        self.assertEqual(avance_actual(self.ana, self.visitas, self.periodo), 3)

    def test_solo_cuentan_las_aprobadas_que_ponderan(self):
        self._actividad(self.ana, self.visitas)
        self._actividad(self.ana, self.visitas, estado_verificacion=Actividad.VERIF_PENDIENTE)
        self._actividad(self.ana, self.visitas, estado_verificacion=Actividad.VERIF_RECHAZADA)
        self._actividad(self.ana, self.visitas, estado_verificacion=Actividad.VERIF_ANTECEDENTES)
        self._actividad(self.ana, self.visitas, pondera=False)
        self.assertEqual(avance_actual(self.ana, self.visitas, self.periodo), 1)

    def test_solo_cuenta_lo_del_funcionario_item_y_periodo(self):
        self._actividad(self.ana, self.visitas)
        self._actividad(self.luis, self.visitas)  # otro funcionario
        self._actividad(self.ana, self.talleres)  # otro ítem
        self._actividad(self.ana, self.visitas, fecha="2026-04-01T09:00")  # otro período
        self._actividad(self.ana, self.visitas, fecha="2025-12-31T23:00")  # antes del período
        self.assertEqual(avance_actual(self.ana, self.visitas, self.periodo), 1)

    def test_los_bordes_del_periodo_cuentan(self):
        self._actividad(self.ana, self.visitas, fecha="2026-01-01T00:00")
        self._actividad(self.ana, self.visitas, fecha="2026-03-31T23:59")
        self.assertEqual(avance_actual(self.ana, self.visitas, self.periodo), 2)

    def test_no_depende_del_estado_operativo_ni_del_tubo(self):
        self._actividad(self.ana, self.visitas, estado=Actividad.INGRESADO, ingreso_a_tubo=False)
        self._actividad(self.ana, self.visitas, estado=Actividad.REALIZADO, ingreso_a_tubo=True)
        self.assertEqual(avance_actual(self.ana, self.visitas, self.periodo), 2)

    def test_item_de_porcentaje_no_se_mide_con_conteo(self):
        soluciones = self._item("Soluciones al ingreso al tubo", Item.PORCENTAJE, "30")
        self._actividad(self.ana, soluciones)
        self.assertIsNone(avance_actual(self.ana, soluciones, self.periodo))

    # --- cumplimiento del funcionario (HU10 + HU26) ---------------------------------
    def test_cumplimiento_suma_ponderados_y_ajuste(self):
        self._meta(self.ana, self.visitas, "4")  # ponderador 40
        self._meta(self.ana, self.talleres, "5")  # ponderador 60
        for _ in range(2):
            self._actividad(self.ana, self.visitas)  # 2 de 4 = 50%  -> 20.00
        for _ in range(6):
            self._actividad(self.ana, self.talleres)  # 6 de 5 = 120% -> 72.00
        FelicitacionReclamo.objects.create(
            funcionario=self.ana,
            tipo=FelicitacionReclamo.FELICITACION,
            fecha="2026-02-15",
            motivo="Buen trabajo",
            usuario_autoriza=self.admin,
        )
        r = cumplimiento_funcionario(self.ana, self.periodo)
        por_item = {f["item"]: f for f in r["actividades"]}
        self.assertEqual(por_item["Visitas"]["porcentaje"], Decimal("50.00"))
        self.assertEqual(por_item["Visitas"]["ponderado"], Decimal("20.00"))
        self.assertFalse(por_item["Visitas"]["cumplida"])
        self.assertEqual(por_item["Talleres"]["porcentaje"], Decimal("120.00"))
        self.assertEqual(por_item["Talleres"]["ponderado"], Decimal("72.00"))
        self.assertTrue(por_item["Talleres"]["cumplida"])
        self.assertEqual(r["ajuste"], Decimal("10.00"))
        self.assertEqual(r["total"], Decimal("102.00"))  # 20 + 72 + 10
        self.assertTrue(r["completo"])

    def test_el_tope_de_150_se_aplica_al_total(self):
        self._meta(self.ana, self.visitas, "2")
        for _ in range(10):
            self._actividad(self.ana, self.visitas)  # 500% -> tope 150% -> 60.00
        r = cumplimiento_funcionario(self.ana, self.periodo)
        self.assertEqual(r["actividades"][0]["porcentaje"], Decimal("150.00"))
        self.assertEqual(r["total"], Decimal("60.00"))

    def test_item_de_porcentaje_deja_el_resultado_incompleto(self):
        soluciones = self._item("Soluciones al ingreso al tubo", Item.PORCENTAJE, "30")
        self._meta(self.ana, self.visitas, "4")
        self._meta(self.ana, soluciones, "80")
        self._actividad(self.ana, self.visitas)
        r = cumplimiento_funcionario(self.ana, self.periodo)
        self.assertFalse(r["completo"])
        self.assertEqual(r["total"], Decimal("10.00"))  # solo Visitas: 25% de 40
        fila = next(f for f in r["actividades"] if f["item"].startswith("Soluciones"))
        self.assertIsNone(fila["avance"])
        self.assertIsNone(fila["ponderado"])

    def test_funcionario_sin_metas(self):
        r = cumplimiento_funcionario(self.luis, self.periodo)
        self.assertEqual(r["actividades"], [])
        self.assertEqual(r["total"], Decimal("0.00"))
        self.assertTrue(r["completo"])
