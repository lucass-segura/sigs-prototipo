#!/bin/sh
# Genera un .zip limpio del repositorio para subir a Drive.
# Solo incluye archivos versionados en git: quedan afuera node_modules, .venv,
# .next, .env y los volúmenes de Docker.
#
# Uso: ./scripts/empaquetar.sh [destino.zip]
set -e

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "Error: el repositorio no tiene commits. Hacé un commit antes de empaquetar." >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Aviso: hay cambios sin commitear; el zip incluye solo lo commiteado (HEAD)." >&2
fi

FECHA="$(date +%Y%m%d)"
DESTINO="${1:-$RAIZ/dist/SIGS-prototipo-$FECHA.zip}"
mkdir -p "$(dirname "$DESTINO")"

git archive --format=zip --prefix=SIGS-prototipo/ -o "$DESTINO" HEAD

echo "Zip generado: $DESTINO"
echo "Tamaño: $(du -h "$DESTINO" | cut -f1)"
echo "Archivos: $(unzip -l "$DESTINO" | tail -1 | awk '{print $2}')"
