"""Tipos de archivo que se pueden mostrar en línea (S28).

Solo se sirven en línea imágenes (PNG, JPEG, GIF, WebP), PDF y texto plano. El tipo se decide con el tipo que quedó
guardado al subir **y** con la firma del contenido: los dos tienen que coincidir. Todo lo demás (SVG, HTML, XML,
scripts, binarios) solo se puede descargar como adjunto.
"""
import codecs

TEXTO = "text/plain"

# Tipo declarado -> prefijo que tiene que tener el contenido.
FIRMAS = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "application/pdf": (b"%PDF-",),
}
TIPOS_PREVISUALIZABLES = (*FIRMAS, "image/webp", TEXTO)
PREFIJO = 16
_TROZO = 64 * 1024


def tipo_declarado(tipo_contenido):
    """`image/PNG; charset=x` -> `image/png`."""
    return (tipo_contenido or "").split(";")[0].strip().lower()


def previsualizable_por_declaracion(tipo_contenido):
    """Tipo seguro declarado al subir, o `None`. No lee el archivo: la firma se comprueba al servirlo."""
    tipo = tipo_declarado(tipo_contenido)
    return tipo if tipo in TIPOS_PREVISUALIZABLES else None


def _firma_coincide(tipo, cabeza):
    if tipo == "image/webp":
        return cabeza[:4] == b"RIFF" and cabeza[8:12] == b"WEBP"
    return any(cabeza.startswith(f) for f in FIRMAS[tipo])


def _es_texto_utf8(archivo):
    """Texto UTF-8 sin bytes nulos. Se lee por trozos para no cargar el archivo entero."""
    decodificador = codecs.getincrementaldecoder("utf-8")()
    archivo.seek(0)
    while True:
        trozo = archivo.read(_TROZO)
        if not trozo:
            break
        if b"\x00" in trozo:
            return False
        try:
            decodificador.decode(trozo)
        except UnicodeDecodeError:
            return False
    try:
        decodificador.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    archivo.seek(0)
    return True


def tipo_para_servir_en_linea(tipo_contenido, ruta):
    """Tipo con el que se puede servir el archivo en línea, o `None` si solo se puede descargar."""
    tipo = previsualizable_por_declaracion(tipo_contenido)
    if tipo is None:
        return None
    with open(ruta, "rb") as archivo:
        if tipo == TEXTO:
            return TEXTO if _es_texto_utf8(archivo) else None
        return tipo if _firma_coincide(tipo, archivo.read(PREFIJO)) else None


def es_png(contenido):
    return contenido.startswith(FIRMAS["image/png"][0])
