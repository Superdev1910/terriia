from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core.validators import normalizar_rut, rut_es_valido, validar_rut


class ValidarRutTests(SimpleTestCase):
    def test_rut_valido_con_y_sin_formato(self):
        self.assertTrue(rut_es_valido("11.111.111-1"))
        self.assertTrue(rut_es_valido("12345678-5"))
        self.assertTrue(rut_es_valido("123456785"))

    def test_dv_k(self):
        self.assertTrue(rut_es_valido("10.000.013-k"))

    def test_rut_invalido(self):
        self.assertFalse(rut_es_valido("12345678-9"))
        self.assertFalse(rut_es_valido("abc"))
        self.assertFalse(rut_es_valido(""))

    def test_normalizar(self):
        self.assertEqual(normalizar_rut("12.345.678-5"), "12345678-5")
        self.assertEqual(normalizar_rut("10000013k"), "10000013-K")

    def test_validar_rut_lanza_error(self):
        with self.assertRaises(ValidationError):
            validar_rut("12345678-9")
