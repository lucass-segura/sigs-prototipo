// Marcadores de carga con la forma de lo que viene: la pantalla no salta cuando llegan los datos.

export function EsqueletoLineas({ lineas = 3, etiqueta = "Cargando…" }: { lineas?: number; etiqueta?: string }) {
  return (
    <div className="esqueleto-grupo" role="status" aria-label={etiqueta}>
      {Array.from({ length: lineas }, (_, i) => (
        <div key={i} className="esqueleto esqueleto-linea" style={{ width: `${95 - ((i * 17) % 40)}%` }} />
      ))}
      <span className="solo-lector">{etiqueta}</span>
    </div>
  );
}

export function EsqueletoTabla({ filas = 5, columnas = 5, etiqueta = "Cargando…" }: { filas?: number; columnas?: number; etiqueta?: string }) {
  return (
    <div className="esqueleto-tabla" role="status" aria-label={etiqueta}>
      {Array.from({ length: filas }, (_, f) => (
        <div key={f} className="esqueleto-fila" style={{ gridTemplateColumns: `repeat(${columnas}, minmax(0, 1fr))` }}>
          {Array.from({ length: columnas }, (_, c) => (
            <div key={c} className="esqueleto esqueleto-linea" style={{ width: `${55 + ((f * 7 + c * 13) % 40)}%` }} />
          ))}
        </div>
      ))}
      <span className="solo-lector">{etiqueta}</span>
    </div>
  );
}

export function EsqueletoTarjetas({ cantidad = 4, etiqueta = "Cargando…" }: { cantidad?: number; etiqueta?: string }) {
  return (
    <div className="resumen-tarjetas" role="status" aria-label={etiqueta}>
      {Array.from({ length: cantidad }, (_, i) => (
        <div key={i} className="tarjeta tarjeta-numero">
          <div className="esqueleto esqueleto-linea" style={{ width: "60%" }} />
          <div className="esqueleto esqueleto-numero" />
        </div>
      ))}
      <span className="solo-lector">{etiqueta}</span>
    </div>
  );
}
