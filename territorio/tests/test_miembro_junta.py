from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria, Rol
from organizacion.models import Delegacion

from ..models import JuntaVecinos, MiembroJunta, Territorio, Vecino
from .utiles import (
    crear_admin,
    crear_funcionario,
    crear_funcionario_con_delegacion,
    crear_usuario,
    rut_valido,
)


class MiembroJuntaBase(APITestCase):
    url = "/api/miembros-junta/"

    def setUp(self):
        self.admin = crear_admin()
        self.client.force_authenticate(self.admin)
        self.delegacion = Delegacion.objects.create(codigo="D97", nombre="Centro de prueba")
        self.otra = Delegacion.objects.create(codigo="D96", nombre="Sur de prueba")
        territorio = Territorio.objects.create(delegacion=self.delegacion, nombre="Barrio A")
        otro_territorio = Territorio.objects.create(delegacion=self.otra, nombre="Barrio B")
        self.junta = JuntaVecinos.objects.create(
            territorio=territorio, numero_registro="JV-M1", nombre="Junta A"
        )
        self.junta_otra = JuntaVecinos.objects.create(
            territorio=otro_territorio, numero_registro="JV-M2", nombre="Junta B"
        )
        self.v1 = self.vecino(20000001, "Ana")
        self.v2 = self.vecino(20000002, "Beto")
        self.v3 = self.vecino(20000003, "Carla")

    def vecino(self, cuerpo, nombres, estado=Vecino.ACTIVO):
        return Vecino.objects.create(
            rut=rut_valido(cuerpo), nombres=nombres, apellidos="Prueba", estado=estado
        )

    def agregar(self, vecino, cargo="socio", junta=None, **extra):
        datos = {"junta": (junta or self.junta).pk, "vecino": vecino.pk, "cargo": cargo}
        datos.update(extra)
        return self.client.post(self.url, datos)


