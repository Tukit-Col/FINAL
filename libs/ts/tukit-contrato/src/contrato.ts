// Tipos de la API de Tukit, derivados de `CONTRATO_API.md`.
//
// Decisiones:
// - El archivo transcribe el contrato y no lo interpreta; lo que el documento deja abierto va marcado
//   con `// INFERIDO:` y la razón.
// - `Dinero` es un entero en pesos colombianos, nunca flotante ni texto; `null` significa que no se
//   conoce el precio y es distinto de `0`.

export type Dinero = number;

export const GRADOS_CANONICOS: readonly string[] = [
  "Parvulos", "Prejardin", "Jardin", "Transicion", "Primero", "Segundo",
  "Tercero", "Cuarto", "Quinto", "Sexto", "Septimo", "Octavo", "Noveno",
  "Decimo", "Once",
];

export type TipoItem =
  | "util"
  | "texto"
  | "libro_libre"
  | "licencia_digital"
  | "no_comprar"
  | "diferido"
  | "uniforme"
  | "otro";

export const TIPOS_COMPRABLES: readonly TipoItem[] = ["util", "texto", "libro_libre"];

export type ModoAdquisicion =
  | "mercado_abierto"
  | "libro_libre"
  | "venta_directa_editorial"
  | "edicion_exclusiva"
  | "plataforma"
  | "diferido";

export const MODOS_SURTIBLES: readonly ModoAdquisicion[] = ["mercado_abierto", "libro_libre"];

export type EstadoResolucion = "RESUELTO_AUTO" | "AMBIGUO" | "SIN_MATCH" | "HUECO_CATALOGO";

export type PerfilKit = "Ahorrador" | "Fan" | "A tu Medida" | "Premium";

export const PERFILES: readonly PerfilKit[] = ["Ahorrador", "Fan", "A tu Medida", "Premium"];

export type Nivel = "economico" | "confiable" | "premium";

export type UnidadBase = "unidad" | "hoja" | "pliego" | "metro" | "gramo" | "mililitro";

export type EstadoTrabajo =
  | "encolado"
  | "procesando"
  | "espera_revision"
  | "publicado"
  | "fallido"
  | "cancelado";

export type NombreEtapa = "percepcion" | "normalizacion" | "resolucion" | "optimizacion";

export const ETAPAS: readonly NombreEtapa[] = [
  "percepcion",
  "normalizacion",
  "resolucion",
  "optimizacion",
];

// INFERIDO: el §4 solo muestra `"ok"`. El §8 habla de paginas "incompletas" y
export type EstadoEtapa = "pendiente" | "en_curso" | "ok" | "incompleta" | "fallida";

export interface Etapa {
  nombre: NombreEtapa;
  estado: EstadoEtapa;
  ms: number;
}

export interface Contacto {
  correo: string;
  celular: string;
}

export interface HijoSolicitud {
  referencia: string;
  colegio_id: string;
  grado: string;
  version_id?: string;
  apodo?: string;
}

export interface Pesos {
  precio: number;
  marca_exigida: number;
  calidad: number;
  personaje: number;
}

export const PESOS_POR_DEFECTO: Pesos = {
  precio: 0.35,
  marca_exigida: 0.3,
  calidad: 0.25,
  personaje: 0.1,
};

// INFERIDO: el §3 solo atestigua `"libros"`. Los cuatro valores son los cuatro
export type DolorDeclarado = "disponibilidad" | "libros" | "un_solo_lugar" | "precio";

export interface Preferencias {
  pesos?: Pesos;
  disposicion_sobreprecio?: number;
  personaje_por_hijo?: Record<string, string[]>;
  dolor_declarado?: DolorDeclarado;
  prioridad?: "precio" | "equilibrio" | "calidad";
}

export interface SolicitudTrabajo {
  contacto?: Contacto;
  hijos: HijoSolicitud[];
  preferencias?: Preferencias;
}

export interface TrabajoCreado {
  trabajo_id: string;
  estado: "encolado";
  estimado_segundos: number;
  consultar_en: string;
}

export interface GradoCanonico {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  trabajo_id: string;
  publicado_en?: string | null;
  borrador_trabajo_id?: string | null;
}

export interface BorradorKits {
  trabajo_id: string;
  basado_en: string;
  nuevo: boolean;
}

export interface AplicarCanonico {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  perfil: PerfilKit;
  personaje?: string;
  apodo?: string;
  usuario_id?: string;
}

export interface TrabajoAplicado {
  trabajo_id: string;
  perfil: PerfilKit;
  personaje: string | null;
  total: number;
}

export interface Entrega {
  destinatario: string;
  direccion: string;
  ciudad: string;
  departamento?: string;
  indicaciones?: string;
  localidad?: string;
  latitud?: number;
  longitud?: number;
}

