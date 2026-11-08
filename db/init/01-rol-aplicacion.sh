#!/bin/sh
# Crea el rol de la aplicación (sin superusuario) y su base de datos.
# Corre una sola vez, cuando el volumen `datos` está vacío.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
  CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}' NOSUPERUSER CREATEDB NOCREATEROLE;
  CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
EOSQL
