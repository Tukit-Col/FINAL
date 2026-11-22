export const VERSION_OPERACION_ASUMIDA = "1.x-asumida";

export type OrigenCaso =
  | "acudiente"
  | "colegio"
  | "operador"
  | "sistema";

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
  vence_en: string | null;
  trabajo_id: string | null;
  pedido_id: string | null;
  asignado_a: string | null;
}

export const CATEGORIAS_CASO_ACUDIENTE: readonly CategoriaCaso[] = [
  "peticion",
  "queja",
  "reclamo",
  "sugerencia",
  "pago",
  "entrega",
];

export interface SolicitudCaso {
  categoria: CategoriaCaso;
  asunto: string;
  descripcion: string;
  contacto: { correo: string; celular: string };
  trabajo_id?: string | null;
}

export interface CasoCreado {
  caso_id: string;
  estado: EstadoCaso;
  categoria: CategoriaCaso;
  recibido_en: string;
  vence_en: string | null;
}

export interface ResumenOperacion {
  abiertos: number;
  urgentes: number;
  vencen_hoy: number;
  resueltos_semana: number;
  sin_asignar?: number;
  vencidos?: number;
}

export interface BandejaOperacion {
  resumen: ResumenOperacion;
  casos: Caso[];
}

export type EstadoCorreo = "enviada" | "fallida" | "omitida";

export interface CorreoEnviado {
  id: string;
  usuario_id: string;
  canal: string;
  plantilla: string;
  estado: EstadoCorreo;
  asunto: string | null;
  detalle: string | null;
  destino_dominio: string | null;
  pedido: string | null;
  caso: string | null;
  creado_en: string | null;
  enviada_en: string | null;
}

export interface FiltrosCorreos {
  estado?: EstadoCorreo;
  plantilla?: string;
  pedido?: string;
  caso?: string;
  limite?: number;
}

export interface BandejaCorreos {
  resumen: Partial<Record<EstadoCorreo, number>>;
  correos: CorreoEnviado[];
}

export function casoActivo(caso: Caso): boolean {
  return caso.estado !== "resuelto" && caso.estado !== "cerrado";
}

export interface SolicitudMiCaso {
  categoria: CategoriaCaso;
  asunto: string;
  descripcion: string;
  trabajo_id?: string | null;
  pedido_id?: string | null;
}

export interface MiCaso {
  caso_id: string;
  categoria: CategoriaCaso;
  estado: EstadoCaso;
  asunto: string;
  abierto_en: string;
  vence_en: string | null;
  trabajo_id: string | null;
  pedido_id: string | null;
}

export interface ComentarioDeCaso {
  texto: string;
  creado_en: string;
  autor: "acudiente" | "equipo";
}

export interface MiCasoDetalle extends MiCaso {
  descripcion: string;
  comentarios: ComentarioDeCaso[];
}
