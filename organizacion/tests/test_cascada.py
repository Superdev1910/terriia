"""Desactivación en cadena y relaciones inactivas (SCRUM-13 HU17; casos CAT-05 y CAT-06)."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Area, Cargo, Delegacion

from .utiles import crear_admin

DELEGACIONES, AREAS, CARGOS = "/api/delegaciones/", "/api/areas/", "/api/cargos/"


class BaseCascada(APITestCase):
    def setUp(self):
        self.admin = crear_admin()
        self.client.force_authenticate(self.admin)
        self.delegacion = Delegacion.objects.create(codigo="D01", nombre="Centro")
        self.social = self.delegacion.areas.get(nombre="Social")
        self.territorial = self.delegacion.areas.get(nombre="DISERCO")
        self.cargo_a = Cargo.objects.create(nombre="Asistente social", area=self.social)
        self.cargo_b = Cargo.objects.create(nombre="Inspector", area=self.territorial)
        self.transversal = Cargo.objects.create(nombre="Secretaria", area=None)


class DesactivarEnCascadaTests(BaseCascada):
    # CAT-06: la restricción se explica al usuario (conteos) y la desactivación es consistente
    def test_listado_informa_cuantos_dependientes_se_afectan(self):
        r = self.client.get(f"{DELEGACIONES}{self.delegacion.pk}/")
        self.assertEqual(r.data["areas_activas"], 4)
        # el cargo transversal no depende de la delegación: no se cuenta
        self.assertEqual(r.data["cargos_vigentes"], 2)
        area = self.client.get(f"{AREAS}{self.social.pk}/")
        self.assertEqual(area.data["cargos_vigentes"], 1)

    def test_desactivar_delegacion_desactiva_areas_y_cargos(self):
        r = self.client.delete(f"{DELEGACIONES}{self.delegacion.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.delegacion.areas.filter(estado=Area.ACTIVA).count(), 0)
        self.cargo_a.refresh_from_db()
        self.cargo_b.refresh_from_db()
        self.transversal.refresh_from_db()
        self.assertFalse(self.cargo_a.vigente)
        self.assertFalse(self.cargo_b.vigente)
        self.assertTrue(self.transversal.vigente)  # no pertenece a ninguna delegación

    def test_nada_se_borra_al_desactivar(self):
        self.client.delete(f"{DELEGACIONES}{self.delegacion.pk}/")
        self.assertEqual(Delegacion.objects.count(), 1)
        self.assertEqual(Area.objects.count(), 4)
        self.assertEqual(Cargo.objects.count(), 3)

    def test_desactivar_desde_el_formulario_tambien_arrastra(self):
        r = self.client.patch(
            f"{DELEGACIONES}{self.delegacion.pk}/", {"estado": "inactiva"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(self.delegacion.areas.filter(estado=Area.ACTIVA).count(), 0)
        self.cargo_a.refresh_from_db()
        self.assertFalse(self.cargo_a.vigente)

    def test_editar_sin_cambiar_el_estado_no_arrastra_nada(self):
        self.client.patch(f"{DELEGACIONES}{self.delegacion.pk}/", {"comuna": "Coquimbo"})
        self.assertEqual(self.delegacion.areas.filter(estado=Area.ACTIVA).count(), 4)
        self.cargo_a.refresh_from_db()
        self.assertTrue(self.cargo_a.vigente)

    def test_desactivar_area_desactiva_sus_cargos(self):
        r = self.client.delete(f"{AREAS}{self.social.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.cargo_a.refresh_from_db()
        self.cargo_b.refresh_from_db()
        self.assertFalse(self.cargo_a.vigente)
        self.assertTrue(self.cargo_b.vigente)  # otra área: no se toca
        self.delegacion.refresh_from_db()
        self.assertEqual(self.delegacion.estado, Delegacion.ACTIVA)

    def test_desactivar_cargo_no_afecta_a_nadie_mas(self):
        self.client.delete(f"{CARGOS}{self.cargo_a.pk}/")
        self.social.refresh_from_db()
        self.assertEqual(self.social.estado, Area.ACTIVA)

    def test_cada_registro_arrastrado_queda_en_auditoria(self):
        Auditoria.objects.all().delete()
        self.client.delete(f"{DELEGACIONES}{self.delegacion.pk}/")
        eventos = Auditoria.objects.filter(evento="desactivar")
        self.assertEqual(eventos.filter(entidad="delegacion").count(), 1)
        self.assertEqual(eventos.filter(entidad="area").count(), 4)
        self.assertEqual(eventos.filter(entidad="cargo").count(), 2)
        un_cargo = eventos.get(entidad="cargo", entidad_id=self.cargo_a.pk)
        self.assertTrue(un_cargo.valor_anterior["vigente"])
        self.assertFalse(un_cargo.valor_nuevo["vigente"])
        self.assertEqual(un_cargo.usuario, self.admin)

    def test_reactivar_delegacion_no_reactiva_a_los_dependientes(self):
        self.client.delete(f"{DELEGACIONES}{self.delegacion.pk}/")
        r = self.client.patch(
            f"{DELEGACIONES}{self.delegacion.pk}/", {"estado": "activa"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(self.delegacion.areas.filter(estado=Area.ACTIVA).count(), 0)

    def test_reactivar_en_orden_delegacion_area_cargo(self):
        self.client.delete(f"{DELEGACIONES}{self.delegacion.pk}/")
        self.client.patch(f"{DELEGACIONES}{self.delegacion.pk}/", {"estado": "activa"})
        r = self.client.patch(f"{AREAS}{self.social.pk}/", {"estado": "activa"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        r = self.client.patch(f"{CARGOS}{self.cargo_a.pk}/", {"vigente": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.cargo_a.refresh_from_db()
        self.assertTrue(self.cargo_a.vigente)


class RelacionesInactivasTests(BaseCascada):
    """CAT-05: relación inactiva rechazada en servidor, con mensaje y sin guardado parcial."""

    def inactivar_delegacion(self):
        self.client.delete(f"{DELEGACIONES}{self.delegacion.pk}/")

    # --- área
    def test_no_se_crea_area_en_delegacion_inactiva(self):
        otra = Delegacion.objects.create(codigo="D02", nombre="Norte")
        otra.areas.all().delete()
        self.client.delete(f"{DELEGACIONES}{otra.pk}/")
        antes = Area.objects.count()
        r = self.client.post(AREAS, {"delegacion": otra.pk, "nombre": "Social", "prioridad": 1})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "delegacion")
        self.assertIn("inactiva", r.data["error"])
        self.assertEqual(Area.objects.count(), antes)

    def test_no_se_activa_un_area_si_su_delegacion_sigue_inactiva(self):
        self.inactivar_delegacion()
        r = self.client.patch(f"{AREAS}{self.social.pk}/", {"estado": "activa"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "estado")
        self.social.refresh_from_db()
        self.assertEqual(self.social.estado, Area.INACTIVA)

    def test_si_se_puede_editar_un_area_inactiva_sin_activarla(self):
        self.inactivar_delegacion()
        r = self.client.patch(f"{AREAS}{self.social.pk}/", {"prioridad": 1})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_no_se_mueve_un_area_a_una_delegacion_inactiva(self):
        otra = Delegacion.objects.create(codigo="D02", nombre="Norte")
        otra.areas.all().delete()
        self.client.delete(f"{DELEGACIONES}{otra.pk}/")
        r = self.client.patch(f"{AREAS}{self.social.pk}/", {"delegacion": otra.pk})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    # --- cargo
    def test_no_se_crea_cargo_en_area_inactiva(self):
        self.client.delete(f"{AREAS}{self.social.pk}/")
        antes = Cargo.objects.count()
        r = self.client.post(CARGOS, {"nombre": "Nuevo", "area": self.social.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "area")
        self.assertEqual(Cargo.objects.count(), antes)

    def test_no_se_crea_cargo_en_area_de_delegacion_inactiva(self):
        self.inactivar_delegacion()
        r = self.client.post(CARGOS, {"nombre": "Nuevo", "area": self.social.pk}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_se_marca_vigente_un_cargo_de_area_inactiva(self):
        self.client.delete(f"{AREAS}{self.social.pk}/")
        r = self.client.patch(f"{CARGOS}{self.cargo_a.pk}/", {"vigente": True}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "vigente")
        self.cargo_a.refresh_from_db()
        self.assertFalse(self.cargo_a.vigente)

    def test_si_se_puede_editar_un_cargo_no_vigente_de_area_inactiva(self):
        self.client.delete(f"{AREAS}{self.social.pk}/")
        r = self.client.patch(f"{CARGOS}{self.cargo_a.pk}/", {"descripcion": "Histórico"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_no_se_mueve_un_cargo_a_un_area_inactiva(self):
        self.client.delete(f"{AREAS}{self.territorial.pk}/")
        r = self.client.patch(f"{CARGOS}{self.cargo_a.pk}/", {"area": self.territorial.pk})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.cargo_a.refresh_from_db()
        self.assertEqual(self.cargo_a.area_id, self.social.pk)

    def test_cargo_transversal_no_depende_de_ninguna_area(self):
        self.inactivar_delegacion()
        r = self.client.post(CARGOS, {"nombre": "Conserje", "area": None}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
