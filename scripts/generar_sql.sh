#!/usr/bin/env bash
# Regenera db/sql/01_crear_base.sql y db/sql/02_cargar_datos_demo.sql a partir de la base real.
#
# Los scripts SQL no se escriben a mano: salen de una base descartable que se migra y se siembra con el
# mismo código de la aplicación (`migrate`, `seed_demo` y `seed_escenarios`) y se vuelcan con `pg_dump`.
# Así nunca se desfasan de las migraciones. Correlo cada vez que cambie una migración o los datos de demo.
#
# La base descartable vive en un proyecto de Docker Compose propio (`sigs_generar`), con su propio volumen y
# sin puertos publicados: no toca tu base ni tus volúmenes. Al terminar, el proyecto se elimina.
#
# - 01_crear_base.sql: roles, base, esquema completo (tablas, restricciones, índices, funciones, triggers y
#   permisos) y los datos que la aplicación necesita para funcionar: reglas RS-1.0 y las filas de
#   `django_migrations` (más los tipos de contenido y permisos de Django).
# - 02_cargar_datos_demo.sql: solo datos (usuarios, espacios, casos de la demo y los 30 escenarios), con las
#   secuencias ajustadas. Los archivos de los documentos de la demo se copian a db/sql/documentos/.
#
# Uso: ./scripts/generar_sql.sh
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

DESTINO="$RAIZ/db/sql"
PROYECTO="sigs_generar"

# Siempre los valores por defecto del proyecto, para que el resultado no dependa de un .env local.
export POSTGRES_SUPERUSER="postgres" POSTGRES_SUPERUSER_PASSWORD="postgres"
export DB_NAME="sigs" DB_OWNER_USER="sigs_owner" DB_OWNER_PASSWORD="sigs_owner" DB_APP_USER="sigs_app" DB_APP_PASSWORD="sigs_app"

dc() { docker compose -p "$PROYECTO" "$@"; }

limpiar() {
  dc down -v --remove-orphans --rmi local >/dev/null 2>&1 || true
}
trap limpiar EXIT INT TERM

# Tablas con datos que la aplicación necesita desde el primer arranque: van en el script de creación.
TABLAS_BASE="conjunto_reglas regla django_migrations django_content_type auth_permission"

# pg_dump avisa de que `conjunto_reglas` apunta a sí misma (`basado_en`): no afecta la carga, porque las
# claves foráneas son diferibles y el script se ejecuta en una transacción. Ese aviso se omite.
pg_dump_base() {
  dc exec -T db pg_dump -U "$POSTGRES_SUPERUSER" -d "$DB_NAME" --no-owner "$@" \
    2> >(grep -v -e 'circular foreign-key' -e '^pg_dump: detail: conjunto_reglas' -e '^pg_dump: hint:' >&2 || true)
}

# Quita las líneas \restrict y \unrestrict de pg_dump (llevan un token aleatorio distinto en cada corrida).
sin_ruido() {
  sed -e '/^\\restrict /d' -e '/^\\unrestrict /d'
}

mkdir -p "$DESTINO/documentos"

echo "==> Levantando la base descartable (proyecto $PROYECTO)"
limpiar
dc up -d --wait db

echo "==> Migrando y sembrando (migrate, seed_demo y seed_escenarios)"
dc run --rm --no-deps -e DOCUMENTOS_DIR=/tmp/documentos -v "$DESTINO/documentos:/salida" backend sh -c '
  set -e
  python manage.py migrate --noinput
  python manage.py seed_demo
  python manage.py seed_escenarios
  mkdir -p /tmp/documentos
  cp -r /tmp/documentos/. /salida/
'

echo "==> Escribiendo 01_crear_base.sql"
{
cat <<'ENCABEZADO'
-- =====================================================================================================
-- SIGS · 01_crear_base.sql
-- Crea los roles, la base de datos y el esquema completo del prototipo, con las reglas RS-1.0.
--
-- GENERADO por scripts/generar_sql.sh a partir de la base migrada de verdad. No lo edites a mano:
-- si cambia una migración, volvé a generarlo.
--
-- Qué hace:
--   1. Crea los roles `sigs_owner` (dueño de las tablas; migra) y `sigs_app` (el que usa la aplicación) si
--      no existen. En `auditoria`, `cierre`, `evaluacion` y `senal`, `sigs_app` solo puede leer e insertar.
--   2. Crea la base de datos (por defecto `sigs`) si no existe.
--   3. Crea las tablas, restricciones, índices, funciones, triggers de solo altas y permisos.
--   4. Carga las reglas RS-1.0 y las filas de `django_migrations`, para que Django vea la base como
--      migrada (`python manage.py migrate --check` no informa nada pendiente).
--   Si la base ya tiene el esquema, no hace nada y lo avisa. Se puede correr más de una vez.
--
-- Cómo correrlo (con psql, como superusuario de PostgreSQL):
--     psql -U postgres -f db/sql/01_crear_base.sql
--   Con otro nombre de base:
--     psql -U postgres -v base=sigs_prueba -f db/sql/01_crear_base.sql
--   Con Docker Compose, sobre el contenedor `db` (carga también los datos de demo):
--     ./scripts/cargar_sql.sh
--
-- Después, para tener datos de prueba: db/sql/02_cargar_datos_demo.sql.
--
-- Las contraseñas de los roles (`sigs_owner` y `sigs_app`) son las de desarrollo del docker-compose.yml.
-- Si usás este script fuera de una prueba local, cambialas con ALTER ROLE.
-- =====================================================================================================
\set ON_ERROR_STOP on
\if :{?base}
\else
  \set base sigs
\endif

-- 1. Roles (protegidos con DO para poder correr el script otra vez)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sigs_owner') THEN
    CREATE ROLE sigs_owner LOGIN PASSWORD 'sigs_owner' NOSUPERUSER CREATEDB NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'sigs_app') THEN
    CREATE ROLE sigs_app LOGIN PASSWORD 'sigs_app' NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
  -- El dueño es miembro del rol de la aplicación solo para que las pruebas puedan hacer SET ROLE.
  IF NOT pg_has_role('sigs_owner', 'sigs_app', 'MEMBER') THEN
    GRANT sigs_app TO sigs_owner;
  END IF;
