import {
  ETIQUETA_FASE_SEGUIMIENTO,
  ETIQUETA_TIPO_INCIDENCIA,
  FASES_SEGUIMIENTO,
  type DesvioPedido,
  type LineaDeTiempoPedido,
  type PasoPedido,
  type SituacionPaso,
  type TipoIncidencia,
} from "@tukit/contrato/comercio";

export interface FaseVista {
  paso: PasoPedido;
  etiqueta: string;
  situacion: SituacionPaso;
  fecha: string | null;
  repartidor: string | null;
}

export interface SeguimientoVista {
  fases: FaseVista[];
  hechas: number;
  actual: FaseVista | null;
  esperaPago: boolean;
  entregado: boolean;
  desvio: { tipo: "incidencia" | "cancelado"; mensaje: string; fecha: string | null } | null;
  entregaEstimada: string | null;
  resumen: string;
}

const MENSAJE_FASE: Record<PasoPedido, string> = {
  creado: "Esperando tu pago.",
  pagado: "Recibimos tu pago. En breve armamos tu kit.",
  en_preparacion: "Estamos armando tu kit.",
  despachado: "Tu kit ya salió de la bodega.",
  en_reparto: "Tu kit va en camino a tu dirección.",
  entregado: "Tu kit llegó. ¡Que lo disfruten!",
};

function mensajeDesvio(d: DesvioPedido): string {
  if (d.tipo === "cancelado") return "Este pedido fue cancelado.";
  const motivo =
    (d.tipo_incidencia && ETIQUETA_TIPO_INCIDENCIA[d.tipo_incidencia as TipoIncidencia]) ||
    "Otro inconveniente";
  return `Tuvimos un inconveniente con la entrega (${motivo.toLowerCase()}). Te contactaremos para resolverlo.`;
}

export function seguimientoDePedido(linea: LineaDeTiempoPedido): SeguimientoVista {
  const porPaso = new Map(linea.pasos.map((p) => [p.paso, p]));
  const entregado = porPaso.get("entregado")?.estado === "actual";
  const fases: FaseVista[] = FASES_SEGUIMIENTO.map((paso) => {
    const p = porPaso.get(paso);
    return {
      paso,
      etiqueta: ETIQUETA_FASE_SEGUIMIENTO[paso],
      situacion: paso === "entregado" && entregado ? "hecho" : (p?.estado ?? "futuro"),
      fecha: p?.fecha ?? null,
      repartidor: paso === "despachado" ? (p?.repartidor_nombre ?? null) : null,
    };
  });

  const hechas = fases.filter((f) => f.situacion === "hecho").length;
  const actual = fases.find((f) => f.situacion === "actual") ?? null;
  const esperaPago = linea.pago_pendiente !== null || porPaso.get("creado")?.estado === "actual";
  const desvio = linea.especial
    ? { tipo: linea.especial.tipo, mensaje: mensajeDesvio(linea.especial), fecha: linea.especial.fecha }
    : null;

  let resumen: string;
  if (desvio) resumen = desvio.mensaje;
  else if (esperaPago) resumen = MENSAJE_FASE.creado;
  else if (actual) resumen = MENSAJE_FASE[actual.paso];
  else resumen = entregado ? MENSAJE_FASE.entregado : "";

  return {
    fases,
    hechas,
    actual,
    esperaPago,
    entregado,
    desvio,
    entregaEstimada: entregado || desvio?.tipo === "cancelado" ? null : linea.entrega_estimada,
    resumen,
  };
}
