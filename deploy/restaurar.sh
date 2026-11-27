#!/bin/bash
# Restaura un respaldo de TerriIA hecho con deploy/respaldo.sh.
# Uso: bash deploy/restaurar.sh <archivo bd-*.sql.gz | media-*.tar.gz> [otro archivo...]
# Pide confirmación antes de tocar nada. Credenciales: .env (DB_*) o ~/.my.cnf (igual que respaldo.sh).
# Para probar sin riesgo, restaura en otra base: DB_NAME_DESTINO=terriia_prueba bash deploy/restaurar.sh ...
set -euo pipefail
umask 077

PROYECTO_DIR="${PROYECTO_DIR:-/var/www/terriia}"
ENV_FILE="$PROYECTO_DIR/.env"

if [ "$#" -lt 1 ]; then
    echo "Uso: bash deploy/restaurar.sh <bd-*.sql.gz | media-*.tar.gz> [...]" >&2
    exit 1
fi
for archivo in "$@"; do
    [ -f "$archivo" ] || { echo "No existe el archivo: $archivo" >&2; exit 1; }
done

leer_env() {
    [ -f "$ENV_FILE" ] || return 0
    grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//' || true
}

DB_NAME="$(leer_env DB_NAME)"; DB_NAME="${DB_NAME:-terriia}"
DB_NAME_DESTINO="${DB_NAME_DESTINO:-$DB_NAME}"
DB_USER="$(leer_env DB_USER)"; DB_USER="${DB_USER:-terriia}"
DB_HOST="$(leer_env DB_HOST)"; DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="$(leer_env DB_PORT)"; DB_PORT="${DB_PORT:-3306}"
DB_PASSWORD="$(leer_env DB_PASSWORD)"

echo "Se restaurará lo siguiente (REEMPLAZA los datos actuales):"
for archivo in "$@"; do
    case "$archivo" in
        *.sql.gz) echo "  - base de datos '$DB_NAME_DESTINO' desde $archivo" ;;
        *.tar.gz) echo "  - carpeta $PROYECTO_DIR/media desde $archivo" ;;
        *) echo "Tipo de archivo no reconocido: $archivo" >&2; exit 1 ;;
    esac
done
read -r -p "Escribe SI para continuar: " respuesta
[ "$respuesta" = "SI" ] || { echo "Cancelado."; exit 1; }

CRED=""
trap '[ -n "$CRED" ] && rm -f "$CRED"' EXIT
OPCIONES_CRED=()
if [ -n "$DB_PASSWORD" ]; then
    CRED="$(mktemp)"
    printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' \
        "$DB_USER" "$DB_PASSWORD" "$DB_HOST" "$DB_PORT" > "$CRED"
    OPCIONES_CRED=("--defaults-extra-file=$CRED")
else
    OPCIONES_CRED=("--host=$DB_HOST" "--port=$DB_PORT" "--user=$DB_USER")
fi

for archivo in "$@"; do
    case "$archivo" in
        *.sql.gz)
            echo "Restaurando base de datos $DB_NAME_DESTINO..."
            mysql "${OPCIONES_CRED[@]}" -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME_DESTINO\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            gunzip -c "$archivo" | mysql "${OPCIONES_CRED[@]}" "$DB_NAME_DESTINO"
            ;;
        *.tar.gz)
            echo "Restaurando media/..."
            # El tar guarda la carpeta como media/: se extrae dentro del proyecto.
            tar -xzf "$archivo" -C "$PROYECTO_DIR"
            ;;
    esac
done

echo "Listo. Si restauraste la base de producción: sudo systemctl restart gunicorn"