END
$$;

-- 2. Base de datos
SELECT format('CREATE DATABASE %I OWNER sigs_owner', :'base')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'base')
\gexec
REVOKE ALL ON DATABASE :"base" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"base" TO sigs_app;

\connect :base
SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'siniestro') AS ya_existe \gset

\if :ya_existe
  \echo 'La base ya tiene el esquema de SIGS: no se crea nada.'
\else
-- 3 y 4. Esquema y datos de arranque, creados por el rol dueño (así lo es de las tablas)
SET ROLE sigs_owner;

ENCABEZADO
pg_dump_base --schema-only | sin_ruido
echo
echo "-- Datos de arranque: reglas RS-1.0, migraciones aplicadas y tablas internas de Django"
echo
# shellcheck disable=SC2046
pg_dump_base --data-only --column-inserts $(for t in $TABLAS_BASE; do printf -- '-t public.%s ' "$t"; done) | sin_ruido
cat <<'PIE'

RESET ROLE;
\echo 'Base creada. Cargá los datos de prueba con db/sql/02_cargar_datos_demo.sql.'
\endif
PIE
} > "$DESTINO/01_crear_base.sql"

echo "==> Escribiendo 02_cargar_datos_demo.sql"
{
cat <<'ENCABEZADO'
-- =====================================================================================================
-- SIGS · 02_cargar_datos_demo.sql
-- Carga los datos de demostración (todo ficticio): usuarios, espacios de trabajo, los casos de la
-- narrativa del TFG (EXP-2026-0147 = 55, prioridad alta) y los 30 escenarios de prueba, con sus
-- evaluaciones. Es lo mismo que producen `seed_demo` y `seed_escenarios`.
--
-- GENERADO por scripts/generar_sql.sh. No lo edites a mano.
--
-- Requisito: la base tiene que estar creada con db/sql/01_crear_base.sql.
-- Solo inserta datos, sin desactivar triggers: las tablas de solo altas aceptan INSERT. Las secuencias
-- quedan ajustadas, así que la aplicación puede seguir creando registros. Todo ocurre en una sola
-- transacción: si algo falla no queda nada a medias. Si la base ya tiene usuarios, no hace nada.
--
-- Contraseña de todos los usuarios de demo (ficticia): Demo.Sigs#2026
--
-- Cómo correrlo (con psql, como superusuario de PostgreSQL):
--     psql -U postgres -f db/sql/02_cargar_datos_demo.sql
--   Con otro nombre de base:
--     psql -U postgres -v base=sigs_prueba -f db/sql/02_cargar_datos_demo.sql
--   Con Docker Compose, sobre el contenedor `db`:
--     ./scripts/cargar_sql.sh
--
-- Los archivos de los documentos de la demo están en db/sql/documentos/. Para que se puedan descargar
-- desde la aplicación hay que copiarlos al volumen `documentos` (lo hace ./scripts/cargar_sql.sh).
-- =====================================================================================================
\set ON_ERROR_STOP on
\if :{?base}
\else
  \set base sigs
\endif

\connect :base
SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'siniestro') AS hay_esquema \gset
\if :hay_esquema
\else
  \echo 'Falta crear la base: corré primero db/sql/01_crear_base.sql.'
  \quit
\endif
SELECT EXISTS (SELECT FROM public.usuario) AS ya_hay_datos \gset

\if :ya_hay_datos
  \echo 'La base ya tiene usuarios: no se cargan los datos de demo.'
\else
BEGIN;

ENCABEZADO
# shellcheck disable=SC2046
pg_dump_base --data-only --column-inserts $(for t in $TABLAS_BASE; do printf -- '-T public.%s ' "$t"; done) | sin_ruido
cat <<'PIE'

COMMIT;
\echo 'Datos de demo cargados. Usuarios: perito08@sigs.test, admin.norte@sigs.test, superadmin@sigs.test, etc.'
\endif
PIE
} > "$DESTINO/02_cargar_datos_demo.sql"

echo "==> Listo"
echo "    $DESTINO/01_crear_base.sql   ($(wc -l < "$DESTINO/01_crear_base.sql" | tr -d ' ') líneas)"
echo "    $DESTINO/02_cargar_datos_demo.sql   ($(wc -l < "$DESTINO/02_cargar_datos_demo.sql" | tr -d ' ') líneas)"
echo "    $DESTINO/documentos/   ($(find "$DESTINO/documentos" -type f | wc -l | tr -d ' ') archivo/s)"
