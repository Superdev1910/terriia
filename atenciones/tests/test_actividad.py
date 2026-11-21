"""Pruebas CP-ACT-01..16 del ingreso de actividades (SCRUM-62). Solo datos ficticios.

Cada prueba indica el código CP, el requerimiento y el resultado esperado. "Ahora" se fija con
mock para que las reglas de fecha y semana no dependan del día en que se corren las pruebas.
"""

from datetime import datetime
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria, Rol
from metas.models import Item
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario
from territorio.models import Territorio, Vecino

from ..models import Actividad, SubAtencion, TipoAtencion
from .utiles import rut_valido

URL = "/api/actividades/"
# Miércoles 18-11-2026 12:00 (hora de Santiago). Semana anterior: lunes 09 a domingo 15.
AHORA = timezone.make_aware(datetime(2026, 11, 18, 12, 0))


def hora(dia, h=10, mes=11):
    return timezone.make_aware(datetime(2026, mes, dia, h, 0))


def con_ahora(momento=AHORA):
    return mock.patch("django.utils.timezone.now", return_value=momento)


class ActividadBase(APITestCase):
    contador_rut = 20000000

    def setUp(self):
        self.del_a = Delegacion.objects.create(codigo="DA", nombre="Delegación A")
        self.del_b = Delegacion.objects.create(codigo="DB", nombre="Delegación B")
        self.cargo = Cargo.objects.create(nombre="Promotor")
        self.otro_cargo = Cargo.objects.create(nombre="Otro cargo")
        self.item = Item.objects.create(cargo=self.cargo, nombre="Visita", ponderador="1.00")
        self.item_ajeno = Item.objects.create(
            cargo=self.otro_cargo, nombre="Ítem ajeno", ponderador="1.00"
        )
        self.func_a, self.user_a = self.crear_autor(self.del_a, "a")
        self.func_b, self.user_b = self.crear_autor(self.del_b, "b")
        self.vecino = self.crear_vecino()

    def nuevo_rut(self):
        ActividadBase.contador_rut += 1
        return rut_valido(ActividadBase.contador_rut)

    def crear_autor(self, delegacion, sufijo, rol=Rol.FUNCIONARIO):
        func = Funcionario.objects.create(
            identificador_inst=f"F-{delegacion.codigo}-{sufijo}",
            nombre=f"Funcionario {sufijo}",
            cargo=self.cargo,
            delegacion=delegacion,
        )
        user = Usuario.objects.create_user(
            email=f"{sufijo}.{delegacion.codigo}@terriia.cl".lower(),
            rut=self.nuevo_rut(),
            password="PruebaSegura123!",
            rol=Rol.objects.get(nombre=rol),
            funcionario=func,
            delegacion=delegacion,
        )
        return func, user

    def crear_vecino(self, telefono="+56911112222", **extra):
        return Vecino.objects.create(
            rut=extra.pop("rut", self.nuevo_rut()),
            nombres="Ana",
            apellidos="Pérez",
            telefono=telefono,
            **extra,
        )

    def datos(self, **extra):
        data = {
            "tipo_registro": "actividad",
            "item": self.item.pk,
            "vecino": self.vecino.pk,
            "fecha": AHORA.isoformat(),
            "contacto": "Ana Pérez",
            "telefono": "+56911112222",
        }
        data.update(extra)
        return data

    def registrar(self, usuario=None, ahora=AHORA, **extra):
        self.client.force_authenticate(usuario or self.user_a)
        with con_ahora(ahora):
            return self.client.post(URL, self.datos(**extra), format="json")

    def crear_en_bd(self, funcionario, fecha, **extra):
        with con_ahora(AHORA):
            return Actividad.objects.create(
                funcionario=funcionario, item=self.item, fecha=fecha, **extra
            )