class MiembroJuntaTests(MiembroJuntaBase):
    def test_agregar_miembro_y_auditar(self):
        response = self.agregar(self.v1, "presidente")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["vecino_rut"], self.v1.rut)
        self.assertEqual(response.data["vecino_nombre"], "Ana Prueba")
        self.assertEqual(response.data["junta_nombre"], "Junta A")
        self.assertEqual(response.data["cargo_display"], "Presidente")
        self.assertEqual(response.data["estado"], "activo")
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="miembro_junta",
                evento="crear",
                entidad_id=response.data["id_miembro_junta"],
            ).exists()
        )

    def test_membresia_activa_duplicada_da_400(self):
        self.agregar(self.v1)
        response = self.agregar(self.v1, "tesorero")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "vecino")
        self.assertIn("ya es miembro activo", response.data["error"])

    def test_vecino_puede_reingresar_si_la_anterior_esta_inactiva(self):
        miembro = self.agregar(self.v1).data["id_miembro_junta"]
        self.client.delete(f"{self.url}{miembro}/")
        self.assertEqual(self.agregar(self.v1).status_code, status.HTTP_201_CREATED)

    def test_segundo_presidente_activo_da_400(self):
        self.agregar(self.v1, "presidente")
        response = self.agregar(self.v2, "presidente")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "cargo")

    def test_presidente_en_otra_junta_es_valido(self):
        self.agregar(self.v1, "presidente")
        response = self.agregar(self.v1, "presidente", junta=self.junta_otra)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_dos_socios_y_dos_directores_son_validos(self):
        self.assertEqual(self.agregar(self.v1, "socio").status_code, 201)
        self.assertEqual(self.agregar(self.v2, "socio").status_code, 201)
        self.assertEqual(self.agregar(self.v3, "director").status_code, 201)
        extra = self.vecino(20000004, "Diana")
        self.assertEqual(self.agregar(extra, "director").status_code, 201)

    def test_vecino_inactivo_da_400(self):
        inactivo = self.vecino(20000005, "Eva", Vecino.INACTIVO)
        response = self.agregar(inactivo)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("vecino activo", response.data["error"])

    def test_junta_inactiva_da_400(self):
        self.junta.activa = False
        self.junta.save()
        self.assertEqual(self.agregar(self.v1).status_code, status.HTTP_400_BAD_REQUEST)

    def test_quitar_desactiva_y_fija_fecha_salida(self):
        pk = self.agregar(self.v1, "presidente").data["id_miembro_junta"]
        response = self.client.delete(f"{self.url}{pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        miembro = MiembroJunta.objects.get(pk=pk)
        self.assertEqual(miembro.estado, MiembroJunta.INACTIVO)
        self.assertEqual(miembro.fecha_salida, date.today())
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="miembro_junta", evento="desactivar", entidad_id=pk
            ).exists()
        )
        # El cargo queda libre para otro vecino.
        self.assertEqual(self.agregar(self.v2, "presidente").status_code, 201)

    def test_patch_a_inactivo_completa_fecha_salida(self):
        pk = self.agregar(self.v1).data["id_miembro_junta"]
        response = self.client.patch(f"{self.url}{pk}/", {"estado": "inactivo"})
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["fecha_salida"], date.today().isoformat())

    def test_fecha_salida_anterior_a_ingreso_da_400(self):
        response = self.agregar(
            self.v1,
            fecha_ingreso="2026-05-10",
            fecha_salida="2026-05-01",
            estado="inactivo",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "fecha_salida")

    def test_no_se_puede_cambiar_junta_ni_vecino(self):
        pk = self.agregar(self.v1).data["id_miembro_junta"]
        response = self.client.patch(f"{self.url}{pk}/", {"vecino": self.v2.pk})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filtros_por_junta_y_vecino(self):
        self.agregar(self.v1)
        self.agregar(self.v2, junta=self.junta_otra)
        por_junta = self.client.get(self.url, {"junta": self.junta.pk}).data["results"]
        self.assertEqual([m["vecino"] for m in por_junta], [self.v1.pk])
        por_vecino = self.client.get(self.url, {"vecino": self.v2.pk}).data["results"]
        self.assertEqual([m["junta"] for m in por_vecino], [self.junta_otra.pk])

    def test_junta_expone_presidente_vecino_y_total_miembros(self):
        url_junta = f"/api/juntas-vecinos/{self.junta.pk}/"
        antes = self.client.get(url_junta).data
        self.assertIsNone(antes["presidente_vecino"])
        self.assertEqual(antes["total_miembros"], 0)
        self.agregar(self.v1, "presidente")
        self.agregar(self.v2, "socio")
        inactivo = self.agregar(self.v3, "socio").data["id_miembro_junta"]
        self.client.delete(f"{self.url}{inactivo}/")
        despues = self.client.get(url_junta).data
        self.assertEqual(despues["presidente_vecino"], "Ana Prueba")
        self.assertEqual(despues["total_miembros"], 2)
        lista = self.client.get("/api/juntas-vecinos/").data["results"]
        self.assertEqual({j["total_miembros"] for j in lista}, {2, 0})

    def test_vecino_lista_sus_juntas_activas(self):
        self.agregar(self.v1)
        datos = self.client.get(f"/api/vecinos/{self.v1.pk}/").data
        self.assertEqual(datos["juntas"], "Junta A")

    def test_delegado_gestiona_solo_su_delegacion(self):
        delegado = crear_usuario("del.junta@terriia.cl", 14000000, Rol.DELEGADO_TERRITORIAL)
        delegado.delegacion = self.delegacion
        delegado.save()
        otro_miembro = MiembroJunta.objects.create(junta=self.junta_otra, vecino=self.v3)
        self.client.force_authenticate(delegado)
        self.assertEqual(self.agregar(self.v1).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get(self.url).data["count"], 1)
        self.assertEqual(
            self.agregar(self.v2, junta=self.junta_otra).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(f"{self.url}{otro_miembro.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        otro_miembro.refresh_from_db()
        self.assertEqual(otro_miembro.estado, MiembroJunta.ACTIVO)
        self.assertEqual(MiembroJunta.objects.filter(junta=self.junta_otra).count(), 1)

    def test_funcionario_y_alcaldesa_reciben_403(self):
        alcaldesa = crear_usuario("alc.junta@terriia.cl", 13500001, Rol.ALCALDESA)
        for usuario in (crear_funcionario(), alcaldesa):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(self.agregar(self.v1).status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(MiembroJunta.objects.exists())

    def test_fecha_ingreso_por_defecto_es_hoy(self):
        response = self.agregar(self.v1)
        self.assertEqual(response.data["fecha_ingreso"], date.today().isoformat())
        manana = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(self.agregar(self.v2, fecha_ingreso=manana).status_code, 201)


class MiembroJuntaFuncionarioTests(MiembroJuntaBase):
    """El Funcionario solo suma socios en juntas de su delegación (desde Registrar actividad)."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(crear_funcionario_con_delegacion(self.delegacion))

    def test_agrega_socio_en_su_junta(self):
        r = self.agregar(self.v1, "socio")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_socio_repetido_da_400(self):
        self.agregar(self.v1, "socio")
        self.assertEqual(self.agregar(self.v1, "socio").status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_asigna_cargos_directivos(self):
        for cargo in ("presidente", "secretario", "tesorero"):
            r = self.agregar(self.v1, cargo)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, (cargo, r.data))
        self.assertFalse(MiembroJunta.objects.exists())

    def test_no_agrega_en_junta_de_otra_delegacion(self):
        r = self.agregar(self.v1, "socio", junta=self.junta_otra)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, r.data)
        self.assertFalse(MiembroJunta.objects.exists())

    def test_no_modifica_ni_desactiva(self):
        miembro = MiembroJunta.objects.create(junta=self.junta, vecino=self.v1, cargo="socio")
        detalle = f"{self.url}{miembro.pk}/"
        self.assertEqual(
            self.client.patch(detalle, {"cargo": "presidente"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.delete(detalle).status_code, status.HTTP_403_FORBIDDEN)
        miembro.refresh_from_db()
        self.assertEqual((miembro.cargo, miembro.estado), ("socio", MiembroJunta.ACTIVO))

    def test_lista_solo_miembros_de_su_delegacion(self):
        MiembroJunta.objects.create(junta=self.junta, vecino=self.v1, cargo="socio")
        MiembroJunta.objects.create(junta=self.junta_otra, vecino=self.v2, cargo="socio")
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([m["vecino"] for m in r.data["results"]], [self.v1.pk])
