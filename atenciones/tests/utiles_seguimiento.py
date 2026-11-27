"""Escenario compartido por las pruebas de seguimiento de actividades (solo datos ficticios).

Dos delegaciones (Centro y Norte). En Centro: un Delegado, dos funcionarios con usuario (Ana y
Luis, mismo cargo) y un cargo transversal. En Norte: Pedro. Más un vecino, un territorio por
delegación y los catálogos de atención.
"""

import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone

from atenciones.models import Actividad, SubAtencion, TipoAtencion
from core.models import Rol
from core.validators import calcular_dv
from metas.models import Item
from organizacion.models import Area, Cargo, Delegacion
from personas.models import Funcionario, Usuario
from territorio.models import Territorio, Vecino

CLAVE = "ClaveSegura#2026"
# Hash rápido solo en las pruebas: crear usuarios con el hash real tarda más de un segundo cada uno.
RAPIDO = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
# Imagen PNG mínima válida (1x1) para las pruebas de evidencia.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\x9f\x85"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def rut(cuerpo):
    return f"{cuerpo}-{calcular_dv(cuerpo)}"


class EscenarioSolicitudesMixin:
    def preparar_escenario(self):
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.area_social_centro = Area.objects.get(delegacion=self.centro, nombre=Area.SOCIAL)
        self.area_seg_centro = Area.objects.get(delegacion=self.centro, nombre=Area.SEGURIDAD)
        self.area_social_norte = Area.objects.get(delegacion=self.norte, nombre=Area.SOCIAL)

        self.cargo = Cargo.objects.create(nombre="Asistente social", area=self.area_social_centro)
        self.cargo_seguridad = Cargo.objects.create(nombre="Inspector", area=self.area_seg_centro)
        self.cargo_norte = Cargo.objects.create(
            nombre="Asistente norte", area=self.area_social_norte
        )
        self.cargo_transversal = Cargo.objects.create(nombre="Administrativo")
        self.item = self.crear_item("Visitas domiciliarias", self.cargo)
        self.item_seguridad = self.crear_item("Rondas", self.cargo_seguridad)
        self.item_norte = self.crear_item("Visitas norte", self.cargo_norte)

        self.ana = self.crear_funcionario("F-0001", "Ana Pérez", self.cargo, self.centro)
        self.luis = self.crear_funcionario("F-0002", "Luis Rojas", self.cargo, self.centro)
        self.marta = self.crear_funcionario(
            "F-0004", "Marta Díaz", self.cargo_seguridad, self.centro
        )
        self.pedro = self.crear_funcionario("F-0003", "Pedro Soto", self.cargo_norte, self.norte)

        self.admin = self.crear_usuario("admin@terriia.cl", 11111111, Rol.ADMINISTRADOR)
        self.delegado = self.crear_usuario(
            "delegado@terriia.cl", 22222222, Rol.DELEGADO_TERRITORIAL, delegacion=self.centro
        )
        self.delegado_norte = self.crear_usuario(
            "delegado.norte@terriia.cl", 33333333, Rol.DELEGADO_TERRITORIAL, delegacion=self.norte
        )
        self.usuario_ana = self.crear_usuario(
            "ana@terriia.cl",
            44444444,
            Rol.FUNCIONARIO,
            funcionario=self.ana,
            delegacion=self.centro,
        )
        self.usuario_luis = self.crear_usuario(
            "luis@terriia.cl",
            55555555,
            Rol.FUNCIONARIO,
            funcionario=self.luis,
            delegacion=self.centro,
        )
        self.usuario_pedro = self.crear_usuario(
            "pedro@terriia.cl",
            66666666,
            Rol.FUNCIONARIO,
            funcionario=self.pedro,
            delegacion=self.norte,
        )
        self.alcaldesa = self.crear_usuario("alcaldesa@terriia.cl", 77777777, Rol.ALCALDESA)

        self.t_centro = Territorio.objects.create(delegacion=self.centro, nombre="Plaza")
        self.t_norte = Territorio.objects.create(delegacion=self.norte, nombre="Cerro")
        self.vecino = Vecino.objects.create(
            rut=rut(12345678), nombres="Juana", apellidos="Mora", telefono="+56911112222"
        )
        # Semilla de atenciones/0002: Social > «Otras gestiones» > «Orientación social».
        self.tipo = TipoAtencion.objects.get(area=Area.SOCIAL, nombre="Otras gestiones")
        self.sub = SubAtencion.objects.get(tipo_atencion=self.tipo, nombre="Orientación social")
        self.tipo_seguridad = TipoAtencion.objects.create(area=Area.SEGURIDAD, nombre="Denuncia")

    # --- fábricas -----------------------------------------------------------------------
    def crear_item(self, nombre, cargo):
        return Item.objects.create(cargo=cargo, nombre=nombre, ponderador=Decimal("50"))

    def crear_funcionario(self, identificador, nombre, cargo, delegacion):
        return Funcionario.objects.create(
            identificador_inst=identificador, nombre=nombre, cargo=cargo, delegacion=delegacion
        )

    def crear_usuario(self, email, cuerpo, rol, **extra):
        return Usuario.objects.create_user(
            email=email,
            rut=rut(cuerpo),
            password=CLAVE,
            rol=Rol.objects.get(nombre=rol),
            **extra,
        )

    def crear_actividad(self, autor=None, **extra):
        datos = {
            "funcionario": autor or self.ana,
            "item": self.item,
            "descripcion": "Visita por goteras en el techo",
        }
        datos.update(extra)
        return Actividad.objects.create(**datos)

    def vencida(self, dias=3, **extra):
        """Solicitud con compromiso vencido hace `dias` días."""
        return self.crear_actividad(
            fecha_compromiso=timezone.localdate() - timedelta(days=dias), **extra
        )

    def datos_registro(self, **extra):
        datos = {
            "item": self.item.pk,
            "descripcion": "Vecina pide ayuda con trámite de subsidio",
            "vecino": self.vecino.pk,
            "territorio": self.t_centro.pk,
            "telefono": "+56 9 1111 2222",
        }
        datos.update(extra)
        return datos

    def url(self, actividad, accion=""):
        return f"/api/actividades/{actividad.pk}/{accion + '/' if accion else ''}"


class MediaTemporalMixin:
    """Guarda las fotos de prueba en una carpeta temporal que se borra al terminar."""

    def setUp(self):
        super().setUp()
        self._media = tempfile.mkdtemp(prefix="terriia-media-")
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._limpiar_media)

    def _limpiar_media(self):
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)