class ActividadTests(ActividadBase):
    def test_cp_act_01_crear_ok(self):
        """CP-ACT-01 | Req: SCRUM-62 ingreso de actividad | Esperado: 201, el autor y su
        delegación salen del usuario logueado (no del cliente), pondera y queda auditado."""
        r = self.registrar(funcionario=self.func_b.pk)  # el cliente intenta fijar otro autor
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["funcionario"], self.func_a.pk)
        self.assertTrue(r.data["pondera"])
        self.assertEqual(r.data["estado"], "Ingresado")
        self.assertEqual(r.data["estado_verificacion"], "pendiente")
        self.assertTrue(r.data["codigo"].startswith("DA-2026-"))
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="actividad", evento="crear", entidad_id=r.data["id_actividad"]
            ).exists()
        )

    def test_cp_act_02_correlativo_unico(self):
        """CP-ACT-02 | Req: SCRUM-62 código <COD>-<AAAA>-<5 dígitos> | Esperado: correlativo
        creciente y sin repetir por delegación y año; cada delegación parte de 00001."""
        codigos = [self.registrar().data["codigo"] for _ in range(3)]
        self.assertEqual(codigos, ["DA-2026-00001", "DA-2026-00002", "DA-2026-00003"])
        otro = self.registrar(
            usuario=self.user_b, vecino=None, contacto="Luis Soto", telefono="+56933334444"
        )
        self.assertEqual(otro.data["codigo"], "DB-2026-00001")
        self.assertEqual(len(set(Actividad.objects.values_list("codigo", flat=True))), 4)

    def test_cp_act_03_fecha_registro_automatica(self):
        """CP-ACT-03 | Req: SCRUM-62 fecha_registro | Esperado: la fija el servidor al guardar
        y el cliente no puede cambiarla."""
        r = self.registrar(fecha_registro="2020-01-01T00:00:00Z", fecha=hora(17).isoformat())
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        actividad = Actividad.objects.get(pk=r.data["id_actividad"])
        self.assertEqual(actividad.fecha_registro, AHORA)
        self.assertEqual(actividad.fecha, hora(17))

    def test_cp_act_04_octava_del_dia_rechazada(self):
        """CP-ACT-04 | Req: máximo 7 actividades por funcionario al día | Esperado: las 7
        primeras entran y la 8ª recibe 400; otro funcionario no se ve afectado."""
        for _ in range(7):
            self.crear_en_bd(self.func_a, hora(18, 9))
        r = self.registrar()
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "fecha")
        self.assertIn("Máximo 7", r.data["error"])
        self.assertEqual(self.registrar(usuario=self.user_b, vecino=None).status_code, 201)

    def test_cp_act_05_semana_cerrada(self):
        """CP-ACT-05 | Req: semana lunes-domingo cerrada | Esperado: el miércoles ya no se
        puede registrar en la semana anterior (cerró el lunes por 1 día de gracia): 400."""
        r = self.registrar(fecha=hora(13).isoformat())  # viernes de la semana anterior
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cerrada", r.data["error"])

    def test_cp_act_06_dentro_de_la_gracia(self):
        """CP-ACT-06 | Req: SEMANA_CIERRE_DIAS_GRACIA | Esperado: el lunes (día de gracia) aún
        se puede registrar en la semana anterior (201); el martes ya no (400)."""
        lunes = hora(16, 12)
        r = self.registrar(ahora=lunes, fecha=hora(13).isoformat())
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        martes = hora(17, 0)
        r = self.registrar(ahora=martes, fecha=hora(13).isoformat())
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cp_act_07_fecha_futura(self):
        """CP-ACT-07 | Req: no se acepta fecha futura | Esperado: 400 en el campo fecha."""
        r = self.registrar(fecha=hora(19).isoformat())
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "fecha")
        self.assertIn("futura", r.data["error"])

    def test_cp_act_08_delegado_no_pondera(self):
        """CP-ACT-08 | Req: no pondera si el atendido es el delegado | Esperado: se guarda
        (201) con pondera=False y un motivo."""
        _, delegado = self.crear_autor(self.del_a, "del", rol=Rol.DELEGADO_TERRITORIAL)
        vecino = self.crear_vecino(rut=delegado.rut)
        r = self.registrar(vecino=vecino.pk)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertFalse(r.data["pondera"])
        self.assertIn("delegado", r.data["motivo_no_pondera"])

    def test_cp_act_09_sin_telefono_no_pondera(self):
        """CP-ACT-09 | Req: no pondera si falta nombre o teléfono | Esperado: 201 con
        pondera=False y motivo de teléfono; igual si falta el nombre."""
        sin_fono = self.crear_vecino(telefono="")
        r = self.registrar(vecino=sin_fono.pk, telefono="")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertFalse(r.data["pondera"])
        self.assertIn("teléfono", r.data["motivo_no_pondera"])
        r = self.registrar(vecino=None, contacto="")
        self.assertFalse(r.data["pondera"])
        self.assertIn("nombre", r.data["motivo_no_pondera"])

    def test_cp_act_10_coordinacion_no_pondera(self):
        """CP-ACT-10 | Req: coordinación preparatoria no pondera | Esperado: 201 con
        pondera=False; y el cliente no puede forzar pondera=True."""
        r = self.registrar(es_coordinacion_preparatoria=True, pondera=True)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertFalse(r.data["pondera"])
        self.assertIn("coordinación", r.data["motivo_no_pondera"])

    def test_cp_act_11_item_de_otro_cargo(self):
        """CP-ACT-11 | Req: el ítem pertenece al cargo del funcionario | Esperado: 400 en
        el campo item."""
        r = self.registrar(item=self.item_ajeno.pk)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "item")

    def test_cp_act_12_vecino_de_otra_delegacion(self):
        """CP-ACT-12 | Req: vecino/territorio/área de la delegación del funcionario |
        Esperado: 400 con un vecino ya atendido en otra delegación; igual con un territorio
        ajeno."""
        self.registrar(usuario=self.user_b)  # el vecino queda atendido en la delegación B
        r = self.registrar(usuario=self.user_a)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "vecino")
        ajeno = Territorio.objects.create(delegacion=self.del_b, nombre="Sector B")
        r = self.registrar(usuario=self.user_a, vecino=None, territorio=ajeno.pk)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "territorio")

    def test_cp_act_13_no_ve_otra_delegacion(self):
        """CP-ACT-13 | Req: alcance por delegación | Esperado: un usuario de la delegación B
        no ve actividades de A en el listado ni por id (404)."""
        creada = self.registrar(usuario=self.user_a).data
        self.client.force_authenticate(self.user_b)
        self.assertEqual(self.client.get(URL).data["count"], 0)
        self.assertEqual(self.client.get(f"{URL}{creada['id_actividad']}/").status_code, 404)
        _, delegado_b = self.crear_autor(self.del_b, "delb", rol=Rol.DELEGADO_TERRITORIAL)
        self.client.force_authenticate(delegado_b)
        self.assertEqual(self.client.get(URL).data["count"], 0)

    def test_cp_act_14_admin_ve_todo(self):
        """CP-ACT-14 | Req: admin y delegación NULL ven todo | Esperado: el administrador y
        un usuario con delegación NULL ven las actividades de ambas delegaciones; el DELETE
        responde 405."""
        self.registrar(usuario=self.user_a)
        self.registrar(usuario=self.user_b, vecino=None)
        admin = Usuario.objects.create_user(
            email="admin.act@terriia.cl",
            rut=self.nuevo_rut(),
            password="PruebaSegura123!",
            rol=Rol.objects.get(nombre=Rol.ADMINISTRADOR),
        )
        alcaldesa = Usuario.objects.create_user(
            email="alcaldesa.act@terriia.cl",
            rut=self.nuevo_rut(),
            password="PruebaSegura123!",
            rol=Rol.objects.get(nombre=Rol.ALCALDESA),
        )
        for usuario in (admin, alcaldesa):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(URL).data["count"], 2)
        pk = Actividad.objects.first().pk
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.delete(f"{URL}{pk}/").status_code, 405)

    def test_cp_act_15_anonimo_403(self):
        """CP-ACT-15 | Req: acceso autenticado | Esperado: sin sesión, listar y crear dan 403
        y el buscador de vecinos también."""
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.post(URL, self.datos(), format="json").status_code, 403)
        self.assertEqual(self.client.get("/api/vecinos/buscar/?rut=1-9").status_code, 403)

    def test_cp_act_16_autocompletado_rut(self):
        """CP-ACT-16 | Req: autocompletar por RUT | Esperado: GET /api/vecinos/buscar/?rut=
        devuelve los datos del vecino (acepta puntos); 404 si no existe o es de otra
        delegación; 400 con RUT inválido."""
        self.client.force_authenticate(self.user_a)
        con_puntos = f"{self.vecino.rut[:-5]}.{self.vecino.rut[-5:-2]}.{self.vecino.rut[-2:]}"
        r = self.client.get("/api/vecinos/buscar/", {"rut": self.vecino.rut})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["id_vecino"], self.vecino.pk)
        self.assertEqual(r.data["telefono"], "+56911112222")
        r = self.client.get("/api/vecinos/buscar/", {"rut": con_puntos})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/vecinos/buscar/", {"rut": "1-1"}).status_code, 400)
        self.assertEqual(
            self.client.get("/api/vecinos/buscar/", {"rut": self.nuevo_rut()}).status_code, 404
        )
        self.registrar(usuario=self.user_b)  # ahora el vecino pertenece a la delegación B
        self.client.force_authenticate(self.user_a)
        r = self.client.get("/api/vecinos/buscar/", {"rut": self.vecino.rut})
        self.assertEqual(r.status_code, 404)


