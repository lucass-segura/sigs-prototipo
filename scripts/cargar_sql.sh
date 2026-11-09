#!/bin/sh
# Carga db/sql/01_crear_base.sql y db/sql/02_cargar_datos_demo.sql en el contenedor `db` y copia los
# documentos de la demo al volumen `documentos`, para probar la aplicación con esos datos.
#
# Uso:
#   ./scripts/cargar_sql.sh              carga en la base del proyecto (`sigs`, o la de DB_NAME)
#   ./scripts/cargar_sql.sh sigs_prueba  crea y carga una base nueva con ese nombre
#
# Es la forma de tener la base hecha "a mano" con SQL en lugar de dejar que la aplicación migre y siembre:
#   docker compose down -v
#   ./scripts/cargar_sql.sh
#   docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build   # no corre ningún seed
# Con una base de otro nombre, la aplicación tiene que apuntar a ella:
#   DB_NAME=sigs_prueba docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build
#
# Si la base ya tiene el esquema o los usuarios, los scripts lo avisan y no cargan nada.
set -eu

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

SUPERUSUARIO="${POSTGRES_SUPERUSER:-postgres}"
BASE="${1:-${DB_NAME:-sigs}}"

case "$BASE" in
  "" | *[!a-zA-Z0-9_]*)
    echo "Error: el nombre de la base solo puede tener letras, números y guion bajo." >&2
    exit 1
    ;;
esac

for archivo in 01_crear_base.sql 02_cargar_datos_demo.sql; do
  if [ ! -f "db/sql/$archivo" ]; then
    echo "Error: falta db/sql/$archivo. Generalo con ./scripts/generar_sql.sh." >&2
    exit 1
  fi
done

echo "==> Levantando la base de datos (servicio db)"
docker compose up -d --wait db

psql_db() {
  docker compose exec -T db psql -q -o /dev/null -U "$SUPERUSUARIO" -d postgres -v ON_ERROR_STOP=1 -v base="$BASE" "$@"
}

echo "==> Creando la base '$BASE' (01_crear_base.sql)"
psql_db < db/sql/01_crear_base.sql

echo "==> Cargando los datos de demo y los escenarios (02_cargar_datos_demo.sql)"
psql_db < db/sql/02_cargar_datos_demo.sql

echo "==> Copiando los documentos de la demo al volumen 'documentos'"
docker compose run --rm --no-deps -v "$RAIZ/db/sql/documentos:/origen:ro" backend sh -c 'mkdir -p /data/documentos && cp -r /origen/. /data/documentos/'

echo
echo "Listo. Base '$BASE' cargada. Usuarios de demo con la contraseña Demo.Sigs#2026 (por ejemplo perito08@sigs.test)."
echo "Para usarla con la aplicación (sin que corran los seeds):"
if [ "$BASE" = "sigs" ]; then
  echo "  docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build"
else
  echo "  DB_NAME=$BASE docker compose -f docker-compose.yml -f db/sql/compose.sin-seeds.yml up -d --build"
fi
