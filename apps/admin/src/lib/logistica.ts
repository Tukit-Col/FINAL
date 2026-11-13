// La logica pura de la pantalla de logistica: filtros, orden, acciones por
// estado y el formato de la fecha estimada.
//
// Vive aparte de las paginas para probarse con `node --test` (sin runner de
// componentes) y por eso SOLO importa tipos del contrato: el runtime de Node no
// resuelve los imports sin extension de `@tukit/contrato`.

import type { AlertaPedido, EstadoPedido, Pedido } from "@tukit/contrato";

// Orden operativo: primero lo que hay que atender (incidencias), luego lo que
// hay que mover (en curso) y al final lo cerrado. Es un `Record` exhaustivo: un
// estado nuevo en el contrato no compila hasta tener su lugar aqui, y sus
// llaves son ademas la lista de estados validos para el filtro.
export const PRIORIDAD_ESTADO: Record<EstadoPedido, number> = {
  incidencia: 0,
  pagado: 1,
  en_preparacion: 2,
  despachado: 3,
  en_reparto: 4,
  pendiente_pago: 5,
  entregado: 6,
  cancelado: 7,
};

export function ordenarPorPrioridad(pedidos: readonly Pedido[]): Pedido[] {
  return [...pedidos].sort((a, b) => PRIORIDAD_ESTADO[a.estado] - PRIORIDAD_ESTADO[b.estado]);
}

export interface FiltrosLogistica {
  // Prefijo del id del pedido: sirve el codigo corto de 8 que ve el papa.
  q: string;
  estado: EstadoPedido | "";
  colegio: string;
  // Dias de Bogota, `YYYY-MM-DD`, sobre `creado_en`. Vacio = sin limite.
  desde: string;
  hasta: string;
  // Alerta accionable de comercio (`?alerta=`): pagado sin avanzar, pago atascado, incidencia.
  alerta: AlertaPedido | "";
  // Tablero kanban o tabla (`?vista=`). No filtra: solo cambia como se pinta.
  vista: VistaLogistica;
}

type ParametrosBusqueda = Record<string, string | string[] | undefined>;

const DIA = /^\d{4}-\d{2}-\d{2}$/;

function primero(valor: string | string[] | undefined): string {
  return (Array.isArray(valor) ? valor[0] : valor)?.trim() ?? "";
}

// Espejo de `AlertaPedido` (el runtime del contrato no se importa aqui).
const ALERTAS: readonly AlertaPedido[] = ["pagado_sin_avanzar", "pago_atascado", "incidencia_abierta"];

function esAlerta(valor: string): valor is AlertaPedido {
  return (ALERTAS as readonly string[]).includes(valor);
}

function esEstado(valor: string): valor is EstadoPedido {
  return Object.hasOwn(PRIORIDAD_ESTADO, valor);
}

/** Los filtros de la URL, saneados: un estado o una fecha que no son validos
 *  se ignoran en vez de dejar la tabla vacia sin explicacion. */
export function leerFiltros(parametros: ParametrosBusqueda): FiltrosLogistica {
  const estado = primero(parametros.estado);
  const desde = primero(parametros.desde);
  const hasta = primero(parametros.hasta);
  const alerta = primero(parametros.alerta);
  const vista = primero(parametros.vista);
  return {
    q: primero(parametros.q),
    estado: esEstado(estado) ? estado : "",
    colegio: primero(parametros.colegio),
    desde: DIA.test(desde) ? desde : "",
    hasta: DIA.test(hasta) ? hasta : "",
    alerta: esAlerta(alerta) ? alerta : "",
    vista: esVista(vista) ? vista : VISTA_POR_DEFECTO,
  };
}

/** Si hay algun filtro puesto. La vista no cuenta: no esconde pedidos. */
export function hayFiltros(filtros: FiltrosLogistica): boolean {
  return [filtros.q, filtros.estado, filtros.colegio, filtros.desde, filtros.hasta, filtros.alerta].some(
    (v) => v !== "",
  );
}

/** Una clave estable de los filtros, para remontar el formulario al cambiarlos. */
export function claveFiltros(filtros: FiltrosLogistica): string {
  return [filtros.q, filtros.estado, filtros.colegio, filtros.desde, filtros.hasta, filtros.alerta].join("|");
}