class ActividadExtrasTests(ActividadBase):
    """Pruebas de apoyo: catálogos, modelo y pantallas (no son parte de CP-ACT-01..16)."""

    def test_sub_atencion_debe_ser_del_tipo(self):
        area = self.del_a.areas.get(nombre="Social")
        tipo = TipoAtencion.objects.create(area="Social", nombre="Tipo X")
        otro = TipoAtencion.objects.create(area="Social", nombre="Tipo Y")
        sub = SubAtencion.objects.create(tipo_atencion=otro, nombre="Sub Y")
        r = self.registrar(area=area.pk, tipo_atencion=tipo.pk, sub_atencion=sub.pk)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["campo"], "sub_atencion")
        tipo.activo = False
        tipo.save()
        r = self.registrar(area=area.pk, tipo_atencion=tipo.pk)
        self.assertEqual(r.data["campo"], "tipo_atencion")

    def test_clean_del_modelo_usa_las_mismas_reglas(self):
        from django.core.exceptions import ValidationError

        actividad = Actividad(funcionario=self.func_a, item=self.item_ajeno, fecha=AHORA)
        with con_ahora(), self.assertRaises(ValidationError) as ctx:
            actividad.clean()
        self.assertIn("item", ctx.exception.message_dict)

    def test_solo_get_y_post(self):
        self.client.force_authenticate(self.user_a)
        creada = self.registrar().data
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.patch(f"{URL}{creada['id_actividad']}/", {}).status_code, 405)

    def test_pantallas_y_menu(self):
        self.client.force_login(self.user_a)
        for nombre in ("atenciones_registrar", "atenciones_mis_registros"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200)
            self.assertIn("Mis registros", r.content.decode())  # el menú trae ambas pantallas
        self.client.logout()
        self.assertEqual(self.client.get(reverse("atenciones_registrar")).status_code, 302)
