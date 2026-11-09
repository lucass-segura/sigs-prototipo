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
# Los vencimientos de las tareas de la demo salen relativos al día en que se generó el SQL (línea
# `-- generado: AAAA-MM-DD` de 02_cargar_datos_demo.sql). Después de cargar, este script los corre según los días
# transcurridos desde esa fecha, para que haya tareas vencidas, de hoy y de esta semana el día de la prueba.
#
# Si la base ya tiene el esquema o los usuarios, los scripts lo avisan y no cargan nada (ni corren los vencimientos).
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

# Consulta de una sola respuesta sobre la base de la demo (sin formato, sin encabezados)
consulta_db() {
  docker compose exec -T db psql -q -t -A -U "$SUPERUSUARIO" -d "$BASE" -v ON_ERROR_STOP=1 "$@"
}

FECHA_GENERACION="$(sed -n 's/^-- generado: \([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)$/\1/p' db/sql/02_cargar_datos_demo.sql | head -n 1)"

echo "==> Creando la base '$BASE' (01_crear_base.sql)"
psql_db < db/sql/01_crear_base.sql

# Solo se corren los vencimientos si esta carga inserta los datos: con la base ya cargada se correrían dos veces.
if [ "$(consulta_db -c 'SELECT EXISTS (SELECT FROM public.usuario)')" = "t" ]; then
  YA_CARGADA=1
else
  YA_CARGADA=0
fi

echo "==> Cargando los datos de demo y los escenarios (02_cargar_datos_demo.sql)"
psql_db < db/sql/02_cargar_datos_demo.sql

if [ "$YA_CARGADA" = "1" ]; then
  echo "==> La base ya tenía datos: no se corren los vencimientos de las tareas"
elif [ -z "$FECHA_GENERACION" ]; then
  echo "==> Aviso: 02_cargar_datos_demo.sql no trae la línea '-- generado: AAAA-MM-DD'; los vencimientos de las tareas quedan sin correr. Regeneralo con ./scripts/generar_sql.sh." >&2
else
  # Los vencimientos corren los días que pasaron desde la generación (hoy = fecha local de la aplicación). Se hace con el
  # rol dueño de las tablas (`tarea` no es de solo altas, así que se puede actualizar).
  DIAS="$(consulta_db -c "SELECT (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date - DATE '$FECHA_GENERACION'")"
  HOY="$(consulta_db -c "SELECT (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date")"
  CORRIDAS="$(printf '%s\n' \
    "SET ROLE sigs_owner;" \
    "WITH c AS (UPDATE public.tarea SET vence_en = vence_en + $DIAS WHERE vence_en IS NOT NULL RETURNING 1) SELECT count(*) FROM c;" \
    | consulta_db)"
  echo "==> Vencimientos de las tareas corridos $DIAS día(s) (SQL generado el $FECHA_GENERACION, hoy $HOY): $CORRIDAS tarea(s) con fecha"
fi

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
