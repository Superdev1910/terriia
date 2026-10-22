"""Pruebas de integración de organizacion (SCRUM-13 HU17).

Recorren los flujos entre mantenedores: delegacion -> area -> cargo, y su relación con
auditoria, usuarios y permisos. Cada prueba es independiente (base de datos limpia).
"""

import unittest

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Area, Cargo, Delegacion

from .utiles import crear_admin, crear_funcionario

DELEGACIONES, AREAS, CARGOS = "/api/delegaciones/", "/api/areas/", "/api/cargos/"


class FlujoOrganizacionTests(APITestCase):
    def setUp(self):
        self.admin = crear_admin()
        self.client.force_authenticate(self.admin)

    def crear_delegacion(self, codigo="D01", nombre="Centro"):
        r = self.client.post(DELEGACIONES, {"codigo": codigo, "nombre": nombre})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    # INT-ORG-01: delegación -> áreas -> cargo, todo por API
    def test_flujo_completo_delegacion_area_cargo(self):
        d = self.crear_delegacion()
        areas = self.client.get(AREAS, {"delegacion": d["id_delegacion"]}).data
        self.assertEqual(areas["count"], 4)
        social = next(a for a in areas["results"] if a["tipo"] == "social")

        r = self.client.post(CARGOS, {"nombre": "Asistente social", "area": social["id_area"]})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIn("D01", r.data["area_texto"])

        lista = self.client.get(CARGOS, {"area": social["id_area"]}).data
        self.assertEqual(lista["count"], 1)
        self.assertEqual(lista["results"][0]["nombre"], "Asistente social")

    # INT-ORG-02: desactivar en cadena conserva el historial
    def test_desactivar_en_cadena_no_borra_nada(self):
        d = self.crear_delegacion()
        area = Area.objects.filter(delegacion_id=d["id_delegacion"]).first()
        cargo = Cargo.objects.create(nombre="Conductor", area=area)

        self.assertEqual(self.client.delete(f"{CARGOS}{cargo.pk}/").status_code, 204)
        self.assertEqual(self.client.delete(f"{AREAS}{area.pk}/").status_code, 204)
        borrar = self.client.delete(f"{DELEGACIONES}{d['id_delegacion']}/")
        self.assertEqual(borrar.status_code, 204)

        self.assertEqual(Delegacion.objects.count(), 1)
        self.assertEqual(Area.objects.filter(delegacion_id=d["id_delegacion"]).count(), 4)
        cargo.refresh_from_db()
        self.assertFalse(cargo.vigente)
        self.assertEqual(cargo.area_id, area.pk)  # el cargo sigue apuntando a su área
        # El registro inactivo sigue consultable (historial)
        self.assertEqual(self.client.get(f"{DELEGACIONES}{d['id_delegacion']}/").status_code, 200)
        # y no aparece en los listados de opciones activas
        self.assertEqual(self.client.get(DELEGACIONES, {"estado": "activa"}).data["count"], 0)

    # INT-ORG-03: la base impide el borrado físico (FK con PROTECT)
    def test_no_se_puede_borrar_fisicamente_con_dependientes(self):
        d = Delegacion.objects.create(codigo="D01", nombre="Centro")
        area = d.areas.first()
        Cargo.objects.create(nombre="Conductor", area=area)
        with self.assertRaises(ProtectedError):
            area.delete()
        with self.assertRaises(ProtectedError):
            d.delete()

    # INT-ORG-04: la auditoría registra la secuencia completa del flujo
    def test_auditoria_del_flujo(self):
        d = self.crear_delegacion()
        area = Area.objects.filter(delegacion_id=d["id_delegacion"]).first()
        self.client.patch(f"{AREAS}{area.pk}/", {"estado": "inactiva"})
        self.client.post(CARGOS, {"nombre": "Secretaria", "area": None}, format="json")
        eventos = list(
            Auditoria.objects.filter(usuario=self.admin)
            .order_by("fecha", "id_auditoria")
            .values_list("evento", "entidad")
        )
        self.assertEqual(eventos, [("crear", "delegacion"), ("editar", "area"), ("crear", "cargo")])
        editar = Auditoria.objects.get(evento="editar", entidad="area")
        self.assertEqual(editar.valor_anterior["estado"], "activa")
        self.assertEqual(editar.valor_nuevo["estado"], "inactiva")

    # INT-ORG-05: las delegaciones son independientes entre sí
    def test_delegaciones_independientes(self):
        a = self.crear_delegacion("D01", "Centro")
        b = self.crear_delegacion("D02", "Norte")
        self.assertEqual(Area.objects.count(), 8)
        for d in (a, b):  # mismos tipos y prioridades en cada una: válido
            r = self.client.get(AREAS, {"delegacion": d["id_delegacion"]})
            self.assertEqual(sorted(x["prioridad"] for x in r.data["results"]), [1, 2, 3, 4])
        self.assertEqual(self.client.get(AREAS, {"search": "d02"}).data["count"], 4)

    # INT-ORG-06: cargos transversales vs. cargos de área
    def test_cargo_transversal_no_aparece_al_filtrar_por_area(self):
        d = self.crear_delegacion()
        area = Area.objects.filter(delegacion_id=d["id_delegacion"]).first()
        self.client.post(CARGOS, {"nombre": "Secretaria", "area": None}, format="json")
        self.client.post(CARGOS, {"nombre": "Conductor", "area": area.pk})
        self.assertEqual(self.client.get(CARGOS).data["count"], 2)
        self.assertEqual(self.client.get(CARGOS, {"area": area.pk}).data["count"], 1)

    # INT-ORG-07: doble envío del mismo formulario
    def test_doble_envio_no_duplica(self):
        datos = {"codigo": "D01", "nombre": "Centro"}
        r1 = self.client.post(DELEGACIONES, datos)
        r2 = self.client.post(DELEGACIONES, datos)
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(Delegacion.objects.count(), 1)
        self.assertEqual(Area.objects.count(), 4)

    # INT-ORG-08: reactivar una delegación desde el formulario de edición
    def test_reactivar_delegacion(self):
        d = self.crear_delegacion()
        self.client.delete(f"{DELEGACIONES}{d['id_delegacion']}/")
        r = self.client.patch(f"{DELEGACIONES}{d['id_delegacion']}/", {"estado": "activa"})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["estado"], "activa")

    # INT-ORG-09: delegación -> ... -> funcionario -> usuario (HU19)
    @unittest.skip("Pendiente: usuario.id_delegacion y funcionario aún no existen en el repo.")
    def test_delegacion_cargo_funcionario_usuario(self):
        pass


