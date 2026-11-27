from datetime import date, datetime
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from atenciones.models import Actividad
from metas.models import Item, MetaDelegacion, MetaIndividual, Periodo
from metas.services import CalculoMetasService
from organizacion.models import Area, Cargo, Delegacion
from personas.models import Funcionario

Usuario = get_user_model()


class CalculoMetasServiceTestCase(TestCase):
    def setUp(self):
        # 1. Estructura organizativa base (Delegación, Área, Cargo, Funcionario)
        self.delegacion = Delegacion.objects.create(nombre="Delegación Centro", codigo="D01")
        self.area = Area.objects.filter(delegacion=self.delegacion).first()
        if not self.area:
            self.area = Area.objects.create(
                delegacion=self.delegacion, nombre="Social", prioridad=1
            )
        self.cargo = Cargo.objects.create(area=self.area, nombre="Inspector Territorial")
        self.funcionario = Funcionario.objects.create(
            identificador_inst="FUNC-001",
            nombre="Juan Pérez",
            cargo=self.cargo,
            delegacion=self.delegacion,
        )

        # 2. Período de evaluación de 90 días
        self.periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1),
            fecha_termino=date(2026, 3, 31),
            dias_computables=90,
            estado="vigente",
        )

        # 3. Ítem con ponderador del 100%
        self.item = Item.objects.create(
            cargo=self.cargo,
            nombre="Inspección en Terreno",
            tipo_meta="conteo",
            ponderador=Decimal("100.00"),
        )

        # 4a. Meta por Delegación (vínculo con Item, Periodo y Delegación)
        self.meta_delegacion = MetaDelegacion.objects.create(
            item=self.item,
            delegacion=self.delegacion,
            periodo=self.periodo,
            valor_objetivo_total=Decimal("10.00"),
        )

        # 4b. Meta Individual asignada al Funcionario mediante meta_delegacion
        self.meta = MetaIndividual.objects.create(
            funcionario=self.funcionario,
            meta_delegacion=self.meta_delegacion,
            valor_objetivo=Decimal("10.00"),
        )

    def test_calculo_base_sin_actividades(self):
        """1. Prueba que sin actividades el cumplimiento sea 0.00% y semáforo rojo."""
        resultado = CalculoMetasService.calcular_cumplimiento_funcionario(
            funcionario_id=self.funcionario.pk,
            periodo_id=self.periodo.pk,
            fecha_evaluacion=date(2026, 1, 15),
        )
        self.assertEqual(resultado["cumplimiento_computable"], 0.00)
        self.assertEqual(resultado["color_semaforo"], "rojo")

    def test_tope_maximo_computable_120_porcentaje(self):
        """2. Valida que el cumplimiento computable se topa en 120% (bruto 200% -> 120)."""
        for _ in range(20):  # 20 de 10 = 200% bruto
            Actividad.objects.create(
                funcionario=self.funcionario,
                item=self.item,
                tipo_registro=Actividad.ACTIVIDAD,
                estado_verificacion=Actividad.VERIF_APROBADA,
                pondera=True,
                fecha=datetime(2026, 2, 15, 12, 0, tzinfo=timezone.get_current_timezone()),
            )
        resultado = CalculoMetasService.calcular_cumplimiento_funcionario(
            funcionario_id=self.funcionario.pk,
            periodo_id=self.periodo.pk,
            fecha_evaluacion=date(2026, 3, 31),
        )
        self.assertGreater(resultado["cumplimiento_bruto"], 120.00)
        self.assertEqual(resultado["cumplimiento_computable"], 120.00)
