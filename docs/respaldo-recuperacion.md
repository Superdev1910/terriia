# Respaldo y recuperación

Cómo se respalda TerriIA en el servidor y cómo se restaura. Scripts: [`deploy/respaldo.sh`](../deploy/respaldo.sh)
y [`deploy/restaurar.sh`](../deploy/restaurar.sh).

## Qué se respalda

| Qué | Dónde está | Archivo del respaldo |
|---|---|---|
| Base de datos MySQL/MariaDB (`DB_NAME`) | servidor de BD | `bd-<base>-<AAAA-MM-DD_HHMMSS>.sql.gz` (`mysqldump` comprimido) |
| Evidencias subidas (carpeta `media/`, ver `MEDIA_ROOT`) | `/var/www/terriia/media/` | `media-<AAAA-MM-DD_HHMMSS>.tar.gz` |

No se respalda el código (está en GitHub) ni el `.env` (tiene claves: guárdalo aparte, cifrado, por quien administra el servidor).
Las evidencias son archivos y la base solo guarda su ruta: **base y `media/` deben restaurarse de la misma fecha**.

## Frecuencia y retención

- **Frecuencia:** una vez al día, de madrugada (hora de baja carga).
- **Retención:** 7 días. El mismo script borra lo más antiguo (`RETENCION_DIAS=7`).
- **Ubicación:** `/var/backups/terriia/`, fuera del proyecto (cambiable con `RESPALDO_DIR`). Crearla una vez:
  `sudo mkdir -p /var/backups/terriia && sudo chown ec2-user: /var/backups/terriia`. `.gitignore` también excluye
  `/var/backups/terriia/`, `*.sql.gz` y `media-*.tar.gz` por si alguien respalda dentro del repo. Idealmente copiar también a otro lugar
  (otro servidor o un bucket) para no perderlo si falla el disco; eso queda por definir con el cliente.

## Credenciales

El script **no contiene claves**. Lee `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT` del `.env` del proyecto.
Si `DB_PASSWORD` está vacío, usa `~/.my.cnf` del usuario que lo ejecuta:

```ini
# ~/.my.cnf   (chmod 600)
[client]
user=terriia
password=<la clave real, solo en el servidor>
```

## Programarlo (cron)

Ejemplo: todos los días a las 02:30 (`crontab -e` con el usuario del proyecto, por ejemplo `ec2-user`):

```cron
30 2 * * * mkdir -p /var/backups/terriia && bash /var/www/terriia/deploy/respaldo.sh >> /var/backups/terriia/respaldo.log 2>&1
```

Ejecución manual: `bash deploy/respaldo.sh`.

## Cómo restaurar

1. Elige la fecha en `/var/backups/terriia/` (por ejemplo `bd-terriia-2026-11-20_023000.sql.gz` y `media-2026-11-20_023000.tar.gz`).
2. Detén la aplicación: `sudo systemctl stop gunicorn`.
3. Restaura con confirmación (pide escribir `SI`):

   ```bash
   bash deploy/restaurar.sh /var/backups/terriia/bd-terriia-2026-11-20_023000.sql.gz /var/backups/terriia/media-2026-11-20_023000.tar.gz
   ```
4. Inicia: `sudo systemctl start gunicorn` y revisa que el sitio abra, que se pueda ingresar y que una evidencia se descargue.

La restauración **reemplaza** los datos actuales. Si solo falló la base, restaura solo el `.sql.gz`.

## Prueba de restauración (hacerla periódicamente, p. ej. una vez al mes)

Una copia que nunca se restauró no es un respaldo confiable. Prueba sin tocar producción, en otra base:

```bash
DB_NAME_DESTINO=terriia_prueba bash deploy/restaurar.sh /var/backups/terriia/bd-terriia-<fecha>.sql.gz
mysql -e "SELECT COUNT(*) FROM terriia_prueba.actividad; SELECT COUNT(*) FROM terriia_prueba.evidencia;"
mysql -e "DROP DATABASE terriia_prueba;"
```

Compara los conteos con producción y comprueba que `tar -tzf /var/backups/terriia/media-<fecha>.tar.gz | head` lista archivos.
Anota fecha y resultado de cada prueba (quién la hizo y si funcionó).

### Registro de pruebas de restauración

| Fecha | Entorno | Respaldo usado | Resultado | Responsable |
|---|---|---|---|---|
| (por completar) | | | | |
