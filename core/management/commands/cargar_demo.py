"""Carga datos ficticios de demostración (solo para demo o evaluación).

Uso: definir DEMO_CLAVE en el entorno (.env) y ejecutar `python manage.py cargar_demo`.
Es idempotente (get_or_create sobre claves naturales), nunca cambia la clave de un usuario
existente y solo toca datos demo: correos @terriia.test, funcionarios DEMO-* y delegaciones DEMO*.
"""

import os
from datetime import datetime, time, timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from atenciones import reglas
from atenciones.models import (
    Actividad,
    ActividadHistorial,
    Comentario,
    ContadorCodigoActividad,
    Evidencia,
    HistorialVerificacion,
)
from core.models import Auditoria, Rol
from core.validators import calcular_dv
from metas.models import (
    FelicitacionReclamo,
    Item,
    MetaDelegacion,
    MetaIndividual,
    Periodo,
    RecalibracionMeta,
)
from organizacion.models import Area, Cargo, Delegacion
from personas.models import Funcionario, Usuario
from territorio.models import Territorio, Vecino

DOMINIO = "@terriia.test"
PREFIJO_FUNCIONARIO = "DEMO-"
PREFIJO_DELEGACION = "DEMO"
VERSION_PERIODO = "demo"
DIAS_PERIODO = 30

# codigo, nombre, territorio
DELEGACIONES = [
    ("DEMON", "Delegación Norte Demo", "Villa Los Aromos"),
    ("DEMOS", "Delegación Sur Demo", "Población El Sauce"),
    ("DEMOC", "Delegación Centro Demo", "Barrio Pedro de Valdivia"),
]

# cargo -> [(item, ponderador, meta individual)]; los ponderadores de cada cargo suman 100.
CARGOS = {
    "Promotor social (demo)": [
        ("Visita domiciliaria (demo)", "60.00", "10.00"),
        ("Taller comunitario (demo)", "40.00", "5.00"),
    ],
    "Gestor territorial (demo)": [
        ("Reunión con junta de vecinos (demo)", "50.00", "8.00"),
        ("Operativo en terreno (demo)", "50.00", "4.00"),
    ],
}

# (rol, parte local del correo, cuerpo del RUT, índice de delegación o None, ficha o None)
USUARIOS = [
    (Rol.ADMINISTRADOR, "admin.demo", 15000001, None, None),
    (Rol.JEFE_DELEGACIONES, "jefe.demo", 15000002, None, None),
    (Rol.ALCALDESA, "alcaldesa.demo", 15000003, None, None),
    (Rol.DELEGADO_TERRITORIAL, "delegado.demo", 15000004, 0, None),
    (Rol.ENCARGADO_AREA, "encargado.demo", 15000005, 0, None),
    (Rol.FUNCIONARIO, "funcionario.demo", 15000006, 0, "DEMO-FUN1"),
    (Rol.FUNCIONARIO, "funcionario2.demo", 15000007, 1, "DEMO-FUN2"),
    (Rol.FUNCIONARIO, "funcionario3.demo", 15000008, 2, "DEMO-FUN3"),
]

# identificador, nombre, índice de delegación, cargo
FUNCIONARIOS = [
    ("DEMO-FUN1", "Camila Rojas Fuentes", 0, "Promotor social (demo)"),
    ("DEMO-FUN2", "Matías Soto Vergara", 1, "Promotor social (demo)"),
    ("DEMO-FUN3", "Valentina Araya Pizarro", 2, "Gestor territorial (demo)"),
]

# Vecinos por delegación (cada delegación atiende solo a los suyos). El 3.º no tiene teléfono.
VECINOS = [
    [
        ("Ana", "Pérez Núñez", "+56911110001"),
        ("Luis", "Castillo Mora", "+56911110002"),
        ("Rosa", "Tapia Leiva", ""),
    ],
    [
        ("Jorge", "Muñoz Silva", "+56911110003"),
        ("Carmen", "Vidal Ortiz", "+56911110004"),
        ("Pedro", "Salinas Cortés", ""),
    ],
    [
        ("María", "Herrera Bravo", "+56911110005"),
        ("Felipe", "Navarro Ríos", "+56911110006"),
        ("Gloria", "Campos Paredes", ""),
    ],
]
CUERPO_VECINO = 16000101

