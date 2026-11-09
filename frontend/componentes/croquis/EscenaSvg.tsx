// Dibujo del croquis en SVG. Es el mismo dibujo que se ve en el editor, en el icono de la paleta y en el PNG que se
// guarda: todo con atributos propios (sin hojas de estilo), así el SVG serializado se ve igual fuera de la página.
import type { Elemento, Escena, TipoElemento } from "@/lib/croquis";
import { COLOR_TRAZO } from "@/lib/croquis";

const ASFALTO = "#7b827e";
const BORDE_CALLE = "#4d5551";
const RAYA = "#f4f1e6";

function estrella(radioExterior: number, radioInterior: number, puntas: number): string {
  const puntos: string[] = [];
  for (let i = 0; i < puntas * 2; i++) {
    const radio = i % 2 === 0 ? radioExterior : radioInterior;
    const angulo = (Math.PI * i) / puntas - Math.PI / 2;
    puntos.push(`${(radio * Math.cos(angulo)).toFixed(1)},${(radio * Math.sin(angulo)).toFixed(1)}`);
  }
  return puntos.join(" ");
}

const PUNTOS_IMPACTO = estrella(26, 12, 8);

/** El elemento dibujado alrededor de (0, 0), sin posición ni giro. */
function Forma({ e }: { e: Elemento }) {
  const color = e.color ?? COLOR_TRAZO;
  switch (e.tipo) {
    case "calle":
      return (
        <>
          <rect x={-200} y={-45} width={400} height={90} fill={ASFALTO} stroke={BORDE_CALLE} strokeWidth={3} />
          <line x1={-190} y1={0} x2={190} y2={0} stroke={RAYA} strokeWidth={3} strokeDasharray="18 14" />
        </>
      );
    case "cruce":
      return (
        <>
          <rect x={-200} y={-45} width={400} height={90} fill={ASFALTO} stroke={BORDE_CALLE} strokeWidth={3} />
          <rect x={-45} y={-200} width={90} height={400} fill={ASFALTO} stroke={BORDE_CALLE} strokeWidth={3} />
          <rect x={-43.5} y={-48} width={87} height={96} fill={ASFALTO} />
          <rect x={-48} y={-43.5} width={96} height={87} fill={ASFALTO} />
          <g stroke={RAYA} strokeWidth={3} strokeDasharray="18 14">
            <line x1={-190} y1={0} x2={-58} y2={0} />
            <line x1={58} y1={0} x2={190} y2={0} />
            <line x1={0} y1={-190} x2={0} y2={-58} />
            <line x1={0} y1={58} x2={0} y2={190} />
          </g>
        </>
      );
    case "curva":
      return (
        <>
          <path d="M -140 -78 L -40 -78 A 100 100 0 0 1 60 22 L 60 122" fill="none" stroke={BORDE_CALLE} strokeWidth={96} />
          <path d="M -140 -78 L -40 -78 A 100 100 0 0 1 60 22 L 60 122" fill="none" stroke={ASFALTO} strokeWidth={90} />
          <path d="M -135 -78 L -40 -78 A 100 100 0 0 1 60 22 L 60 117" fill="none" stroke={RAYA} strokeWidth={3} strokeDasharray="18 14" />
        </>
      );
    case "rotonda":
      return (
        <>
          <circle r={170} fill={ASFALTO} stroke={BORDE_CALLE} strokeWidth={3} />
          <circle r={125} fill="none" stroke={RAYA} strokeWidth={3} strokeDasharray="18 14" />
          <circle r={80} fill="#9dc0a4" stroke={BORDE_CALLE} strokeWidth={3} />
        </>
      );
    case "vehiculo":
      return (
        <>
          <rect x={-40} y={-20} width={80} height={40} rx={11} fill={color} stroke="#14201d" strokeWidth={2} />
          <rect x={-8} y={-15} width={26} height={30} rx={5} fill="#d7ebe6" opacity={0.9} />
          <rect x={24} y={-13} width={9} height={26} rx={3} fill="#d7ebe6" opacity={0.75} />
          <circle cx={38} cy={-12} r={3} fill="#ffe58a" />
          <circle cx={38} cy={12} r={3} fill="#ffe58a" />
          <rect x={-36} y={-9} width={20} height={18} rx={4} fill="#ffffff" opacity={0.92} />
          <text
            x={-26}
            y={1}
            textAnchor="middle"
            dominantBaseline="central"
            fontSize={15}
            fontWeight={700}
            fill="#14201d"
            fontFamily="Arial, Helvetica, sans-serif"
          >
            {e.etiqueta ?? ""}
          </text>
        </>
      );
    case "moto":
      return (
        <>
          <rect x={-26} y={-5} width={52} height={10} rx={5} fill={color} stroke="#14201d" strokeWidth={2} />
          <rect x={12} y={-10} width={4} height={20} rx={2} fill="#14201d" />
          <circle cx={-4} cy={0} r={7} fill="#c24d2c" stroke="#14201d" strokeWidth={1.5} />
        </>
      );
    case "persona":
      return (
        <>
          <ellipse cx={0} cy={0} rx={7} ry={13} fill={color} stroke="#14201d" strokeWidth={1.5} />
          <circle cx={0} cy={0} r={7} fill="#f1d2b0" stroke="#14201d" strokeWidth={1.5} />
        </>
      );
    case "flecha":
      return (
        <>
          <line x1={-72} y1={0} x2={56} y2={0} stroke={color} strokeWidth={6} strokeLinecap="round" />
          <polygon points="52,-15 80,0 52,15" fill={color} />
        </>
      );
    case "impacto":
      return (
        <>
          <polygon points={PUNTOS_IMPACTO} fill="#d62828" stroke="#ffffff" strokeWidth={2} />
          <circle r={5} fill="#ffffff" />
        </>
      );
    case "texto":
      return (
        <text
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={22}
          fontWeight={700}
          fill={color}
          stroke="#ffffff"
          strokeWidth={5}
          paintOrder="stroke"
          strokeLinejoin="round"
          fontFamily="Arial, Helvetica, sans-serif"
        >
          {e.texto ?? ""}
        </text>
      );
    case "lapiz":
      return (
        <polyline
          points={(e.puntos ?? []).map(([x, y]) => `${x},${y}`).join(" ")}
          fill="none"
          stroke={color}
          strokeWidth={4}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      );
  }
}