// `en-CA` formatea como `YYYY-MM-DD`, que se compara como texto. Zona fija y no
// la del proceso: un pedido de las 9 p. m. de Bogota es de ese dia, aunque en
// UTC ya sea el siguiente.
const DIA_BOGOTA = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Bogota",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

export function diaBogota(iso: string): string {
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime()) ? "" : DIA_BOGOTA.format(fecha);
}

/** Valor de `?colegio=` para los pedidos que no traen colegio. */
export const COLEGIO_NINGUNO = "sin-colegio";

export function filtrarPedidos(pedidos: readonly Pedido[], filtros: FiltrosLogistica): Pedido[] {
  const q = filtros.q.toLowerCase();
  return pedidos.filter((pedido) => {
    if (q && !pedido.pedido_id.toLowerCase().startsWith(q)) return false;
    if (filtros.estado && pedido.estado !== filtros.estado) return false;
    if (filtros.colegio === COLEGIO_NINGUNO) {
      if (pedido.colegios.length > 0) return false;
    } else if (filtros.colegio && !pedido.colegios.includes(filtros.colegio)) return false;
    if (filtros.alerta && !(pedido.alertas ?? []).includes(filtros.alerta)) return false;
    if (filtros.desde || filtros.hasta) {
      const dia = diaBogota(pedido.creado_en);
      if (filtros.desde && dia < filtros.desde) return false;
      if (filtros.hasta && dia > filtros.hasta) return false;
    }
    return true;
  });
}

export function colegiosDisponibles(pedidos: readonly Pedido[]): string[] {
  return [...new Set(pedidos.flatMap((p) => p.colegios))].sort((a, b) => a.localeCompare(b, "es"));
}

/** El dia elegido en el formulario como medianoche de Bogota CON zona: comercio
 *  rechaza una fecha sin zona (se correria al guardarla). Bogota no tiene horario
 *  de verano, asi que `-05:00` es fijo. */
export function fechaEstimadaIso(dia: string): string | null {
  return DIA.test(dia) ? `${dia}T00:00:00-05:00` : null;
}

// Que pide cada accion antes de enviarse. `simple` va directo; las demas abren
// su formulario o su confirmacion.
export type FormaAccion = "simple" | "despachar" | "incidencia" | "cancelar";

export interface AccionLogistica {
  destino: EstadoPedido;
  etiqueta: string;
  forma: FormaAccion;
}

const PREPARAR: AccionLogistica = { destino: "en_preparacion", etiqueta: "Pasar a preparación", forma: "simple" };
const INCIDENCIA: AccionLogistica = { destino: "incidencia", etiqueta: "Reportar incidencia", forma: "incidencia" };

// Espejo de `AVANCES_DE_LOGISTICA` en `comercio/dominio/despacho.py`: un boton
// por transicion que el back-office puede hacer. Si se desalinean, comercio
// responde 409 y el boton muestra su mensaje; no se abre nada por aqui.
const ACCIONES: Partial<Record<EstadoPedido, readonly AccionLogistica[]>> = {
  pagado: [PREPARAR, INCIDENCIA],
  en_preparacion: [{ destino: "despachado", etiqueta: "Despachar", forma: "despachar" }, INCIDENCIA],
  despachado: [{ destino: "en_reparto", etiqueta: "Salió a reparto", forma: "simple" }, INCIDENCIA],
  en_reparto: [{ destino: "entregado", etiqueta: "Marcar entregado", forma: "simple" }, INCIDENCIA],
  incidencia: [
    { destino: "en_preparacion", etiqueta: "Reprogramar", forma: "simple" },
    { destino: "cancelado", etiqueta: "Cancelar pedido", forma: "cancelar" },
  ],
};

export function accionesDisponibles(estado: EstadoPedido): readonly AccionLogistica[] {
  return ACCIONES[estado] ?? [];
}

// Por que la pantalla no puede mostrar logistica. Cada motivo tiene su texto
// en `AvisoAcceso`.
export type MotivoAcceso = "sin_sesion" | "sesion_expirada" | "sin_rol" | "servicio_caido" | "limite";

/** El motivo a partir del HTTP con que fallo la lectura. Un 429 es el limite de
 *  tasa (ADR 0047): la sesion sigue viva y los servicios arriba, solo hay que
 *  esperar. */
