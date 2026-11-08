#!/bin/sh
# Crea los dos roles de la base y la base de datos. Corre una sola vez, cuando el volumen `datos` está vacío.
#
# - DB_OWNER_USER: dueño de la base y de las tablas. Migra y carga los datos de demo. No es superusuario.
# - DB_APP_USER: el que usa el servidor web. No es dueño ni superusuario: en `auditoria`, `cierre`,
#   `evaluacion` y `senal` solo puede leer e insertar (los permisos los otorga la migración 0004).
#   Así la auditoría no se puede modificar ni con SQL directo del usuario de la aplicación.
#
# El dueño es miembro del rol de la aplicación solo para que las pruebas puedan hacer `SET ROLE`.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
  CREATE ROLE ${DB_OWNER_USER} LOGIN PASSWORD '${DB_OWNER_PASSWORD}' NOSUPERUSER CREATEDB NOCREATEROLE;
  CREATE ROLE ${DB_APP_USER} LOGIN PASSWORD '${DB_APP_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  GRANT ${DB_APP_USER} TO ${DB_OWNER_USER};
  CREATE DATABASE ${DB_NAME} OWNER ${DB_OWNER_USER};
  REVOKE ALL ON DATABASE ${DB_NAME} FROM PUBLIC;
  GRANT CONNECT ON DATABASE ${DB_NAME} TO ${DB_APP_USER};
EOSQL
