#!/bin/sh
# Prepara la base y arranca el servidor. Sin pasos manuales extra.
#
# Las migraciones y los datos de demo son tareas administrativas: corren con el rol dueño de la base
# (`DB_OWNER_USER`, el que usa Django por defecto). El servidor web corre con el rol de la aplicación
# (`DB_APP_USER`), que en la auditoría y demás tablas de solo altas solo puede leer e insertar.
set -e

if [ "$1" = "gunicorn" ]; then
  python manage.py migrate --noinput
  if [ "${CARGAR_DATOS_DEMO:-true}" = "true" ]; then
    python manage.py seed_demo --si-vacia
    python manage.py seed_escenarios --si-vacia
  fi
  export DB_USER="${DB_APP_USER:-sigs_app}"
  export DB_PASSWORD="${DB_APP_PASSWORD:-sigs_app}"
fi

exec "$@"
