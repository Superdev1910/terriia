from decimal import Decimal

from core.models import Rol
from metas.models import Item, MetaDelegacion, MetaIndividual, Periodo
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario


class DatosMetasMixin:
    def preparar_datos(self):
        self.admin = Usuario.objects.create_user(
            email="admin@terriia.cl",
            rut="11.111.111-1",
            password="ClaveSegura#2026",
            rol=Rol.objects.get(nombre=Rol.ADMINISTRADOR),
        )
        self.client.force_authenticate(self.admin)
        self.cargo = Cargo.objects.create(nombre="Inspector")
        self.item = Item.objects.create(
            cargo=self.cargo, nombre="Visitas", tipo_meta=Item.CONTEO, ponderador=Decimal("100")
        )
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.periodo = Periodo.objects.create(
            fecha_inicio="2026-01-01", fecha_termino="2026-03-31", estado=Periodo.VIGENTE
        )
        self.ana = self.crear_funcionario("F-0001", "Ana Pérez", self.centro)
        self.luis = self.crear_funcionario("F-0002", "Luis Rojas", self.centro)

    def crear_funcionario(self, identificador, nombre, delegacion):
        return Funcionario.objects.create(
            identificador_inst=identificador, nombre=nombre, cargo=self.cargo, delegacion=delegacion
        )

    def crear_item(self, nombre, tipo=Item.CONTEO, ponderador="100"):
        return Item.objects.create(
            cargo=self.cargo, nombre=nombre, tipo_meta=tipo, ponderador=Decimal(ponderador)
        )

    def crear_meta_delegacion(self, total="100.00", delegacion=None, item=None):
        return MetaDelegacion.objects.create(
            item=item or self.item,
            delegacion=delegacion or self.centro,
            periodo=self.periodo,
            valor_objetivo_total=Decimal(total),
        )

    def crear_meta(self, meta_delegacion, funcionario, valor="40.00"):
        return MetaIndividual.objects.create(
            meta_delegacion=meta_delegacion, funcionario=funcionario, valor_objetivo=Decimal(valor)
        )
