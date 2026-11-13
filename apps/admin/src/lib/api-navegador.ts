// El lado del navegador de las acciones del §7.
//
// Habla solo con los Route Handlers de esta misma app, nunca con el backend:
// la URL del backend se queda en el servidor y el navegador no tiene que saber
// que existe.

import type {
  AltaProducto,
  BorradorKits,
  DecisionRevision,
  ErrorApi,
  MarcarNoDisponible,
  AsignacionCaso,
  CasoDetalleAdmin,
  DestinoDeLote,
  PedidoAdmin,
  PrioridadCaso,
  RespuestaLote,
  RespuestaReconciliacion,
  VistaPreviaPedido,
  ProductoDadoDeAlta,
  SinCoincidencia,
  SolicitudAvanceAdmin,
  ValidarLinea,
} from "@tukit/contrato";
import { conEspera } from "@tukit/contrato";

export class FalloApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "FalloApi";
  }
}

async function enviar<T>(ruta: string, cuerpo: unknown): Promise<T> {
  const respuesta = await fetch(ruta, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpo),
  });
  const texto = await respuesta.text();
  const leido: unknown = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    // Un 429 llega con la espera en el mensaje aunque el cuerpo no la traiga.
    const error = conEspera(
      respuesta.status,
      (leido ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
    // El mensaje que se muestra es el del backend, no uno inventado aqui: es
    // el unico que sabe por que rechazo la accion (motivo vacio, precio con
    // decimales, trabajo ya publicado).
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salio mal al guardar el cambio.",
      error,
    );
  }
  return leido as T;
}

const id = encodeURIComponent;

/** AD-02. Sin `sku` se lee como "confirmo el producto que el sistema eligio". */
export function validarLinea(
  trabajoId: string,
  itemId: string,
  cuerpo: ValidarLinea,
): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/lineas/${id(itemId)}/validar`, cuerpo);
}

/** AD-04. Fija el producto de UN kit (por-nivel): escribe LINEA y recalcula su
 *  subtotal. A diferencia de `validarLinea` (item, los tres kits), esto cambia
 *  el producto de un solo perfil, que es lo que hace que el concepto suba de
 *  economico a premium entre kits y que el personaje del Fan llegue al kit. */
export function fijarProductoLinea(
  trabajoId: string,
  perfil: string,
  itemId: string,
  sku: string,
): Promise<void> {
  return enviar(
    `/api/trabajos/${id(trabajoId)}/kits/${id(perfil)}/lineas/${id(itemId)}/producto`,
    { sku },
  );
}

/** AD-02. El motivo es obligatorio: una marca sin motivo no se puede revisar despues. */
export function marcarSinCoincidencia(
  trabajoId: string,
  itemId: string,
  cuerpo: SinCoincidencia,
): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/lineas/${id(itemId)}/sin-coincidencia`, cuerpo);
}

/** AD-07. Alta manual con precio e imagen, para utiles y libros. */
export function altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
  return enviar<ProductoDadoDeAlta>("/api/productos", cuerpo);
}

/** AD-05. Apaga la oferta en catalogo, o sea para todos los trabajos. */
export function marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
  return enviar(`/api/productos/${id(sku)}/no-disponible`, cuerpo);
}

/** AD-06. Aprobar publica y avisa al acudiente; devolver reabre en silencio. */
export function decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/revision`, cuerpo);
}

/** Aprueba la lista de un preview y deja sus tres kits como los canónicos del
 *  grado. No avisa a nadie: un preview no tiene acudiente. */
export function guardarComoCanonico(trabajoId: string, cuerpo: { nota?: string }): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/canonico`, cuerpo);
}

/** Abre (o retoma) la versión siguiente de los kits canónicos de un grado:
 *  una copia editable del canónico vigente. Devuelve el trabajo a corregir. */
export function abrirBorradorKits(canonicoId: string): Promise<BorradorKits> {
  return enviar(`/api/trabajos/${id(canonicoId)}/borrador`, {});
}

/** Borra un trabajo desechable (preview, encolado, fallido). Un `publicado`
 *  esta protegido: el backend responde 409 `trabajo_publicado_protegido`. */
export function eliminarTrabajo(trabajoId: string): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/eliminar`, {});
}

/** Logistica: mueve el pedido un paso. El Route Handler pone el token de la
 *  cookie; un 409/422 llega como `FalloApi` con el `campo` en `detalle`. */
export function avanzarPedido(
  pedidoId: string,
  cuerpo: SolicitudAvanceAdmin,
): Promise<PedidoAdmin> {
  return enviar(`/api/logistica/${id(pedidoId)}/avanzar`, cuerpo);
}

/** Tickets: responde al acudiente (queda en la historia y le llega un aviso). */
export function responderTicket(casoId: string, texto: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/responder`, { texto });
}

/** Tickets: mueve el ticket de estado; 409 si la transicion no procede. */
export function cambiarEstadoTicket(casoId: string, destino: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/estado`, { destino });
}

/** Tickets: vincula el ticket a un pedido. */
export function vincularPedidoTicket(casoId: string, pedidoId: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/pedido`, { pedido_id: pedidoId });
}

/** Logistica: pregunta a Wompi por el pago de un pedido atascado (aplica el resultado). */
export function reconciliarPago(pedidoId: string): Promise<RespuestaReconciliacion> {
  return enviar(`/api/logistica/${id(pedidoId)}/reconciliar`, {});
}

/** Logistica: lo que verá el acudiente si el pedido pasa a `destino` (no escribe nada). */
export async function vistaPrevia(pedidoId: string, destino: string): Promise<VistaPreviaPedido> {
  const respuesta = await fetch(`/api/logistica/${id(pedidoId)}/vista-previa?destino=${encodeURIComponent(destino)}`);
  const texto = await respuesta.text();
  const leido: unknown = texto ? JSON.parse(texto) : null;
  if (!respuesta.ok) {
    const error = (leido ?? {}) as ErrorApi;
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "No pudimos cargar la vista previa.",
      error as unknown as Record<string, unknown>,
    );
  }
  return leido as VistaPreviaPedido;
}

/** Logistica: mueve varios pedidos al mismo destino simple; el resultado es por pedido. */
export function avanzarEnLote(cuerpo: { pedido_ids: string[]; destino: DestinoDeLote }): Promise<RespuestaLote> {
  return enviar("/api/logistica/lote", cuerpo);
}

/** Tickets: asignarme o soltar. */
export function asignarTicket(casoId: string, asignar: AsignacionCaso): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/asignar`, { asignar });
}

/** Tickets: cambia la prioridad. */
export function priorizarTicket(casoId: string, prioridad: PrioridadCaso): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/prioridad`, { prioridad });
}

/** Tickets: nota interna (solo el equipo la ve). */
export function agregarNota(casoId: string, texto: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/nota`, { texto });
}