export function motivoDeFallo(estado: number): MotivoAcceso {
  if (estado === 401) return "sesion_expirada";
  if (estado === 403) return "sin_rol";
  if (estado === 429) return "limite";
  return "servicio_caido";
}

/** Si una lectura cayo por la sesion, el rol o el limite, el aviso que va en
 *  su lugar; si no, `null` y la pagina decide (un 404 es `notFound`, una caida
 *  sube). Desde que el gateway exige sesion en /v1/admin, un token vencido
 *  rompia la pagina con un 500 en vez de decir "vuelve a ingresar". */
export function motivoDeAcceso(causa: unknown): MotivoAcceso | null {
  const estado = (causa as { estado?: unknown } | null | undefined)?.estado;
  if (estado === 401 || estado === 403 || estado === 429) return motivoDeFallo(estado);
  return null;
}

// ------------------------------------------------ Fase 4: motivo, fallos, previa, lote

export interface MotivoSinAcciones {
  titulo: string;
  detalle: string;
  /** La unica salida que el admin tiene para este estado. */
  accion?: "reconciliar";
}

/** Por que un pedido no muestra botones de logistica, o `null` si los tiene.
 *  `pendiente_pago` solo lo mueve el pago: la salida legitima es preguntarle a
 *  Wompi (no hay "marcar pagado a mano"). */
export function motivoSinAcciones(estado: EstadoPedido): MotivoSinAcciones | null {
  if (accionesDisponibles(estado).length > 0) return null;
  if (estado === "pendiente_pago") {
    return {
      titulo: "Esperando el pago",
      detalle:
        "El pedido se mueve cuando Wompi confirma el pago. Si el acudiente ya pagó y no avanza, pregúntale a Wompi: " +
        "si aprobó, el pedido pasa a Pagado. Si nadie paga en 24 h, el pedido vence solo.",
      accion: "reconciliar",
    };
  }
  if (estado === "entregado") {
    return { titulo: "Entregado: sin pasos pendientes", detalle: "El pedido llegó a su destino y ya no se mueve." };
  }
  return {
    titulo: "Cancelado",
    detalle: "El pedido está cancelado y su pago quedó marcado para reembolso si estaba aprobado.",
  };
}

export type ClaseDeFallo = "sesion" | "rol" | "conflicto" | "pasarela" | "otro";

/** La clase de un fallo de la API según su HTTP: decide el estilo y la salida del banner. */
export function claseDeFallo(estado: number): ClaseDeFallo {
  if (estado === 401) return "sesion";
  if (estado === 403) return "rol";
  if (estado === 409) return "conflicto";
  if (estado === 502) return "pasarela";
  return "otro";
}

/** Un 404/405 de una ruta nueva: el servicio todavía no se reinició con ella. */
export function rutaSinActivar(estado: number): boolean {
  return estado === 404 || estado === 405;
}

export type ResultadoReconciliacion = "pagado" | "en_curso" | "libre";

export function etiquetaResultadoReconciliacion(r: ResultadoReconciliacion): string {
  switch (r) {
    case "pagado":
      return "El pago estaba aprobado: el pedido pasó a Pagado";
    case "en_curso":
      return "El pago sigue en curso en Wompi";
    case "libre":
      return "No hay un pago aprobado: el pedido sigue sin pagar";
  }
}

const RANGO_FORMA: Record<FormaAccion, number> = { simple: 0, despachar: 0, incidencia: 1, cancelar: 2 };

/** Los destinos del selector: primero el avance natural, la incidencia después y cancelar al final. */
export function destinosParaSelector(estado: EstadoPedido): AccionLogistica[] {
  return [...accionesDisponibles(estado)].sort((a, b) => RANGO_FORMA[a.forma] - RANGO_FORMA[b.forma]);
}

const DESTINO_DE_LOTE: Partial<Record<EstadoPedido, "en_preparacion" | "en_reparto" | "entregado">> = {
  pagado: "en_preparacion",
  despachado: "en_reparto",
  en_reparto: "entregado",
};

/** El único destino simple que comparten todos los pedidos, o `null` si hay
 *  mezcla, no hay pedidos o el paso pide datos (despachar, incidencia, cancelar). */
export function destinoComunDeLote(pedidos: readonly Pick<Pedido, "estado">[]): EstadoPedido | null {
  if (pedidos.length === 0) return null;
  const destinos = new Set(pedidos.map((p) => DESTINO_DE_LOTE[p.estado] ?? null));
  if (destinos.size !== 1) return null;
  return [...destinos][0] ?? null;
}

