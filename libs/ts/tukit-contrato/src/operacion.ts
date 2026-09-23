// Superficie de LECTURA de `operacion`. ASUMIDA, no transcrita.
//
// `operacion` es el servicio de casos, PQRS, notificaciones, auditoria y
// telemetria (§1 de ARQUITECTURA.md). Cada falla del flujo transaccional abre
// un Caso aqui (§Procesos: AuthFailure, MappingFailure, PaymentFailure,
// StockFailure, DeliveryFailure). El contrato v1.0 no publica su superficie de
// lectura, asi que estos tipos son una inferencia a partir de esa
// responsabilidad canonica y de la ADR 0004 (gestion de casos propia, no
// Salesforce).
//
// Vive aparte de `contrato.ts` por la misma razon que `comercio.ts` y
// `catalogo.ts`: separar lo transcrito de lo asumido. La bandeja de tickets del
// back-office consume SOLO esto.

export const VERSION_OPERACION_ASUMIDA = "1.x-asumida";

// De donde nacio el caso. `sistema` son las fallas de la saga (§Procesos); el
// resto son PQRS que abre una persona.
export type OrigenCaso =
  | "acudiente"
  | "colegio"
  | "operador"
  | "sistema";

// Las cinco fallas nombradas de la saga + las categorias de PQRS.
export type CategoriaCaso =
  | "pago"
  | "stock"
  | "entrega"
  | "mapeo_lista"
  | "autenticacion"
  | "peticion"
  | "queja"
  | "reclamo"
  | "sugerencia";

export const ETIQUETA_CATEGORIA_CASO: Record<CategoriaCaso, string> = {
  pago: "Pago",
  stock: "Stock",
  entrega: "Entrega",
  mapeo_lista: "Lista mal leída",
  autenticacion: "Acceso",
  peticion: "Petición",
  queja: "Queja",
  reclamo: "Reclamo",
  sugerencia: "Sugerencia",
};

export type EstadoCaso = "abierto" | "en_gestion" | "esperando_tercero" | "resuelto" | "cerrado";

export const ESTADOS_CASO: readonly EstadoCaso[] = [
  "abierto",
  "en_gestion",
  "esperando_tercero",
  "resuelto",
  "cerrado",
];

export const ETIQUETA_ESTADO_CASO: Record<EstadoCaso, string> = {
  abierto: "Abierto",
  en_gestion: "En gestión",
  esperando_tercero: "Esperando a un tercero",
  resuelto: "Resuelto",
  cerrado: "Cerrado",
};

// La prioridad ordena la bandeja. Una PQRS tiene un reloj legal (Ley 1755); una
// falla de pago bloquea plata. El operador entra por lo urgente primero.
export type Prioridad = "urgente" | "alta" | "media" | "baja";

export const ORDEN_PRIORIDAD: Record<Prioridad, number> = {
  urgente: 0,
  alta: 1,
  media: 2,
  baja: 3,
};

export const ETIQUETA_PRIORIDAD: Record<Prioridad, string> = {
  urgente: "Urgente",
  alta: "Alta",
  media: "Media",
  baja: "Baja",
};

export interface Caso {
  caso_id: string;
  origen: OrigenCaso;
  categoria: CategoriaCaso;
  estado: EstadoCaso;
  prioridad: Prioridad;
  asunto: string;
  abierto_en: string;
  // ISO 8601 del vencimiento del SLA/termino legal. `null` si no aplica.
  vence_en: string | null;
  // Referencias cruzadas a otros dominios (declaradas, nunca FK fisica).
  trabajo_id: string | null;
  pedido_id: string | null;
  asignado_a: string | null;
}

export interface ResumenOperacion {
  abiertos: number;
  urgentes: number;
  vencen_hoy: number;
  resueltos_semana: number;
}

export interface BandejaOperacion {
  resumen: ResumenOperacion;
  casos: Caso[];
}

export function casoActivo(caso: Caso): boolean {
  return caso.estado !== "resuelto" && caso.estado !== "cerrado";
}