export interface CambioDeProducto {
  trabajo_id: string;
  perfil: PerfilKit;
  item_id: string;
  sku: string;
}

export interface CambioDeDescarte {
  trabajo_id: string;
  perfil: PerfilKit;
  item_id: string;
  descartado: boolean;
}

export interface OpcionDeLinea {
  sku: string;
  nombre: string;
  marca: string | null;
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
  precio: Dinero;
  unidades_por_empaque: number;
  unidades_a_comprar: number;
  subtotal: Dinero;
  diferencia: Dinero | null;
  en_kit: boolean;
  sugerido: boolean;
}

export interface OpcionesDeLinea {
  item_id: string;
  concepto: string | null;
  opciones: OpcionDeLinea[];
}

export interface SolicitudCheckout {
  perfil: PerfilKit;
  correo: string;
  entrega: Entrega;
  metodo?: string;
  url_redireccion?: string;
}

export interface Checkout {
  pedido_id: string;
  total: number;
  pago_id: string;
  referencia_wompi?: string;
  transaccion_wompi?: string;
  estado?: string;
  url_redireccion: string | null;
  widget: WidgetWompi | null;
}

export interface PagoIniciado {
  pago_id: string;
  referencia_wompi: string;
  estado: string;
  url_redireccion: string | null;
  widget: WidgetWompi | null;
}

export interface WidgetWompi {
  publicKey: string;
  currency: string;
  amountInCents: number;
  reference: string;
  signature: { integrity: string };
  customerData?: { email?: string };
  redirectUrl?: string;
}

export interface ResultadoPago {
  pedido_id: string;
  total: number;
  estado_pago: "iniciado" | "aprobado" | "rechazado" | "reembolsado";
  estado_pedido: string;
  trabajo_id: string | null;
}

export interface HijoSubida {
  referencia: string;
  colegio_id?: string;
  colegio_dane?: string;
  colegio_nombre?: string;
  grado: string;
  anio_lectivo?: number;
  apodo?: string;
}

export interface SubidaHecha {
  referencia: string;
  version_id: string | null;
  grado: string;
  estado?: "pendiente";
}

export interface SubidaListas {
  subidas: SubidaHecha[];
  contacto_referencia: string | null;
}

export interface Oferta {
  tienda: string;
  precio: Dinero;
  vigente_hasta: string | null;
}

export interface ProductoKit {
  sku: string;
  nombre: string;
  marca: string | null;
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
  confianza: number;
  ofertas: Oferta[];
}

export interface Edicion {
  isbn13: string;
  titulo: string;
  editorial: string;
  anio_edicion: number;
}

// INFERIDO: el §5.2 dice "del grafo de sustituibilidad, si los hay" sin fijar
export interface Sustituto {
  concepto: string;
  nombre: string;
  grado: number;
  motivo: string;
  producto?: ProductoKit | null;
}

export interface LineaKit {
  item_id: string;
  hijo?: string;
  descripcion: string;
  tipo: TipoItem;
  estado_resolucion?: EstadoResolucion;
  modo_adquisicion?: ModoAdquisicion;

  informativa?: boolean;
  instruccion_colegio?: string | null;
  url_externa?: string | null;
  nota?: string | null;

  cantidad_pedida?: number;
  unidad_base?: UnidadBase;
  unidades_por_empaque?: number;
  unidades_a_comprar?: number;

  producto_elegido?: ProductoKit | null;
  alternativas?: ProductoKit[];

  edicion?: Edicion | null;
  no_consolidable?: boolean;
  motivo_no_consolidable?: string | null;

  cambiado_por_acudiente?: boolean;
  sku_sugerido?: string | null;

  concepto?: string | null;
  atributo_faltante?: Record<string, string> | null;
  mensaje?: string | null;
  sustitutos?: Sustituto[];

  precio?: Dinero | null;
  subtotal_linea: Dinero | null;

  descartado?: boolean;
  subtotal_descartado?: Dinero | null;

  se_compra_en?: string | null;
  url_compra?: string | null;
}

export interface Consolidacion {
  concepto: string;
  hijos: string[];
  demanda_base: number;
  producto: string;
  unidades_a_comprar: number;
  ahorro: Dinero;
  explicacion: string;
}

export interface Objetivos {
  costo: Dinero;
  fidelidad: number;
  disponibilidad: number;
}

export interface Kit {
  perfil: PerfilKit;
  total: Dinero;
  objetivos: Objetivos;
  lineas: LineaKit[];
  consolidaciones: Consolidacion[];
  personaje_sin_encaje?: { hijo: string; concepto: string; personaje: string }[];
}