/** "18 avanzados, 2 con problema" (pluraliza el primer término). */
export function resumenDeLote(r: {
  avanzados: readonly unknown[];
  fallidos: readonly unknown[];
}): string {
  const n = r.avanzados.length;
  return `${n} ${n === 1 ? "avanzado" : "avanzados"}, ${r.fallidos.length} con problema`;
}

/** Los pasos que ve el acudiente (`LineaDeTiempoPedido.pasos[].paso`), en su idioma. */
export const ETIQUETA_PASO_ACUDIENTE: Record<string, string> = {
  creado: "Pedido creado",
  pagado: "Pago confirmado",
  en_preparacion: "En preparación",
  despachado: "Despachado",
  en_reparto: "En reparto",
  entregado: "Entregado",
};

/** El aviso que recibirá el acudiente, en una frase. `null` = no se le avisa. */
export function textoAviso(aviso: string | null): string {
  switch (aviso) {
    case "pedido_en_preparacion":
      return "Le avisamos que estamos preparando su kit.";
    case "pedido_cancelado":
      return "Le avisamos que se canceló el pedido y si hay reembolso.";
    case "pedido_despachado":
      return "Le avisamos que su pedido salió despachado.";
    case "pedido_en_reparto":
      return "Le avisamos que su pedido va en reparto.";
    case "pedido_entregado":
      return "Le avisamos que su pedido fue entregado.";
    case "incidencia":
      return "Le avisamos que hubo un inconveniente con la entrega.";
    default:
      return "No se le envía aviso: el contacto lo haces tú.";
  }
}

/** El enlace de un chip de alerta: conserva los demás filtros y cambia solo `alerta`. */
export function hrefConAlerta(filtros: FiltrosLogistica, alerta: AlertaPedido | ""): string {
  const parametros = new URLSearchParams();
  for (const [clave, valor] of Object.entries({ ...filtros, alerta })) {
    // La vista por defecto no se escribe: `/logistica` pelado sigue siendo el inicio.
    if (clave === "vista" && valor === VISTA_POR_DEFECTO) continue;
    if (valor) parametros.set(clave, valor);
  }
  const cola = parametros.toString();
  return cola ? `/logistica?${cola}` : "/logistica";
}

/** Los primeros 8 caracteres del id: el código corto que ve el acudiente. */
export function codigoCorto(pedidoId: string): string {
  return pedidoId.slice(0, 8);
}

// ------------------------------------------------ Tablero kanban por etapa

/** Las dos vistas de `/logistica`. El tablero es la de entrada: la pregunta
 *  diaria del operador es "que hay en cada etapa y que se atasco", y eso se
 *  lee de un vistazo en columnas. La tabla queda para buscar, comparar y el
 *  avance en lote (`?vista=tabla`). */
export type VistaLogistica = "tablero" | "tabla";

export const VISTA_POR_DEFECTO: VistaLogistica = "tablero";

function esVista(valor: string): valor is VistaLogistica {
  return valor === "tablero" || valor === "tabla";
}

/** El flujo feliz, en el orden en que avanza un pedido (columnas de izquierda
 *  a derecha). Es el mismo orden de la matriz `ACCIONES`. */
export const COLUMNAS_FLUJO: readonly EstadoPedido[] = [
  "pendiente_pago",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
];

/** Lo que sale del flujo: la incidencia (hay que atenderla) y lo cancelado.
 *  Van en un carril aparte, visibles, no escondidos al final. */
export const CARRIL_APARTE: readonly EstadoPedido[] = ["incidencia", "cancelado"];

/** Las columnas cerradas muestran solo los ultimos N para no saturar; el
 *  resto se ve en la tabla con su filtro. */
export const ESTADOS_LIMITADOS: readonly EstadoPedido[] = ["entregado", "cancelado"];
export const LIMITE_CERRADOS = 5;
/** Las etapas abiertas tambien se recortan: con miles de pedidos una columna de
 *  1000 tarjetas no se lee. Las alertas van primero, asi que no se esconden. */
export const LIMITE_ABIERTAS = 8;