A, P, R, N = (
    Actividad.VERIF_APROBADA,
    Actividad.VERIF_PENDIENTE,
    Actividad.VERIF_RECHAZADA,
    Actividad.VERIF_ANTECEDENTES,
)
ACT, GS = Actividad.ACTIVIDAD, Actividad.GESTION_SOCIAL
# Plan por funcionario: (verificación, índice de ítem, tipo de registro, índice de vecino).
# Con las metas de arriba, F1 queda en verde, F2 en ámbar y F3 en rojo frente al 50% esperado
# de un período recién creado por este comando.
PLAN = {
    "DEMO-FUN1": [(A, 0, ACT, i % 2) for i in range(8)]
    + [(A, 1, ACT, i % 2) for i in range(4)]
    + [(P, 0, ACT, 0), (P, 0, ACT, 2), (R, 0, ACT, 1), (N, 1, ACT, 1), (P, 0, GS, 0)],
    "DEMO-FUN2": [(A, 0, ACT, i % 2) for i in range(5)]
    + [(A, 1, ACT, i % 2) for i in range(2)]
    + [(P, 0, ACT, 0), (P, 1, ACT, 2), (R, 0, ACT, 1), (A, 1, GS, 1)],
    "DEMO-FUN3": [(A, 0, ACT, i % 2) for i in range(2)]
    + [(A, 1, ACT, 0)]
    + [(P, 0, ACT, 0), (P, 1, ACT, 2), (P, 0, ACT, 1), (N, 0, ACT, 1)],
}


def rut(cuerpo):
    return f"{cuerpo}-{calcular_dv(cuerpo)}"


class Resumen:
    """Cuenta filas creadas y ya existentes por tipo."""

    def __init__(self):
        self.creados, self.existentes = {}, {}

    def anotar(self, nombre, creado):
        destino = self.creados if creado else self.existentes
        destino[nombre] = destino.get(nombre, 0) + 1

    def nombres(self):
        return list(dict.fromkeys(list(self.creados) + list(self.existentes)))


