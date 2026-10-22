# Modelo de datos — TerriIA (v2.4)

Este es **el diseño oficial de la base de datos**. Antes de crear un modelo en Django, revisa aquí tu tabla.

Archivo: `docs/modelo-fisico-mysql-terriia-v2.4.sql`

## Regla de oro

Tu modelo en `models.py` debe tener **los mismos nombres de tabla, campos y valores** que el SQL.

| En el SQL | En Django |
|---|---|
| `CREATE TABLE area (` | `class Meta: db_table = "area"` |
| `id_area INT AUTO_INCREMENT PRIMARY KEY` | `id_area = models.AutoField(primary_key=True)` |
| `nombre VARCHAR(150) NOT NULL` | `nombre = models.CharField(max_length=150)` |
| `telefono VARCHAR(20)` (sin NOT NULL) | `telefono = models.CharField(max_length=20, blank=True, null=True)` |
| `estado ENUM('vigente','cerrado')` | `estado = models.CharField(max_length=..., choices=[("vigente", "Vigente"), ("cerrado", "Cerrado")])` |
| `activo BOOLEAN DEFAULT TRUE` | `activo = models.BooleanField(default=True)` |
| `id_delegacion INT NOT NULL` + `FOREIGN KEY ... REFERENCES delegacion` | `delegacion = models.ForeignKey(Delegacion, on_delete=models.PROTECT, db_column="id_delegacion")` |
| `UNIQUE` | `unique=True` |

- **No inventes campos ni valores.** Si necesitas uno que no está, avísale a Patricio y se agrega al SQL (nueva versión).
- **No importes el SQL en phpMyAdmin.** Las tablas las crea Django con `python manage.py migrate`; el SQL es solo la referencia.

## Tablas por integrante

| Integrante | Tablas | App |
|---|---|---|
| Brian | delegacion, area, cargo | `organizacion` |
| Pamela | vecino, territorio, junta_vecinos | `territorio` |
| Valentina | periodo, item | `metas` |
| Fernando | funcionario, meta_delegacion, meta | `personas` / `metas` |
| Patricio | rol, usuario, auditoria, codigo_recuperacion | `core` / `personas` |