export interface Recomendacion {
  perfil: PerfilKit;
  razon: string;
  dentro_de_presupuesto: boolean | null;
  pesos_usados: Pesos;
}

export interface Degradacion {
  dependencia: string;
  efecto: string;
  lineas_afectadas: number;
}

export interface Trabajo {
  trabajo_id: string;
  estado: EstadoTrabajo;
  etapas: Etapa[];
  kits: Kit[];
  recomendado: Recomendacion | null;
  degradaciones: Degradacion[];
  origen?: string;
  hijos?: HijoDeTrabajo[];
  personajes_por_hijo?: Record<string, string[]>;
}

export interface TrabajoResumen {
  trabajo_id: string;
  estado: EstadoTrabajo;
  creado_en: string;
  hijos: HijoSolicitud[];
  preferencias: Preferencias;
}

interface SolicitudBase {
  colegio_id: string;
  colegio_nombre: string | null;
  grado: string;
  creado_en: string;
}

export interface SolicitudRecibida extends SolicitudBase {
  tipo: "recibida";
  tarea_id?: string | null;
}

export interface SolicitudAprobada extends SolicitudBase {
  tipo: "aprobada";
  trabajo_id: string;
}

export interface SolicitudEnProceso extends SolicitudBase {
  tipo: "trabajo";
  trabajo_id: string;
  estado: EstadoTrabajo;
}

export type Solicitud = SolicitudRecibida | SolicitudAprobada | SolicitudEnProceso;

export interface MisSolicitudes {
  solicitudes: Solicitud[];
  listas_disponibles: boolean;
}

export interface ErrorApi {
  error: string;
  mensaje: string;
  campo?: string;
}

export interface ErrorVariosGrados extends ErrorApi {
  error: "lista_de_varios_grados";
  grados_detectados: string[];
  paginas: number;
}

export function esErrorVariosGrados(valor: ErrorApi): valor is ErrorVariosGrados {
  return valor.error === "lista_de_varios_grados";
}

export interface ErrorDemasiadasPeticiones extends ErrorApi {
  error: "demasiadas_peticiones";
  reintentar_en_segundos: number;
}

export const EXTENSIONES_ACEPTADAS = [".pdf", ".jpg", ".jpeg", ".png", ".webp"] as const;
export const TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024;

export function validarArchivo(archivo: File): string | null {
  const nombre = archivo.name.toLowerCase();
  if (!EXTENSIONES_ACEPTADAS.some((ext) => nombre.endsWith(ext))) {
    return "Formato no soportado. Sube la lista en PDF, JPG, PNG o WEBP.";
  }
  if (archivo.size === 0) {
    return "El archivo está vacío.";
  }
  if (archivo.size > TAMANO_MAXIMO_BYTES) {
    return "El archivo supera el límite de 10 MB.";
  }
  return null;
}

export interface AcudienteResumen {
  usuario_id: string;
  estado: EstadoTrabajo;
  actualizado_en: string;
  trabajo_id: string;
  grados: string[];
  preferencias: Preferencias;
}

export interface EntradaCola {
  trabajo_id: string;
  estado: EstadoTrabajo;
  origen?: string;
  recibido_en: string;
  hijos: number;
  lineas_totales: number;
  lineas_pendientes: number;
  colegios: string[];
  grados: string[];
  edicion_de?: string | null;
}

export interface ColaAdmin {
  entradas: EntradaCola[];
}

export interface TrabajoAdmin extends Trabajo {
  recibido_en: string;
  contacto_id: string;
  lineas_pendientes: string[];
  nota_revision?: string | null;
  origen?: string;
  hijos?: Omit<HijoDeTrabajo, "apodo">[];
}

export interface HijoDeTrabajo {
  referencia?: string;
  colegio_id?: string;
  grado?: string;
  anio_lectivo?: number;
  version_id?: string;
  basado_en?: string;
  apodo?: string;
}

export interface ValidarLinea {
  sku?: string;
  nota?: string;
}

export interface SinCoincidencia {
  motivo: string;
}

export interface AltaProducto {
  concepto: string;
  nombre: string;
  marca: string | null;
  nivel: Nivel;
  personaje: string | null;
  imagen_url: string | null;
  tienda: string;
  precio: Dinero;
  url?: string | null;
  trabajo_id?: string;
  item_id?: string;
}

export interface ProductoDadoDeAlta {
  sku: string;
}

export interface MarcarNoDisponible {
  motivo: string;
}

export interface DecisionRevision {
  decision: "aprobar" | "devolver";
  nota?: string;
}

export interface PercepcionCruda {
  paginas: { pagina: number; crudo: string }[];
  items: {
    texto_original?: string;
    descripcion?: string;
    cantidad: number | null;
    confianza: number | null;
  }[];
}