/** Transformación del elemento en la escena. */
export function transformacion(e: Elemento): string {
  return `translate(${e.x} ${e.y}) rotate(${e.rotacion ?? 0}) scale(${e.escala ?? 1})`;
}

export function ElementoSvg({ e }: { e: Elemento }) {
  return (
    <g data-elemento={e.id} transform={transformacion(e)}>
      <Forma e={e} />
    </g>
  );
}

function Leyenda({ escena }: { escena: Escena }) {
  const tipos = new Set<TipoElemento>(escena.elementos.map((e) => e.tipo));
  const filas: { clave: string; texto: string; icono: Elemento | "calzada" }[] = [];
  if (["calle", "cruce", "curva", "rotonda"].some((t) => tipos.has(t as TipoElemento))) filas.push({ clave: "calzada", texto: "Calzada", icono: "calzada" });
  const etiquetas = [...new Set(escena.elementos.filter((e) => e.tipo === "vehiculo").map((e) => e.etiqueta ?? ""))].sort();
  for (const et of etiquetas) {
    const ejemplo = escena.elementos.find((e) => e.tipo === "vehiculo" && (e.etiqueta ?? "") === et);
    if (ejemplo) filas.push({ clave: `v${et}`, texto: et ? `Vehículo ${et}` : "Vehículo", icono: { ...ejemplo, x: 0, y: 0, rotacion: 0, escala: 0.4 } });
  }
  const sencillos: [TipoElemento, string, number][] = [
    ["moto", "Moto", 0.6],
    ["persona", "Persona", 0.85],
    ["flecha", "Sentido de circulación", 0.4],
    ["impacto", "Punto de impacto", 0.6],
  ];
  for (const [tipo, texto, escala] of sencillos) {
    const ejemplo = escena.elementos.find((e) => e.tipo === tipo);
    if (ejemplo) filas.push({ clave: tipo, texto, icono: { ...ejemplo, x: 0, y: 0, rotacion: 0, escala } });
  }
  if (filas.length === 0) return null;
  const alto = 34 + filas.length * 26;
  return (
    <g transform={`translate(20 ${escena.alto - alto - 20})`} data-leyenda="true" pointerEvents="none">
      <rect width={250} height={alto} rx={8} fill="#ffffff" fillOpacity={0.94} stroke="#8b908a" strokeWidth={1.5} />
      <text x={14} y={22} fontSize={14} fontWeight={700} fill="#1d2321" fontFamily="Arial, Helvetica, sans-serif">
        Referencias
      </text>
      {filas.map((f, i) => (
        <g key={f.clave} transform={`translate(0 ${42 + i * 26})`}>
          <g transform="translate(36 0)">
            {f.icono === "calzada" ? (
              <rect x={-18} y={-8} width={36} height={16} fill={ASFALTO} stroke={BORDE_CALLE} strokeWidth={1.5} />
            ) : (
              <g transform={`scale(${f.icono.escala ?? 1})`}>
                <Forma e={f.icono} />
              </g>
            )}
          </g>
          <text x={68} y={0} dominantBaseline="central" fontSize={14} fill="#1d2321" fontFamily="Arial, Helvetica, sans-serif">
            {f.texto}
          </text>
        </g>
      ))}
    </g>
  );
}

