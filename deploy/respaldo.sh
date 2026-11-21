#!/bin/bash
# Respaldo diario de TerriIA: base de datos MySQL/MariaDB + carpeta media/ (evidencias).
# Uso: bash deploy/respaldo.sh            (ver docs/respaldo-recuperacion.md)
# Credenciales: se leen del .env del proyecto (DB_*) o, si DB_PASSWORD está vacío, de ~/.my.cnf.
# Ninguna clave se escribe en este script ni queda en la lista de procesos.
# Variables opcionales: PROYECTO_DIR (por defecto /var/www/terriia), RESPALDO_DIR (por defecto
# $PROYECTO_DIR/respaldos), RETENCION_DIAS (por defecto 7).
set -euo pipefail
umask 077

PROYECTO_DIR="${PROYECTO_DIR:-/var/www/terriia}"
RESPALDO_DIR="${RESPALDO_DIR:-$PROYECTO_DIR/respaldos}"
RETENCION_DIAS="${RETENCION_DIAS:-7}"
ENV_FILE="$PROYECTO_DIR/.env"

# Lee una variable del .env sin ejecutarlo (así no se interpreta nada del archivo).
leer_env() {
    [ -f "$ENV_FILE" ] || return 0
    grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' || true
}

DB_NAME="$(leer_env DB_NAME)"; DB_NAME="${DB_NAME:-terriia}"
DB_USER="$(leer_env DB_USER)"; DB_USER="${DB_USER:-terriia}"
DB_HOST="$(leer_env DB_HOST)"; DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="$(leer_env DB_PORT)"; DB_PORT="${DB_PORT:-3306}"
DB_PASSWORD="$(leer_env DB_PASSWORD)"

CRED=""
trap '[ -n "$CRED" ] && rm -f "$CRED"' EXIT
OPCIONES_CRED=()
if [ -n "$DB_PASSWORD" ]; then
    # Archivo temporal 600 con la clave: mysqldump lo lee y se borra al salir.
    CRED="$(mktemp)"
    printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' \
        "$DB_USER" "$DB_PASSWORD" "$DB_HOST" "$DB_PORT" > "$CRED"
    OPCIONES_CRED=("--defaults-extra-file=$CRED")
else
    echo "DB_PASSWORD vacío en .env: se usará ~/.my.cnf" >&2
    OPCIONES_CRED=("--host=$DB_HOST" "--port=$DB_PORT" "--user=$DB_USER")
fi

FECHA="$(date +%Y-%m-%d_%H%M%S)"
mkdir -p "$RESPALDO_DIR"

echo "[1/3] Base de datos $DB_NAME..."
# --single-transaction: copia consistente de InnoDB sin bloquear el sitio.
mysqldump "${OPCIONES_CRED[@]}" --single-transaction --routines --default-character-set=utf8mb4 \
    "$DB_NAME" | gzip > "$RESPALDO_DIR/bd-$DB_NAME-$FECHA.sql.gz"

echo "[2/3] Carpeta media/ (evidencias)..."
if [ -d "$PROYECTO_DIR/media" ]; then
    tar -czf "$RESPALDO_DIR/media-$FECHA.tar.gz" -C "$PROYECTO_DIR" media
else
    echo "   (no existe $PROYECTO_DIR/media: aún no hay evidencias)"
fi

echo "[3/3] Rotación: se borran los respaldos de más de $RETENCION_DIAS días..."
find "$RESPALDO_DIR" -maxdepth 1 -type f \( -name 'bd-*.sql.gz' -o -name 'media-*.tar.gz' \) \
    -mtime +"$RETENCION_DIAS" -print -delete

echo "Listo: respaldo $FECHA en $RESPALDO_DIR"
