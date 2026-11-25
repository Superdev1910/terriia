"""Permisos y cálculo de los dashboards de metas (pruebas de apoyo)."""

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from atenciones.models import Actividad
from atenciones.tests.utiles import rut_valido
from core.models import Rol
from metas.models import Item, MetaDelegacion, MetaIndividual, Periodo
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario


class DashboardPermisosTests(TestCase):
    contador_rut = 30000000

    def setUp(self):
        self.cargo = Cargo.objects.create(nombre="Territorial")
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1), fecha_termino=date(2026, 3, 31), estado=Periodo.VIGENTE
        )
        self.item = Item.objects.create(
            cargo=self.cargo, nombre="Visitas", tipo_meta=Item.CONTEO, ponderador=Decimal("100")
        )
        self.ana, self.user_ana = self._persona(self.centro, "ana", Rol.FUNCIONARIO)
        self.luis, self.user_luis = self._persona(self.centro, "luis", Rol.FUNCIONARIO)
        _, self.delegado_centro = self._persona(self.centro, "del-cen", Rol.DELEGADO_TERRITORIAL)
        _, self.delegado_norte = self._persona(self.norte, "del-nor", Rol.DELEGADO_TERRITORIAL)
        self.admin = self._usuario("admin", Rol.ADMINISTRADOR, None, None)
        md = MetaDelegacion.objects.create(
            item=self.item,
            delegacion=self.centro,
            periodo=self.periodo,
            valor_objetivo_total=Decimal("100"),
        )
        MetaIndividual.objects.create(
            meta_delegacion=md, funcionario=self.ana, valor_objetivo=Decimal("10")
        )

    def _usuario(self, sufijo, rol, funcionario, delegacion):
        DashboardPermisosTests.contador_rut += 1
        return Usuario.objects.create_user(
            email=f"{sufijo}@terriia.cl",
            rut=rut_valido(DashboardPermisosTests.contador_rut),
            password="PruebaSegura123!",
            rol=Rol.objects.get(nombre=rol),
            funcionario=funcionario,
            delegacion=delegacion,
        )

    def _persona(self, delegacion, sufijo, rol):
        func = Funcionario.objects.create(
            identificador_inst=f"F-{sufijo}",
            nombre=sufijo,
            cargo=self.cargo,
            delegacion=delegacion,
        )
        return func, self._usuario(sufijo, rol, func, delegacion)

    def _get(self, usuario, nombre, argumento, **params):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        url = reverse(nombre, args=[argumento])
        return cliente.get(url, params)

    def _actividad(self, **campos):
        datos = {
            "estado_verificacion": Actividad.VERIF_APROBADA,
            "pondera": True,
            "fecha": timezone.make_aware(datetime(2026, 2, 10, 10, 0)),
        }
        datos.update(campos)
        return Actividad.objects.create(funcionario=self.ana, item=self.item, **datos)

    def test_funcionario_ve_lo_suyo_y_no_lo_de_otro(self):
        self.assertEqual(
            self._get(self.user_ana, "dashboard-funcionario", self.ana.pk).status_code, 200
        )
        self.assertEqual(
            self._get(self.user_ana, "dashboard-funcionario", self.luis.pk).status_code, 403
        )

    def test_delegado_de_otra_delegacion_recibe_403(self):
        r = self._get(self.delegado_norte, "dashboard-funcionario", self.ana.pk)
        self.assertEqual(r.status_code, 403)
        r = self._get(self.delegado_norte, "dashboard-delegacion", self.centro.pk)
        self.assertEqual(r.status_code, 403)

    def test_delegado_ve_su_delegacion(self):
        r = self._get(self.delegado_centro, "dashboard-funcionario", self.ana.pk)
        self.assertEqual(r.status_code, 200)
        r = self._get(self.delegado_centro, "dashboard-delegacion", self.centro.pk)
        self.assertEqual(r.status_code, 200)

    def test_admin_ve_todo(self):
        r = self._get(self.admin, "dashboard-funcionario", self.luis.pk)
        self.assertEqual(r.status_code, 200)
        r = self._get(self.admin, "dashboard-delegacion", self.norte.pk)
        self.assertEqual(r.status_code, 200)

    def test_funcionario_no_ve_dashboard_de_delegacion(self):
        r = self._get(self.user_ana, "dashboard-delegacion", self.centro.pk)
        self.assertEqual(r.status_code, 403)

    def test_inexistentes_dan_404(self):
        self.assertEqual(self._get(self.admin, "dashboard-funcionario", 99999).status_code, 404)
        self.assertEqual(self._get(self.admin, "dashboard-delegacion", 99999).status_code, 404)

    def test_periodo_inexistente_404_y_no_numerico_400(self):
        r = self._get(self.admin, "dashboard-funcionario", self.ana.pk, periodo=99999)
        self.assertEqual(r.status_code, 404)
        r = self._get(self.admin, "dashboard-funcionario", self.ana.pk, periodo="abc")
        self.assertEqual(r.status_code, 400)
        r = self._get(self.admin, "dashboard-delegacion", self.centro.pk, periodo=99999)
        self.assertEqual(r.status_code, 404)
        r = self._get(self.admin, "dashboard-delegacion", self.centro.pk, periodo="abc")
        self.assertEqual(r.status_code, 400)

    def test_avance_cuenta_solo_aprobadas_que_ponderan(self):
        self._actividad(estado_verificacion=Actividad.VERIF_PENDIENTE)
        self._actividad(pondera=False)
        r = self._get(self.admin, "dashboard-funcionario", self.ana.pk)
        self.assertEqual(r.data["items"][0]["avance_aprobado"], 0)
        self._actividad()
        r = self._get(self.admin, "dashboard-funcionario", self.ana.pk)
        self.assertEqual(r.data["items"][0]["avance_aprobado"], 1)
        self.assertGreater(r.data["cumplimiento_bruto"], 0)
