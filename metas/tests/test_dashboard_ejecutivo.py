from datetime import date, datetime
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from atenciones.models import Actividad
from atenciones.tests.utiles import rut_valido
from atenciones.tests.utiles_seguimiento import RAPIDO
from core.models import Rol
from metas.models import Item, MetaDelegacion, MetaIndividual, Periodo
from metas.services import CalculoMetasService
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario
from unittest.mock import patch


@RAPIDO
class DashboardEjecutivoTests(TestCase):
    def setUp(self):
        self.cargo = Cargo.objects.create(nombre="Cargo ejecutivo")
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.sur = Delegacion.objects.create(
            codigo="SUR",
            nombre="Sur",
            estado=Delegacion.INACTIVA,
        )
        self.periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1),
            fecha_termino=date(2026, 3, 31),
            estado=Periodo.VIGENTE,
        )
        self.ana = self._funcionario("F-EJ-001", "Ana Pérez", self.centro)
        self.luis = self._funcionario("F-EJ-002", "Luis Rojas", self.centro)
        self.pedro = self._funcionario("F-EJ-003", "Pedro Soto", self.norte)
        self.sofia = self._funcionario("F-EJ-004", "Sofía Díaz", self.norte)
        inactivo = self._funcionario("F-EJ-005", "Funcionario inactivo", self.centro)
        inactivo.estado = Funcionario.INACTIVO
        inactivo.save(update_fields=["estado"])

        self.alcaldesa = self._usuario("alcaldesa", Rol.ALCALDESA)
        self.admin = self._usuario("admin", Rol.ADMINISTRADOR)
        self.jefe = self._usuario("jefe", Rol.JEFE_DELEGACIONES)
        self.delegado = self._usuario("delegado", Rol.DELEGADO_TERRITORIAL, delegacion=self.centro)
        self.usuario_funcionario = self._usuario(
            "funcionario", Rol.FUNCIONARIO, funcionario=self.ana, delegacion=self.centro
        )

    def _funcionario(self, identificador, nombre, delegacion):
        return Funcionario.objects.create(
            identificador_inst=identificador,
            nombre=nombre,
            cargo=self.cargo,
            delegacion=delegacion,
        )

    def _usuario(self, sufijo, rol, funcionario=None, delegacion=None):
        rut = rut_valido(31000000 + len(sufijo))
        return Usuario.objects.create_user(
            email=f"{sufijo}@terriia.cl",
            rut=rut,
            password="ClaveSegura#2026",
            rol=Rol.objects.get(nombre=rol),
            funcionario=funcionario,
            delegacion=delegacion,
        )

    def _consultar_api(self, usuario, **params):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente.get(reverse("dashboard-ejecutivo"), params)

    def _calculos_esperados(self):
        valores = {
            self.ana.pk: Decimal("100.00"),
            self.luis.pk: Decimal("40.00"),
            self.pedro.pk: Decimal("100.00"),
            self.sofia.pk: Decimal("100.00"),
        }

        def calcular(periodo, funcionario_ids):
            return {pk: valores[pk] for pk in funcionario_ids}

        return patch.object(
            CalculoMetasService,
            "calcular_computable_por_funcionario",
            side_effect=calcular,
        )

    def test_alcaldesa_y_administrador_pueden_consultar_api(self):
        with self._calculos_esperados(), patch.object(
            CalculoMetasService,
            "calcular_porcentaje_esperado",
            return_value=Decimal("80.00"),
        ):
            for usuario in (self.alcaldesa, self.admin):
                respuesta = self._consultar_api(usuario)
                self.assertEqual(respuesta.status_code, 200)

    def test_consolida_global_y_por_delegacion_sin_datos_individuales(self):
        with self._calculos_esperados(), patch.object(
            CalculoMetasService,
            "calcular_porcentaje_esperado",
            return_value=Decimal("80.00"),
        ):
            respuesta = self._consultar_api(self.alcaldesa)

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.data
        self.assertEqual(
            set(datos),
            {
                "periodo",
                "cumplimiento_global_pct",
                "porcentaje_esperado",
                "delegaciones",
            },
        )
        self.assertEqual(datos["cumplimiento_global_pct"], 85.0)
        self.assertEqual(datos["porcentaje_esperado"], 80.0)
        por_codigo = {fila["codigo"]: fila for fila in datos["delegaciones"]}
        self.assertEqual(set(por_codigo), {"CEN", "NOR", "SUR"})
        self.assertEqual(por_codigo["CEN"]["cumplimiento_pct"], 70.0)
        self.assertEqual(por_codigo["CEN"]["color_semaforo"], "ambar")
        self.assertEqual(por_codigo["NOR"]["cumplimiento_pct"], 100.0)
        self.assertEqual(por_codigo["NOR"]["color_semaforo"], "verde")
        self.assertEqual(por_codigo["SUR"]["cumplimiento_pct"], 0.0)
        self.assertEqual(por_codigo["SUR"]["color_semaforo"], "rojo")
        self.assertNotIn("funcionarios", str(datos).lower())
        self.assertNotIn("areas", str(datos).lower())
        self.assertNotIn("solicitudes", str(datos).lower())
        for nombre_personal in ("Ana Pérez", "Luis Rojas", "Pedro Soto", "Sofía Díaz"):
            self.assertNotIn(nombre_personal, str(datos))
        for fila in datos["delegaciones"]:
            self.assertEqual(
                set(fila),
                {
                    "delegacion_id",
                    "codigo",
                    "nombre",
                    "cumplimiento_pct",
                    "porcentaje_esperado",
                    "color_semaforo",
                },
            )

    def test_roles_no_autorizados_reciben_403(self):
        for usuario in (self.jefe, self.delegado, self.usuario_funcionario):
            respuesta = self._consultar_api(usuario)
            self.assertEqual(respuesta.status_code, 403)

    def test_semaforo_conserva_limites_del_servicio_existente(self):
        self.assertEqual(
            CalculoMetasService.calcular_color_semaforo(Decimal("80.00"), Decimal("80.00")),
            "verde",
        )
        self.assertEqual(
            CalculoMetasService.calcular_color_semaforo(Decimal("64.00"), Decimal("80.00")),
            "ambar",
        )
        self.assertEqual(
            CalculoMetasService.calcular_color_semaforo(Decimal("63.99"), Decimal("80.00")),
            "rojo",
        )

    def test_periodo_invalido_o_inexistente_se_rechaza(self):
        self.assertEqual(
            self._consultar_api(self.alcaldesa, periodo="abc").status_code,
            400,
        )
        self.assertEqual(
            self._consultar_api(self.alcaldesa, periodo=999999).status_code,
            404,
        )

    def test_pantalla_solo_es_visible_para_alcaldesa_y_administrador(self):
        url = reverse("metas_dashboard_ejecutivo")
        for usuario in (self.alcaldesa, self.admin):
            self.client.force_login(usuario)
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, "Dashboard ejecutivo municipal")
            self.assertContains(respuesta, "metas/js/dashboard_ejecutivo.js")
            self.assertContains(respuesta, reverse("dashboard-ejecutivo"))
            self.assertNotContains(respuesta, "Ana Pérez")

        self.client.force_login(self.jefe)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_alcaldesa_tiene_enlace_de_menu_y_otros_roles_no(self):
        self.client.force_login(self.alcaldesa)
        contenido = self.client.get(reverse("metas_dashboard_ejecutivo")).content.decode()
        self.assertIn(f'href="{reverse("metas_dashboard_ejecutivo")}"', contenido)

        self.client.force_login(self.jefe)
        contenido_jefe = self.client.get(
            reverse("atenciones_reporte_solicitudes_resueltas")
        ).content.decode()
        self.assertNotIn(f'href="{reverse("metas_dashboard_ejecutivo")}"', contenido_jefe)


