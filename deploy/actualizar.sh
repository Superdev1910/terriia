#!/bin/bash
# Actualiza el servidor con lo último de main. Uso: bash deploy/actualizar.sh
set -e
cd /var/www/terriia
git pull origin main
source venv/bin/activate
pip install -r requirements-servidor.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn
echo "Listo: servidor actualizado."
