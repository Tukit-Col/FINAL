// Superficie de LECTURA de `comercio`. ASUMIDA, no transcrita.
//
// `arquitectura/CONTRATO_API.md` v1.0 no publica todavia la superficie de
// `comercio` (pedidos, inventario, reservas, pagos, entrega — §1 de
// ARQUITECTURA.md). El §9 del contrato solo fija el borde del pago (Wompi:
// id y estado). Todo este fichero es una inferencia a partir de la topologia
// canonica: `comercio` es "todo lo que toca dinero" y guarda el pedido, su
// envio con copia congelada de la direccion (ADR 0015) y el precio congelado
// en la reserva (ADR 0012, R-PRECIO).
//
// Vive en su propio fichero, aparte de `contrato.ts`, para que la diferencia
// entre "lo que el contrato dice" y "lo que supusimos" se vea de un vistazo el
// dia que el backend publique la 1.x. Las pantallas de logistica del back-office
// consumen SOLO esto; cuando `comercio` conteste, se cambia una variable de
// entorno y no una pantalla.

import type { Dinero } from "./contrato";

export const VERSION_COMERCIO_ASUMIDA = "1.x-asumida";

// El ciclo de vida de un pedido, del pago a la puerta. Nombres alineados a lo
// que la saga de pago del §Procesos de ARQUITECTURA.md hace observable.
export type EstadoPedido =
  | "pendiente_pago"
  | "pagado"
  | "en_preparacion"
  | "despachado"
  | "en_reparto"
  | "entregado"
  | "incidencia"
  | "cancelado";

export const ESTADOS_PEDIDO: readonly EstadoPedido[] = [
  "pendiente_pago",
  "pagado",
  "en_preparacion",
  "despachado",
  "en_reparto",
  "entregado",
  "incidencia",
  "cancelado",
];

export const ETIQUETA_ESTADO_PEDIDO: Record<EstadoPedido, string> = {
  pendiente_pago: "Pendiente de pago",
  pagado: "Pagado",
  en_preparacion: "En preparación",
  despachado: "Despachado",
  en_reparto: "En reparto",
  entregado: "Entregado",
  incidencia: "Con incidencia",
  cancelado: "Cancelado",
};

// El estado del pago es lo unico que el §9 fija: id de la pasarela y estado.
export type EstadoPago = "iniciado" | "aprobado" | "rechazado" | "reembolsado";

export interface Pago {
  // Solo id y estado salen de Wompi (§9, SG-03): nunca datos de tarjeta.
  referencia_wompi: string;
  metodo: "pse" | "nequi" | "tarjeta";
  estado: EstadoPago;
  monto: Dinero;
}

// Copia CONGELADA de la direccion en el envio (ADR 0015): el historial de
// entregas no se puede reescribir aunque la libreta de `identidad` cambie.
export interface Envio {
  destinatario: string;
  direccion: string;
  ciudad: string;
  // Mas de la copia congelada del hecho de entrega (ADR 0015). `null` en los
  // pedidos legados; el formulario nuevo de entrega los llena.
  telefono: string | null;
  departamento: string | null;
  documento_destinatario: string | null;
  indicaciones: string | null;
  // Envios viejos, de cuando se despachaba por transportadora. Con reparto
  // propio ya no se piden; se siguen mostrando si vienen.
  transportadora: string | null;
  guia: string | null;
  // Reparto propio: quien lleva el pedido. El nombre viaja a todas las
  // lecturas (el papa sabe quien le llega); el celular SOLO al detalle del
  // back-office, por eso es opcional: el tablero y `mis-pedidos` no lo traen.
  repartidor_nombre: string | null;
  repartidor_celular?: string | null;
  // ISO 8601. `null` mientras no haya fecha estimada.
  entrega_estimada: string | null;
  entregado_en: string | null;
}

export interface LineaPedido {
  sku: string;
  nombre: string;
  cantidad: number;
  // Precio CONGELADO en la reserva (ADR 0012): no se mueve aunque el catalogo
  // cambie despues.
  precio_unitario: Dinero;
}

export interface Pedido {
  pedido_id: string;
  // El acudiente dueño del pedido (usuario de identidad). El back-office lo
  // usa para mostrar su correo con el padron protegido de identidad.
  usuario_id: string;
  // De que trabajo publicado salio este pedido, para poder cruzar back-office
  // con la cola de revision.
  trabajo_id: string | null;
  estado: EstadoPedido;
  creado_en: string;
  total: Dinero;
  hijos: number;
  colegios: string[];
  lineas: LineaPedido[];
  pago: Pago | null;
  envio: Envio | null;
}

// Los tipos de incidencia viven en el codigo de comercio (sin CHECK en la base,
// `dominio/despacho.py`); esta lista los repite para el formulario del admin.
export type TipoIncidencia = "no_habia_nadie" | "direccion_errada" | "rechazado" | "otro";

export const TIPOS_INCIDENCIA: readonly TipoIncidencia[] = [
  "no_habia_nadie",
  "direccion_errada",
  "rechazado",
  "otro",
];

export const ETIQUETA_TIPO_INCIDENCIA: Record<TipoIncidencia, string> = {
  no_habia_nadie: "No había nadie",
  direccion_errada: "Dirección errada",
  rechazado: "Rechazado",
  otro: "Otro",
};

// Un avance del pedido desde el back-office: quien (`actor_id`, un usuario de
// identidad), de que estado a cual y con que nota. `tipo_incidencia` es texto y
// no `TipoIncidencia` a proposito: un tipo que se agregue en comercio antes que
// aqui no debe romper la lectura.
export interface EntradaHistorialPedido {
  estado_desde: EstadoPedido;
  estado_hacia: EstadoPedido;
  actor_id: string;
  // Copia del correo de quien hizo el avance; `null` en filas anteriores.
  actor_correo: string | null;
  nota: string | null;
  tipo_incidencia: string | null;
  creado_en: string;
}

// El detalle del back-office: el pedido con el celular del repartidor y su
// historial. Solo staff lo lee.
export interface PedidoConHistorial extends Pedido {
  historial: EntradaHistorialPedido[];
}

// Lo que el admin manda a `POST /v1/ordenes/{id}/avanzar`. Comercio valida que
// la transicion le toque al back-office y que vengan los datos del destino.
export interface SolicitudAvancePedido {
  destino: EstadoPedido;
  repartidor_nombre?: string;
  repartidor_celular?: string;
  tipo_incidencia?: TipoIncidencia;
  nota?: string;
  // ISO 8601 CON zona (`2026-10-05T00:00:00-05:00`): sin zona, comercio
  // responde 400 para no correr la fecha al guardarla.
  entrega_estimada?: string;
}

// El panel de logistica necesita, ademas de la lista, el consolidado por estado
// para pintar las tarjetas de arriba sin recontar en cada pantalla.
export interface ResumenComercio {
  pedidos_totales: number;
  por_estado: Record<EstadoPedido, number>;
  ingresos_confirmados: Dinero;
  entregas_pendientes: number;
}

export interface TableroComercio {
  resumen: ResumenComercio;
  pedidos: Pedido[];
}

// Un pedido esta "en curso" si ya se pago pero todavia no llega. Es la cuenta
// que el operador mira primero.
export function pedidoEnCurso(pedido: Pedido): boolean {
  return (
    pedido.estado === "pagado" ||
    pedido.estado === "en_preparacion" ||
    pedido.estado === "despachado" ||
    pedido.estado === "en_reparto"
  );
}