function Norte({ escena }: { escena: Escena }) {
  return (
    <g transform={`translate(${escena.ancho - 70} 70)`} data-norte="true" pointerEvents="none">
      <circle r={42} fill="#ffffff" fillOpacity={0.94} stroke="#8b908a" strokeWidth={1.5} />
      <polygon points="0,-14 10,24 0,15 -10,24" fill="#1d2321" />
      <text y={-26} textAnchor="middle" dominantBaseline="central" fontSize={17} fontWeight={700} fill="#1d2321" fontFamily="Arial, Helvetica, sans-serif">
        N
      </text>
    </g>
  );
}

/** Fondo, cuadrícula, elementos, referencias y norte. Va dentro de un `<svg viewBox="0 0 ancho alto">`. */
export function EscenaSvg({ escena }: { escena: Escena }) {
  return (
    <>
      <defs>
        <pattern id="croquis-cuadricula-fina" width={20} height={20} patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e6e9e5" strokeWidth={1} />
        </pattern>
        <pattern id="croquis-cuadricula-gruesa" width={100} height={100} patternUnits="userSpaceOnUse">
          <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#d2d8d3" strokeWidth={1.5} />
        </pattern>
      </defs>
      <rect width={escena.ancho} height={escena.alto} fill="#ffffff" />
      {escena.cuadricula ? (
        <>
          <rect width={escena.ancho} height={escena.alto} fill="url(#croquis-cuadricula-fina)" />
          <rect width={escena.ancho} height={escena.alto} fill="url(#croquis-cuadricula-gruesa)" />
        </>
      ) : null}
      <g data-capa="elementos">
        {escena.elementos.map((e) => (
          <ElementoSvg key={e.id} e={e} />
        ))}
      </g>
      {escena.leyenda ? <Leyenda escena={escena} /> : null}
      {escena.norte ? <Norte escena={escena} /> : null}
      <text
        x={escena.ancho - 14}
        y={escena.alto - 12}
        textAnchor="end"
        fontSize={13}
        fill="#6d726c"
        fontFamily="Arial, Helvetica, sans-serif"
        pointerEvents="none"
      >
        Croquis ilustrativo, sin escala
      </text>
    </>
  );
}

/** Icono de la paleta: el elemento a su tamaño aproximado dentro de un cuadrito. */
export function IconoElemento({ e, lado = 56 }: { e: Elemento; lado?: number }) {
  const mitad = e.tipo === "calle" ? 210 : e.tipo === "cruce" ? 210 : e.tipo === "curva" ? 190 : e.tipo === "rotonda" ? 180 : e.tipo === "flecha" ? 95 : e.tipo === "impacto" ? 30 : e.tipo === "persona" ? 18 : e.tipo === "moto" ? 32 : e.tipo === "texto" ? 40 : 46;
  return (
    <svg width={lado} height={lado} viewBox={`${-mitad} ${-mitad} ${mitad * 2} ${mitad * 2}`} aria-hidden="true" focusable="false">
      <Forma e={{ ...e, texto: e.tipo === "texto" ? "Aa" : e.texto }} />
    </svg>
  );
}