class Command(BaseCommand):
    help = (
        "Carga datos ficticios de demostración (solo demo/evaluación). Requiere DEMO_CLAVE en el "
        "entorno. Es idempotente y no toca datos que no sean demo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--borrar",
            action="store_true",
            help="Borra los datos demo (@terriia.test, DEMO-*, DEMO*) antes de cargarlos.",
        )

    def handle(self, *args, **opciones):
        clave = self._leer_clave()
        self.resumen = Resumen()
        self.hoy = timezone.localdate()
        try:
            with transaction.atomic():
                if opciones["borrar"]:
                    self._borrar()
                    self.stdout.write("Datos demo anteriores borrados.")
                self._cargar(clave)
        except ProtectedError as error:
            raise CommandError(
                "No se pudo borrar: hay datos no demo que dependen de los datos demo "
                f"({error.args[0]})."
            )
        self._informar()

    # --- clave -----------------------------------------------------------------------------
    def _leer_clave(self):
        clave = os.getenv("DEMO_CLAVE", "")
        if len(clave) < 8:
            raise CommandError(
                "Define la variable de entorno DEMO_CLAVE (mínimo 8 caracteres) en el .env "
                "antes de ejecutar cargar_demo."
            )
        try:
            validate_password(clave)
        except ValidationError as error:
            raise CommandError(
                "DEMO_CLAVE no cumple las reglas de contraseña: " + " ".join(error.messages)
            )
        return clave

    # --- carga -----------------------------------------------------------------------------
    def _cargar(self, clave):
        delegaciones = self._delegaciones()
        items = self._cargos_e_items()
        funcionarios = self._funcionarios(delegaciones)
        usuarios = self._usuarios(clave, delegaciones, funcionarios)
        periodo = self._periodo()
        self._metas(periodo, delegaciones, funcionarios, items)
        vecinos = self._vecinos()
        self._actividades(periodo, delegaciones, funcionarios, items, vecinos, usuarios)
        self._felicitacion(funcionarios["DEMO-FUN1"], usuarios["jefe.demo"])

    def _obtener(self, nombre, modelo, buscar, defaults=None):
        objeto, creado = modelo.objects.get_or_create(**buscar, defaults=defaults or {})
        self.resumen.anotar(nombre, creado)
        return objeto

    def _delegaciones(self):
        resultado = []
        for codigo, nombre, territorio in DELEGACIONES:
            delegacion = self._obtener(
                "Delegaciones", Delegacion, {"codigo": codigo}, {"nombre": nombre}
            )
            self._obtener(
                "Territorios", Territorio, {"delegacion": delegacion, "nombre": territorio}
            )
            resultado.append(delegacion)
        return resultado

    def _cargos_e_items(self):
        self.cargos, items = {}, {}
        for nombre_cargo, filas in CARGOS.items():
            cargo = self._obtener("Cargos", Cargo, {"nombre": nombre_cargo, "area": None})
            self.cargos[nombre_cargo] = cargo
            items[nombre_cargo] = [
                self._obtener(
                    "Ítems", Item, {"cargo": cargo, "nombre": nombre}, {"ponderador": ponderador}
                )
                for nombre, ponderador, _meta in filas
            ]
        return items

    def _funcionarios(self, delegaciones):
        resultado = {}
        for ident, nombre, idx, cargo in FUNCIONARIOS:
            funcionario = self._obtener(
                "Funcionarios",
                Funcionario,
                {"identificador_inst": ident},
                {"nombre": nombre, "cargo": self.cargos[cargo], "delegacion": delegaciones[idx]},
            )
            if (
                funcionario.cargo_id != self.cargos[cargo].pk
                or funcionario.delegacion_id != delegaciones[idx].pk
            ):
                raise CommandError(
                    f"El funcionario {ident} ya existe con otro cargo o delegación. "
                    "Ejecuta cargar_demo --borrar para recrear los datos demo."
                )
            resultado[ident] = funcionario
        return resultado

    def _usuarios(self, clave, delegaciones, funcionarios):
        usuarios = {}
        for nombre_rol, local, cuerpo, idx, ficha in USUARIOS:
            email = f"{local}{DOMINIO}"
            usuario = Usuario.objects.filter(email=email).first()
            if usuario:
                self.resumen.anotar("Usuarios", False)
            else:
                while Usuario.objects.filter(rut=rut(cuerpo)).exists():
                    cuerpo += 100  # RUT ocupado por otro usuario: se usa el siguiente libre
                usuario = Usuario.objects.create_user(
                    email=email,
                    rut=rut(cuerpo),
                    password=clave,
                    rol=Rol.objects.get(nombre=nombre_rol),
                    funcionario=funcionarios[ficha] if ficha else None,
                    delegacion=delegaciones[idx] if idx is not None else None,
                )
                self.resumen.anotar("Usuarios", True)
            usuarios[local] = usuario
        return usuarios

    def _periodo(self):
        periodo = Periodo.objects.filter(estado=Periodo.VIGENTE).order_by("-fecha_inicio").first()
        self.resumen.anotar("Períodos", periodo is None)
        if periodo is None:
            periodo = Periodo.objects.create(
                fecha_inicio=self.hoy - timedelta(days=DIAS_PERIODO // 2 - 1),
                fecha_termino=self.hoy + timedelta(days=DIAS_PERIODO // 2),
                dias_computables=DIAS_PERIODO,
                estado=Periodo.VIGENTE,
                version_parametros=VERSION_PERIODO,
            )
        return periodo

    def _metas(self, periodo, delegaciones, funcionarios, items):
        for ident, _nombre, idx, cargo in FUNCIONARIOS:
            for item, (_n, _pond, objetivo) in zip(items[cargo], CARGOS[cargo]):
                meta_delegacion = self._obtener(
                    "Metas de delegación",
                    MetaDelegacion,
                    {"item": item, "delegacion": delegaciones[idx], "periodo": periodo},
                    {"valor_objetivo_total": objetivo},
                )
                self._obtener(
                    "Metas individuales",
                    MetaIndividual,
                    {"meta_delegacion": meta_delegacion, "funcionario": funcionarios[ident]},
                    {"valor_objetivo": objetivo, "unidad": "actividades"},
                )

    def _vecinos(self):
        vecinos, cuerpo = [], CUERPO_VECINO
        for grupo in VECINOS:
            fila = []
            for nombres, apellidos, telefono in grupo:
                fila.append(
                    self._obtener(
                        "Vecinos",
                        Vecino,
                        {"rut": rut(cuerpo)},
                        {"nombres": nombres, "apellidos": apellidos, "telefono": telefono},
                    )
                )
                cuerpo += 1
            vecinos.append(fila)
        return vecinos

    def _fecha(self, periodo, numero):
        """Fecha pasada dentro del período (no valida cierre de semana: es dato histórico)."""
        ultimo = min(self.hoy - timedelta(days=1), periodo.fecha_termino)
        dia = max(ultimo - timedelta(days=numero % 13), periodo.fecha_inicio)
        hora = time(8 + (numero // 13) % 9, 0)
        return timezone.make_aware(datetime.combine(dia, hora))

    def _actividades(self, periodo, delegaciones, funcionarios, items, vecinos, usuarios):
        revisor = usuarios["delegado.demo"]
        for ident, _nombre, idx, cargo in FUNCIONARIOS:
            funcionario = funcionarios[ident]
            area = Area.objects.filter(delegacion=delegaciones[idx], nombre=Area.SOCIAL).first()
            territorio = Territorio.objects.get(
                delegacion=delegaciones[idx], nombre=DELEGACIONES[idx][2]
            )
            for numero, (verif, i_item, tipo, i_vecino) in enumerate(PLAN[ident], start=1):
                descripcion = f"Registro demo {ident} n.° {numero}"
                if Actividad.objects.filter(funcionario=funcionario, descripcion=descripcion):
                    self.resumen.anotar("Actividades", False)
                    continue
                vecino = vecinos[idx][i_vecino]
                item = items[cargo][i_item]
                try:
                    reglas.validar_consistencia(
                        funcionario, item, area=area, territorio=territorio, vecino=vecino
                    )
                except ValidationError as error:
                    raise CommandError(
                        f"Los datos existentes chocan con los demo ({error.message_dict}). "
                        "Ejecuta cargar_demo --borrar para recrearlos."
                    )
                primera = numero == 1 and ident == "DEMO-FUN1"
                datos = {}
                if primera:
                    # Seguimiento: solicitada por el delegado, en proceso y con compromiso.
                    datos = {
                        "origen": Actividad.ORIGEN_DELEGADO,
                        "delegado_solicitante": revisor,
                        "prioridad": "alta",
                        "responsable": funcionario,
                        "estado": Actividad.EN_PROCESO,
                        "fecha_estado": timezone.now(),
                        "usuario_cambio": revisor,
                        "fecha_compromiso": self.hoy + timedelta(days=5),
                    }
                actividad = Actividad(
                    tipo_registro=tipo,
                    funcionario=funcionario,
                    item=item,
                    vecino=vecino,
                    territorio=territorio,
                    area=area,
                    fecha=self._fecha(periodo, numero),
                    descripcion=descripcion,
                    accion="Atención en terreno (dato ficticio)",
                    contacto=f"{vecino.nombres} {vecino.apellidos}" if vecino.telefono else "",
                    telefono=vecino.telefono,
                    estado_verificacion=verif,
                    **datos,
                )
                actividad.pondera, actividad.motivo_no_pondera = reglas.calcular_ponderacion(
                    vecino=vecino, contacto=actividad.contacto, telefono=actividad.telefono
                )
                actividad.save()
                self.resumen.anotar("Actividades", True)
                if verif != P:
                    HistorialVerificacion.objects.create(
                        actividad=actividad,
                        usuario=revisor,
                        estado_anterior=P,
                        estado_nuevo=verif,
                        observacion="Revisión de demostración.",
                    )
                if primera:
                    Comentario.objects.create(
                        actividad=actividad,
                        usuario=revisor,
                        texto="Por favor coordinar la visita con la junta de vecinos.",
                    )
                    self.resumen.anotar("Comentarios", True)

    def _felicitacion(self, funcionario, autoriza):
        self._obtener(
            "Felicitaciones/reclamos",
            FelicitacionReclamo,
            {
                "funcionario": funcionario,
                "tipo": FelicitacionReclamo.FELICITACION,
                "motivo": "Felicitación demo por buena atención",
            },
            {"usuario_autoriza": autoriza},
        )

    # --- borrar ----------------------------------------------------------------------------
    def _borrar(self):
        """Borra solo lo demo y lo que cuelga de ello. Si algo no demo depende, falla y revierte."""
        usuarios = Usuario.objects.filter(email__iendswith=DOMINIO)
        funcionarios = Funcionario.objects.filter(
            identificador_inst__startswith=PREFIJO_FUNCIONARIO
        )
        delegaciones = Delegacion.objects.filter(codigo__startswith=PREFIJO_DELEGACION)
        actividades = Actividad.objects.filter(funcionario__in=funcionarios)
        for modelo in (Comentario, HistorialVerificacion, ActividadHistorial, Evidencia):
            modelo.objects.filter(actividad__in=actividades).delete()
        actividades.delete()
        ContadorCodigoActividad.objects.filter(delegacion__in=delegaciones).delete()
        FelicitacionReclamo.objects.filter(funcionario__in=funcionarios).delete()
        RecalibracionMeta.objects.filter(meta__funcionario__in=funcionarios).delete()
        MetaIndividual.objects.filter(funcionario__in=funcionarios).delete()
        metas = MetaDelegacion.objects.filter(delegacion__in=delegaciones)
        periodos = list(metas.values_list("periodo_id", flat=True).distinct())
        metas.delete()
        Auditoria.objects.filter(usuario__in=usuarios).delete()
        usuarios.delete()
        funcionarios.delete()
        total_vecinos = sum(len(grupo) for grupo in VECINOS)
        ruts = [rut(CUERPO_VECINO + i) for i in range(total_vecinos)]
        Vecino.objects.filter(rut__in=ruts, actividades__isnull=True).delete()
        Item.objects.filter(
            cargo__nombre__in=list(CARGOS), metas_delegacion__isnull=True, actividades__isnull=True
        ).delete()
        Cargo.objects.filter(nombre__in=list(CARGOS), items__isnull=True).delete()
        Territorio.objects.filter(delegacion__in=delegaciones).delete()
        Area.objects.filter(delegacion__in=delegaciones).delete()
        delegaciones.delete()
        Periodo.objects.filter(
            pk__in=periodos, version_parametros=VERSION_PERIODO, metas_delegacion__isnull=True
        ).delete()

    # --- salida ----------------------------------------------------------------------------
    def _informar(self):
        escribir = self.stdout.write
        escribir(self.style.SUCCESS("Datos de demostración listos (solo para demo o evaluación)."))
        escribir("Usuarios demo (rol):")
        for nombre_rol, local, *_ in USUARIOS:
            escribir(f"  {local}{DOMINIO}  ->  {nombre_rol}")
        escribir("Filas creadas / ya existentes:")
        for nombre in self.resumen.nombres():
            creadas = self.resumen.creados.get(nombre, 0)
            existentes = self.resumen.existentes.get(nombre, 0)
            escribir(f"  {nombre}: {creadas} creadas, {existentes} ya existían")
        escribir("La clave de todos los usuarios demo es la que está en DEMO_CLAVE.")
