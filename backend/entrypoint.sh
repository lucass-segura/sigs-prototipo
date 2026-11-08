#!/bin/sh
# Prepara la base y arranca el servidor. Sin pasos manuales extra.
set -e

if [ "$1" = "gunicorn" ]; then
  python manage.py migrate --noinput
  if [ "${CARGAR_DATOS_DEMO:-true}" = "true" ]; then
    python manage.py seed_demo --si-vacia
    python manage.py seed_escenarios --si-vacia
  fi
fi

exec "$@"
