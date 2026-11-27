import os
import secrets
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from atenciones.models import Actividad
from core.models import Rol
from metas.models import MetaIndividual, Periodo
from metas.services import CalculoMetasService
from organizacion.models import Delegacion
from personas.models import Funcionario, Usuario


class CargarDemoTests(TestCase):
    def setUp(self):
        # Clave generada en cada prueba: nunca se escribe una clave literal.
        self.clave = secrets.token_urlsafe(16)
        parche = mock.patch.dict(os.environ, {"DEMO_CLAVE": self.clave})
        parche.start()
        self.addCleanup(parche.stop)

    def cargar(self, *args):
        salida = StringIO()
        call_command("cargar_demo", *args, stdout=salida)
        return salida.getvalue()

    def conteos(self):
        return (
            Usuario.objects.count(),
            Funcionario.objects.count(),
            Delegacion.objects.count(),
            Actividad.objects.count(),
            MetaIndividual.objects.count(),
            Periodo.objects.count(),
        )

    def test_falla_sin_clave(self):
        for valor in ("", "corta"):
            with mock.patch.dict(os.environ, {"DEMO_CLAVE": valor}):
                with self.assertRaises(CommandError):
                    self.cargar()
        self.assertFalse(Usuario.objects.filter(email__endswith="@terriia.test").exists())

    def test_falla_si_la_variable_no_existe(self):
        entorno = {k: v for k, v in os.environ.items() if k != "DEMO_CLAVE"}
        with mock.patch.dict(os.environ, entorno, clear=True):
            with self.assertRaises(CommandError):
                self.cargar()

    def test_un_usuario_por_rol_y_login(self):
        salida = self.cargar()
        self.assertNotIn(self.clave, salida)
        for nombre in Rol.TODOS:
            usuarios = Usuario.objects.filter(rol__nombre=nombre, email__endswith="@terriia.test")
            self.assertTrue(usuarios.exists(), nombre)
            for usuario in usuarios:
                self.assertTrue(usuario.check_password(self.clave))
        for usuario in Usuario.objects.filter(rol__nombre=Rol.FUNCIONARIO):
            self.assertIsNotNone(usuario.funcionario_id)
            self.assertTrue(usuario.funcionario.identificador_inst.startswith("DEMO-"))
        self.assertEqual(Usuario.objects.filter(rol__nombre=Rol.FUNCIONARIO).count(), 3)

    def test_idempotente_y_no_cambia_clave(self):
        self.cargar()
        antes = self.conteos()
        otra = secrets.token_urlsafe(16)
        with mock.patch.dict(os.environ, {"DEMO_CLAVE": otra}):
            self.cargar()
        self.assertEqual(self.conteos(), antes)
        usuario = Usuario.objects.get(email="admin.demo@terriia.test")
        self.assertTrue(usuario.check_password(self.clave))
        self.assertFalse(usuario.check_password(otra))

    def test_periodo_vigente_y_reutilizado(self):
        self.cargar()
        self.assertEqual(Periodo.objects.filter(estado=Periodo.VIGENTE).count(), 1)
        self.cargar()
        self.assertEqual(Periodo.objects.filter(estado=Periodo.VIGENTE).count(), 1)

    def test_reutiliza_periodo_vigente_existente(self):
        from datetime import timedelta

        from django.utils import timezone

        hoy = timezone.localdate()
        existente = Periodo.objects.create(
            fecha_inicio=hoy - timedelta(days=10), fecha_termino=hoy + timedelta(days=10)
        )
        self.cargar()
        self.assertEqual(list(Periodo.objects.all()), [existente])

    def test_dashboard_ejecutivo_alcaldesa(self):
        self.cargar()
        cliente = APIClient()
        cliente.force_authenticate(Usuario.objects.get(email="alcaldesa.demo@terriia.test"))
        respuesta = cliente.get(reverse("dashboard-ejecutivo"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertGreater(respuesta.json()["cumplimiento_global_pct"], 0)

    def test_semaforo_varia_y_hay_estados_mixtos(self):
        self.cargar()
        periodo = Periodo.objects.get(estado=Periodo.VIGENTE)
        colores = {
            CalculoMetasService.calcular_cumplimiento_funcionario(f.pk, periodo.pk)[
                "color_semaforo"
            ]
            for f in Funcionario.objects.filter(identificador_inst__startswith="DEMO-")
        }
        self.assertEqual(colores, {"verde", "ambar", "rojo"})
        estados = set(Actividad.objects.values_list("estado_verificacion", flat=True))
        self.assertEqual(estados, {"aprobada", "pendiente", "rechazada", "antecedentes"})
        self.assertTrue(Actividad.objects.filter(tipo_registro=Actividad.GESTION_SOCIAL).exists())

    def test_borrar_solo_toca_datos_demo(self):
        ajeno = Usuario.objects.create_user(
            email="otro@terriia.cl",
            rut="11111111-1",
            password=secrets.token_urlsafe(16),
            rol=Rol.objects.get(nombre=Rol.FUNCIONARIO),
        )
        self.cargar()
        self.cargar("--borrar")
        self.assertTrue(Usuario.objects.filter(pk=ajeno.pk).exists())
        self.assertEqual(Usuario.objects.filter(email__endswith="@terriia.test").count(), 8)
        self.assertEqual(
            Funcionario.objects.filter(identificador_inst__startswith="DEMO-").count(), 3
        )
