// Tipos de la API de Tukit, derivados de `arquitectura/CONTRATO_API.md` v1.0.
//
// El contrato es de otro equipo y este fichero NO lo interpreta: lo transcribe.
// Donde el documento deja un hueco (una forma que muestra un ejemplo pero no
// enumera), el hueco va marcado con `// INFERIDO:` y la razon, para que se
// pueda contrastar contra lo que el backend construya en vez de descubrirse
// como un fallo de deserializacion.

// ---------------------------------------------------------------- §1.4 Dinero
//
// Entero en pesos colombianos. Nunca flotante, nunca string. `null` significa
// "no se conoce el precio", que es distinto de `0`.
//
// El alias no da seguridad de tipos por si solo (un `number` cualquiera pasa),
// pero si nombra la unidad en cada firma donde aparece, que es donde se comete
// el error de meter centavos o decimales. La guarda en tiempo de ejecucion
// vive en `dinero.ts`.
export type Dinero = number;

// ------------------------------------------------------------- §1.1 TipoItem
export type TipoItem =
  | "util"
  | "texto"
  | "libro_libre"
  | "licencia_digital"
  | "no_comprar"
  | "diferido"
  | "uniforme"
  | "otro";

// Los unicos que cuentan para la metrica de "catalogo sin huecos": esa se mide
// solo sobre lo comprable.
export const TIPOS_COMPRABLES: readonly TipoItem[] = ["util", "texto", "libro_libre"];

// --------------------------------------------------- §1.1.1 ModoAdquisicion
export type ModoAdquisicion =
  | "mercado_abierto"
  | "libro_libre"
  | "venta_directa_editorial"
  | "edicion_exclusiva"
  | "plataforma"
  | "diferido";

export const MODOS_SURTIBLES: readonly ModoAdquisicion[] = ["mercado_abierto", "libro_libre"];

// ------------------------------------------------------ §1.2 EstadoResolucion
export type EstadoResolucion = "RESUELTO_AUTO" | "AMBIGUO" | "SIN_MATCH" | "HUECO_CATALOGO";

// ------------------------------------------------------------- §1.3 PerfilKit
export type PerfilKit = "Ahorrador" | "Fan" | "Premium";

export const PERFILES: readonly PerfilKit[] = ["Ahorrador", "Fan", "Premium"];

// `nivel` de un producto, que NO es el perfil de un kit aunque compartan la
// palabra "premium". Sale de `catalogo.modelos.base.Nivel`.
export type Nivel = "economico" | "confiable" | "premium";

// `catalogo.modelos.base.UnidadBase`.
export type UnidadBase = "unidad" | "hoja" | "pliego" | "metro" | "gramo" | "mililitro";

// ------------------------------------------------------------- §2 El trabajo
export type EstadoTrabajo = "encolado" | "procesando" | "espera_revision" | "publicado" | "fallido";

export type NombreEtapa = "percepcion" | "normalizacion" | "resolucion" | "optimizacion";

export const ETAPAS: readonly NombreEtapa[] = [
  "percepcion",
  "normalizacion",
  "resolucion",
  "optimizacion",
];

// INFERIDO: el §4 solo muestra `"ok"`. El §8 habla de paginas "incompletas" y
// de trabajos `fallido`, y una etapa que todavia no corrio tiene que poder
// decirlo, asi que se admiten los cinco. La UI trata cualquier valor que no
// reconozca como `pendiente` en vez de romperse.
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
}

// ----------------------------------------------------------- §3 Preferencias
export interface Pesos {
  precio: number;
  marca_exigida: number;
  calidad: number;
  personaje: number;
}

// Los valores por defecto medidos de la P21 de la encuesta, normalizados.
export const PESOS_POR_DEFECTO: Pesos = {
  precio: 0.35,
  marca_exigida: 0.3,
  calidad: 0.25,
  personaje: 0.1,
};

// INFERIDO: el §3 solo atestigua `"libros"`. Los cuatro valores son los cuatro
// dolores que mide la encuesta (37 % disponibilidad, 28 % libros, 22 % un solo
// lugar, 17 % precio) y son los que eligen el titular de la UI.
export type DolorDeclarado = "disponibilidad" | "libros" | "un_solo_lugar" | "precio";

export interface Preferencias {
  pesos?: Pesos;
  // Restriccion DURA, no una pista.
  presupuesto_por_hijo?: Dinero | null;
  disposicion_sobreprecio?: number;
  personaje_por_hijo?: Record<string, string[]>;
  dolor_declarado?: DolorDeclarado;
}

export interface SolicitudTrabajo {
  contacto: Contacto;
  hijos: HijoSolicitud[];
  preferencias?: Preferencias;
}

export interface TrabajoCreado {
  trabajo_id: string;
  estado: "encolado";
  estimado_segundos: number;
  consultar_en: string;
}

// --------------------------------------------------------------- §5 Los kits
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
// la forma. Se modela con lo que `catalogo.modelos.catalogo.Sustituibilidad-
// Concepto` obliga a tener: concepto destino, grado y motivo curado.
export interface Sustituto {
  concepto: string;
  nombre: string;
  grado: number;
  motivo: string;
  producto?: ProductoKit | null;
}

// Una sola forma con campos opcionales, y no una union discriminada, porque
// asi es como el contrato la escribe: `tipo` no separa los casos (un `texto`
// puede venir resuelto o informativo). Las funciones de `linea.ts` son las que
// clasifican, y estan en un solo sitio para que la pantalla no repita reglas.
export interface LineaKit {
  item_id: string;
  hijo?: string;
  descripcion: string;
  tipo: TipoItem;
  estado_resolucion?: EstadoResolucion;
  modo_adquisicion?: ModoAdquisicion;