@RAPIDO
class DashboardEjecutivoIntegracionTests(TestCase):
    """Cálculo real (sin mocks) del dashboard ejecutivo contra la base de datos."""

    def setUp(self):
        self.cargo = Cargo.objects.create(nombre="Inspector")
        self.item_a = Item.objects.create(
            cargo=self.cargo, nombre="Visitas", tipo_meta=Item.CONTEO, ponderador=Decimal("60")
        )
        self.item_b = Item.objects.create(
            cargo=self.cargo, nombre="Reuniones", tipo_meta=Item.CONTEO, ponderador=Decimal("40")
        )
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.sur = Delegacion.objects.create(codigo="SUR", nombre="Sur")
        self.periodo = Periodo.objects.create(
            fecha_inicio=date(2026, 1, 1),
            fecha_termino=date(2026, 3, 31),
            estado=Periodo.VIGENTE,
        )
        self.md = {}
        for delegacion in (self.centro, self.norte):
            for item in (self.item_a, self.item_b):
                self.md[(delegacion.pk, item.pk)] = MetaDelegacion.objects.create(
                    item=item,
                    delegacion=delegacion,
                    periodo=self.periodo,
                    valor_objetivo_total=Decimal("100.00"),
                )
        self.alcaldesa = Usuario.objects.create_user(
            email="alcaldesa@terriia.cl",
            rut=rut_valido(32000001),
            password="ClaveSegura#2026",
            rol=Rol.objects.get(nombre=Rol.ALCALDESA),
        )
        self.n = 0

    def _funcionario(self, delegacion, metas):
        """metas: {item: valor_objetivo}."""
        self.n += 1
        funcionario = Funcionario.objects.create(
            identificador_inst=f"F-INT-{self.n:03d}",
            nombre=f"Funcionario {self.n}",
            cargo=self.cargo,
            delegacion=delegacion,
        )
        for item, valor in metas.items():
            MetaIndividual.objects.create(
                meta_delegacion=self.md[(delegacion.pk, item.pk)],
                funcionario=funcionario,
                valor_objetivo=Decimal(valor),
            )
        return funcionario

    def _actividades(self, funcionario, item, cantidad, **extra):
        datos = {
            "tipo_registro": Actividad.ACTIVIDAD,
            "estado_verificacion": Actividad.VERIF_APROBADA,
            "pondera": True,
            "fecha": datetime(2026, 2, 15, 12, 0, tzinfo=timezone.get_current_timezone()),
        }
        datos.update(extra)
        for _ in range(cantidad):
            Actividad.objects.create(funcionario=funcionario, item=item, **datos)

    def _consultar(self, **params):
        cliente = APIClient()
        cliente.force_authenticate(self.alcaldesa)
        return cliente.get(reverse("dashboard-ejecutivo"), params)

    def _escenario(self):
        tz = timezone.get_current_timezone()
        self.ana = self._funcionario(self.centro, {self.item_a: "4", self.item_b: "5"})
        self.luis = self._funcionario(self.centro, {self.item_a: "2"})
        self.pedro = self._funcionario(self.norte, {self.item_a: "3"})
        # Ana: 3 de 4 en A (75%) y 5 de 5 en B (100%) -> 45 + 40 = 85
        self._actividades(self.ana, self.item_a, 3)
        self._actividades(self.ana, self.item_b, 5)
        # Ruido que no debe contar
        self._actividades(self.ana, self.item_a, 2, estado_verificacion=Actividad.VERIF_PENDIENTE)
        self._actividades(self.ana, self.item_a, 2, estado_verificacion=Actividad.VERIF_RECHAZADA)
        self._actividades(self.ana, self.item_a, 2, pondera=False)
        self._actividades(self.ana, self.item_a, 2, tipo_registro=Actividad.GESTION_SOCIAL)
        self._actividades(self.ana, self.item_a, 2, fecha=datetime(2025, 12, 31, 23, 59, tzinfo=tz))
        self._actividades(self.ana, self.item_a, 2, fecha=datetime(2026, 4, 1, 0, 0, tzinfo=tz))
        # Luis: 6 de 2 en A (300% * 0.6 = 180) queda topado en 150
        self._actividades(self.luis, self.item_a, 6)
        # Pedro: 1 de 3 en A (33,33% * 0.6 = 20)
        self._actividades(self.pedro, self.item_a, 1)

    def test_calculo_real_por_delegacion_y_global(self):
        self._escenario()
        respuesta = self._consultar()

        self.assertEqual(respuesta.status_code, 200)
        por_codigo = {fila["codigo"]: fila for fila in respuesta.data["delegaciones"]}
        self.assertEqual(por_codigo["CEN"]["cumplimiento_pct"], 117.5)  # (85 + 150) / 2
        self.assertEqual(por_codigo["NOR"]["cumplimiento_pct"], 20.0)
        self.assertEqual(por_codigo["SUR"]["cumplimiento_pct"], 0.0)  # sin funcionarios
        self.assertEqual(respuesta.data["cumplimiento_global_pct"], 85.0)  # (85 + 150 + 20) / 3

    def test_coincide_con_el_calculo_individual(self):
        self._escenario()
        por_codigo = {fila["codigo"]: fila for fila in self._consultar().data["delegaciones"]}
        individual = CalculoMetasService.calcular_cumplimiento_funcionario(
            self.pedro.pk, self.periodo.pk
        )
        self.assertEqual(
            por_codigo["NOR"]["cumplimiento_pct"], individual["cumplimiento_computable"]
        )
        con_periodo = CalculoMetasService.calcular_cumplimiento_funcionario(
            self.ana.pk, self.periodo.pk, periodo=self.periodo
        )
        sin_periodo = CalculoMetasService.calcular_cumplimiento_funcionario(
            self.ana.pk, self.periodo.pk
        )
        self.assertEqual(con_periodo, sin_periodo)
        self.assertEqual(con_periodo["cumplimiento_computable"], 85.0)

    def _consultas(self):
        with CaptureQueriesContext(connection) as contexto:
            respuesta = self._consultar()
        self.assertEqual(respuesta.status_code, 200)
        return len(contexto)

    def test_cantidad_de_consultas_no_crece_con_los_funcionarios(self):
        for delegacion in (self.centro, self.norte):
            for _ in range(2):
                funcionario = self._funcionario(delegacion, {self.item_a: "4", self.item_b: "5"})
                self._actividades(funcionario, self.item_a, 2)
        consultas_con_4 = self._consultas()

        for delegacion in (self.centro, self.norte, self.centro, self.norte):
            funcionario = self._funcionario(delegacion, {self.item_a: "4", self.item_b: "5"})
            self._actividades(funcionario, self.item_a, 2)
            self._actividades(funcionario, self.item_b, 1)
        consultas_con_8 = self._consultas()

        self.assertEqual(consultas_con_4, consultas_con_8)
        self.assertLessEqual(consultas_con_8, 10)

    def test_sin_periodo_vigente_y_sin_parametro_responde_400(self):
        Periodo.objects.update(estado=Periodo.CERRADO)
        self.assertEqual(self._consultar().status_code, 400)

    def test_periodo_no_numerico_responde_400(self):
        self.assertEqual(self._consultar(periodo="abc").status_code, 400)

    def test_sin_autenticar_es_rechazado(self):
        respuesta = APIClient().get(reverse("dashboard-ejecutivo"))
        self.assertIn(respuesta.status_code, (401, 403))
