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
    const error = conEspera(
      respuesta.status,
      (leido ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
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

export function validarLinea(
  trabajoId: string,
  itemId: string,
  cuerpo: ValidarLinea,
): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/lineas/${id(itemId)}/validar`, cuerpo);
}

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

export function marcarSinCoincidencia(
  trabajoId: string,
  itemId: string,
  cuerpo: SinCoincidencia,
): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/lineas/${id(itemId)}/sin-coincidencia`, cuerpo);
}

export function altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
  return enviar<ProductoDadoDeAlta>("/api/productos", cuerpo);
}

export function marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
  return enviar(`/api/productos/${id(sku)}/no-disponible`, cuerpo);
}

export function decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/revision`, cuerpo);
}

export function guardarComoCanonico(trabajoId: string, cuerpo: { nota?: string }): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/canonico`, cuerpo);
}

export function abrirBorradorKits(canonicoId: string): Promise<BorradorKits> {
  return enviar(`/api/trabajos/${id(canonicoId)}/borrador`, {});
}

export function eliminarTrabajo(trabajoId: string): Promise<void> {
  return enviar(`/api/trabajos/${id(trabajoId)}/eliminar`, {});
}

export function avanzarPedido(
  pedidoId: string,
  cuerpo: SolicitudAvanceAdmin,
): Promise<PedidoAdmin> {
  return enviar(`/api/logistica/${id(pedidoId)}/avanzar`, cuerpo);
}

export function responderTicket(casoId: string, texto: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/responder`, { texto });
}

export function cambiarEstadoTicket(casoId: string, destino: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/estado`, { destino });
}

export function vincularPedidoTicket(casoId: string, pedidoId: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/pedido`, { pedido_id: pedidoId });
}

export function reconciliarPago(pedidoId: string): Promise<RespuestaReconciliacion> {
  return enviar(`/api/logistica/${id(pedidoId)}/reconciliar`, {});
}

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

export function avanzarEnLote(cuerpo: { pedido_ids: string[]; destino: DestinoDeLote }): Promise<RespuestaLote> {
  return enviar("/api/logistica/lote", cuerpo);
}

export function asignarTicket(casoId: string, asignar: AsignacionCaso): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/asignar`, { asignar });
}

export function priorizarTicket(casoId: string, prioridad: PrioridadCaso): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/prioridad`, { prioridad });
}

export function agregarNota(casoId: string, texto: string): Promise<CasoDetalleAdmin> {
  return enviar(`/api/tickets/${id(casoId)}/nota`, { texto });
}