  // §5.1.1 — `informativa: true` significa se muestra, no se cobra.
  informativa?: boolean;
  instruccion_colegio?: string | null;
  url_externa?: string | null;
  nota?: string | null;

  // §5 — los tres numeros que el sistema anterior colapsaba en uno.
  cantidad_pedida?: number;
  unidad_base?: UnidadBase;
  unidades_por_empaque?: number;
  unidades_a_comprar?: number;

  producto_elegido?: ProductoKit | null;
  alternativas?: ProductoKit[];

  // §5.1 — textos escolares.
  edicion?: Edicion | null;
  no_consolidable?: boolean;
  motivo_no_consolidable?: string | null;

  // §5.2 — huecos de catalogo.
  concepto?: string | null;
  atributo_faltante?: Record<string, string> | null;
  mensaje?: string | null;
  sustitutos?: Sustituto[];

  precio?: Dinero | null;
  subtotal_linea: Dinero | null;
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
  // Incluye solo lineas con `informativa: false` (§5.1.1).
  total: Dinero;
  objetivos: Objetivos;
  lineas: LineaKit[];
  consolidaciones: Consolidacion[];
}

// ---------------------------------------------------------- §6 Recomendacion
export interface Recomendacion {
  perfil: PerfilKit;
  razon: string;
  dentro_de_presupuesto: boolean;
  pesos_usados: Pesos;
}

// ------------------------------------------------------------ §8 Degradacion
export interface Degradacion {
  dependencia: string;
  efecto: string;
  lineas_afectadas: number;
}

// ------------------------------------------------------- §4 Consultar trabajo
export interface Trabajo {
  trabajo_id: string;
  estado: EstadoTrabajo;
  etapas: Etapa[];
  // Mientras `estado` no sea `publicado`, va vacio: el acudiente nunca ve un
  // kit sin revisar.
  kits: Kit[];
  recomendado: Recomendacion | null;
  degradaciones: Degradacion[];
}

// ---------------------------------------------------------------- §11 Errores
export interface ErrorApi {
  error: string;
  mensaje: string;
  campo?: string;
}

// §2.1 — el 422 que rechaza un PDF con la lista de trece grados.
export interface ErrorVariosGrados extends ErrorApi {
  error: "lista_de_varios_grados";
  grados_detectados: string[];
  paginas: number;
}

export function esErrorVariosGrados(valor: ErrorApi): valor is ErrorVariosGrados {
  return valor.error === "lista_de_varios_grados";
}

// ------------------------------------------------- §2 Limites de los archivos
//
// "Formatos y limites: los que ya valida el frontend".
export const EXTENSIONES_ACEPTADAS = [".pdf", ".jpg", ".jpeg", ".png", ".webp"] as const;
export const TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024;

export function validarArchivo(archivo: File): string | null {
  const nombre = archivo.name.toLowerCase();
  if (!EXTENSIONES_ACEPTADAS.some((ext) => nombre.endsWith(ext))) {
    return "Formato no soportado. Sube la lista en PDF, JPG, PNG o WEBP.";
  }
  if (archivo.size === 0) {
    return "El archivo esta vacio.";
  }
  if (archivo.size > TAMANO_MAXIMO_BYTES) {
    return "El archivo supera el limite de 10 MB.";
  }
  return null;
}

// ----------------------------------------------------- §7 Revision (admin)
//
// El §7 lista las rutas y sus requisitos pero no los cuerpos, salvo el de
// `/revision`. Todo lo de abajo excepto `DecisionRevision` es INFERIDO a
// partir de lo que cada requisito del SRS necesita para poder ejecutarse.

// INFERIDO (AD-02/AD-03): la cola necesita, por trabajo, con que decidir a
// cual entrar primero.
export interface EntradaCola {
  trabajo_id: string;
  estado: EstadoTrabajo;
  recibido_en: string;
  hijos: number;
  lineas_totales: number;
  lineas_pendientes: number;
  colegios: string[];
  grados: string[];
}

export interface ColaAdmin {
  entradas: EntradaCola[];
}

// INFERIDO (AD-03): el detalle del trabajo en admin es el mismo `Trabajo` mas
// lo que la revision necesita y el acudiente no ve: por que cada linea esta
// pendiente y quien la toco.
export interface TrabajoAdmin extends Trabajo {
  recibido_en: string;
  contacto_id: string;
  lineas_pendientes: string[];
  nota_revision?: string | null;
}

// INFERIDO (AD-04): validar es fijar el producto de la linea. Sin `sku` se lee
// como "confirmo el que el sistema eligio".
export interface ValidarLinea {
  sku?: string;
  nota?: string;
}

// INFERIDO (AD-04): una marca de "sin coincidencia" que no diga por que no se
// puede revisar despues.
export interface SinCoincidencia {
  motivo: string;
}

// INFERIDO (AD-07): alta manual de producto con precio e imagen, que es lo que
// el requisito nombra. `precio` en pesos enteros, como todo `Dinero`.
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
  // Cuando el alta resuelve una linea concreta de un trabajo.
  trabajo_id?: string;
  item_id?: string;
}

export interface ProductoDadoDeAlta {
  sku: string;
}

// INFERIDO (AD-05).
export interface MarcarNoDisponible {
  motivo: string;
}

// El unico cuerpo que el §7 si fija.
export interface DecisionRevision {
  decision: "aprobar" | "devolver";
  nota?: string;
}