class SeguridadOrganizacionTests(APITestCase):
    """El control de acceso se valida en el servidor, no en la pantalla."""

    def setUp(self):
        self.admin = crear_admin()
        d = Delegacion.objects.create(codigo="D01", nombre="Centro")
        self.area = d.areas.first()
        self.cargo = Cargo.objects.create(nombre="Conductor", area=self.area)
        self.rutas = {
            DELEGACIONES: d.pk,
            AREAS: self.area.pk,
            CARGOS: self.cargo.pk,
        }

    def test_funcionario_no_puede_ninguna_operacion(self):
        self.client.force_authenticate(crear_funcionario())
        for base, pk in self.rutas.items():
            for metodo, url in [
                (self.client.get, base),
                (self.client.post, base),
                (self.client.get, f"{base}{pk}/"),
                (self.client.patch, f"{base}{pk}/"),
                (self.client.delete, f"{base}{pk}/"),
            ]:
                self.assertEqual(metodo(url).status_code, 403, f"{metodo.__name__} {url}")
        self.cargo.refresh_from_db()
        self.assertTrue(self.cargo.vigente)  # el DELETE denegado no desactivó nada

    def test_sin_sesion_denegado(self):
        for base in self.rutas:
            self.assertEqual(self.client.get(base).status_code, 403)

    def test_login_real_admin_y_funcionario(self):
        func = crear_funcionario()
        clave = "ClaveSegura#2026"
        r = self.client.post("/api/auth/login/", {"email": func.email, "password": clave})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(DELEGACIONES).status_code, 403)
        self.client.post("/api/auth/logout/")
        r = self.client.post("/api/auth/login/", {"email": self.admin.email, "password": clave})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(DELEGACIONES).status_code, 200)

    def test_usuario_inactivo_pierde_acceso(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(DELEGACIONES).status_code, 200)
        self.client.force_authenticate(None)
        self.admin.estado = "inactivo"
        self.admin.save()
        clave = "ClaveSegura#2026"
        r = self.client.post("/api/auth/login/", {"email": self.admin.email, "password": clave})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.get(DELEGACIONES).status_code, 403)

    def test_entradas_hostiles_se_tratan_como_datos(self):
        self.client.force_authenticate(self.admin)
        for texto in ["'; DROP TABLE delegacion;--", "<script>alert(1)</script>", "%", "\\"]:
            r = self.client.get(DELEGACIONES, {"search": texto})
            self.assertEqual(r.status_code, 200, texto)
        r = self.client.post(DELEGACIONES, {"codigo": "X1", "nombre": "<b>Norte</b>"})
        self.assertEqual(r.status_code, 201)  # se guarda como texto; la pantalla lo escapa
        self.assertEqual(Delegacion.objects.count(), 2)