export interface ColumnaTablero {
  estado: EstadoPedido;
  /** Cuantos pedidos (ya filtrados) hay en la etapa, aunque no se muestren todos. */
  total: number;
  pedidos: Pedido[];
  /** Los que no caben por el limite de las columnas cerradas. */
  ocultos: number;
}

/** Desde cuando el pedido esta en su etapa, lo mejor que el tablero sabe: el
 *  tablero de comercio no trae la fecha de llegada a cada estado, asi que la
 *  entrega usa `entregado_en` y el resto la creacion del pedido. */
export function fechaDeEtapa(pedido: Pedido): string {
  if (pedido.estado === "entregado" && pedido.envio?.entregado_en) return pedido.envio.entregado_en;
  return pedido.creado_en;
}

function instante(iso: string): number {
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/** Los pedidos por etapa, en el orden de `estados`. En las etapas abiertas va
 *  primero lo que tiene alerta y luego lo mas viejo (lo que lleva mas esperando);
 *  en las cerradas lo mas reciente, recortado a `limite`. */
export function agruparPorEtapa(
  pedidos: readonly Pedido[],
  estados: readonly EstadoPedido[],
  limite: number = LIMITE_CERRADOS,
  limiteAbiertas: number = LIMITE_ABIERTAS,
): ColumnaTablero[] {
  return estados.map((estado) => {
    const deLaEtapa = pedidos.filter((p) => p.estado === estado);
    const cerrada = ESTADOS_LIMITADOS.includes(estado);
    const ordenados = [...deLaEtapa].sort((a, b) => {
      if (cerrada) return instante(fechaDeEtapa(b)) - instante(fechaDeEtapa(a));
      const alerta = Number((b.alertas ?? []).length > 0) - Number((a.alertas ?? []).length > 0);
      return alerta !== 0 ? alerta : instante(fechaDeEtapa(a)) - instante(fechaDeEtapa(b));
    });
    const visibles = ordenados.slice(0, Math.max(0, cerrada ? limite : limiteAbiertas));
    return { estado, total: deLaEtapa.length, pedidos: visibles, ocultos: deLaEtapa.length - visibles.length };
  });
}

/** Unidades del pedido (suma de cantidades de sus lineas). */
export function articulosDePedido(pedido: Pick<Pedido, "lineas">): number {
  return pedido.lineas.reduce((suma, linea) => suma + linea.cantidad, 0);
}

export interface AccionDeTarjeta {
  accion: AccionLogistica;
  /** `true`: se envia desde la tarjeta. `false`: pide datos (repartidor) y
   *  abre el detalle, donde vive su formulario. */
  directa: boolean;
}

/** El paso siguiente que ofrece una tarjeta: SOLO el avance natural de la
 *  matriz (su primera accion). Incidencia y cancelar quedan en el detalle,
 *  donde piden tipo, nota o confirmacion. `null` si el estado no se mueve
 *  desde logistica (pendiente de pago, entregado, cancelado). */
export function accionDeTarjeta(estado: EstadoPedido): AccionDeTarjeta | null {
  // Una incidencia se atiende leyendo su nota: reprogramar o cancelar desde la
  // tarjeta seria decidir a ciegas. Va al detalle.
  if (estado === "incidencia") return null;
  const accion = accionesDisponibles(estado).find((a) => a.forma === "simple" || a.forma === "despachar");
  if (!accion) return null;
  return { accion, directa: accion.forma === "simple" };
}

/** El enlace del selector Tablero | Tabla: conserva los filtros y cambia la vista.
 *  La vista por defecto no se escribe en la URL. */
export function hrefConVista(filtros: FiltrosLogistica, vista: VistaLogistica): string {
  return hrefConAlerta({ ...filtros, vista }, filtros.alerta);
}

/** El enlace "ver todos" de una columna recortada: la tabla filtrada por esa etapa. */
export function hrefEtapaEnTabla(filtros: FiltrosLogistica, estado: EstadoPedido): string {
  return hrefConAlerta({ ...filtros, estado, vista: "tabla" }, filtros.alerta);
}

/** El enlace de un grupo del mapa a la tabla filtrada por su colegio (o por los
 *  pedidos sin colegio si `colegioId` es `null`). */
export function hrefColegioEnTabla(colegioId: string | null): string {
  return `/logistica?${new URLSearchParams({ vista: "tabla", colegio: colegioId ?? COLEGIO_NINGUNO })}`;
}
