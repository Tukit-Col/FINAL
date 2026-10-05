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

// Los grados del sistema educativo colombiano, en orden pedagógico (el mismo
// que sirve identidad en `/v1/grados`). Es la lista canónica: sirve para
// ordenar los grados de un colegio y —en la ruta de subir archivo— para elegir
// el grado aunque el colegio todavía no tenga ninguna lista verificada, que es
// justo cuando el acudiente sugiere su colegio. Client-safe: se exporta por
// `indice.ts` y no arrastra nada de servidor.
export const GRADOS_CANONICOS: readonly string[] = [
  "Parvulos", "Prejardin", "Jardin", "Transicion", "Primero", "Segundo",
  "Tercero", "Cuarto", "Quinto", "Sexto", "Septimo", "Octavo", "Noveno",
  "Decimo", "Once",
];

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
// Ahorrador y Premium salen siempre; Fan solo si se pidió un personaje y
// "A tu Medida" solo con el punto medio o un tope (ADR 0030).
export type PerfilKit = "Ahorrador" | "Fan" | "A tu Medida" | "Premium";

export const PERFILES: readonly PerfilKit[] = ["Ahorrador", "Fan", "A tu Medida", "Premium"];

// `nivel` de un producto, que NO es el perfil de un kit aunque compartan la
// palabra "premium". Sale de `catalogo.modelos.base.Nivel`.
export type Nivel = "economico" | "confiable" | "premium";

// `catalogo.modelos.base.UnidadBase`.
export type UnidadBase = "unidad" | "hoja" | "pliego" | "metro" | "gramo" | "mililitro";

// ------------------------------------------------------------- §2 El trabajo
// `cancelado`: el acudiente cancelo la solicitud (ADR 0031). Terminal, y no
// sale en "Mis solicitudes".
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
  // Lo que eligió en el paso 3: `equilibrio` pide el kit "A tu Medida".
  prioridad?: "precio" | "equilibrio" | "calidad";
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

// --------------------------------------- §Ruta rapida sobre la cache bendita
//
// Un (colegio, grado, anio) publicado es la cache de 3 kits validados. El
// acudiente que cae en uno de estos NO sube PDF ni entra a la cola: elige su
// nivel + personaje y se le arma el pedido al vuelo (`aplicarCanonico`).
export interface GradoCanonico {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  trabajo_id: string;
}

export interface AplicarCanonico {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  perfil: PerfilKit;
  personaje?: string;
  usuario_id?: string;
}

export interface TrabajoAplicado {
  trabajo_id: string;
  perfil: PerfilKit;
  personaje: string | null;
  total: number;
}

// El checkout del acudiente: elige el perfil de kit + a donde entregar, y el
// backend (Inteligencia) arma la orden en Comercio server-to-server. El
// navegador NUNCA manda lineas ni ids de producto: el trabajo ya tiene el kit,
// y el id canonico de cada producto lo resuelve Comercio (RPO cero, ADR 0017).
export interface Entrega {
  destinatario: string;
  direccion: string;
  ciudad: string;
}

// El acudiente cambia el producto de un renglón de su kit por el sugerido o por
// una de sus alternativas. El cambio vive en SU trabajo, no en el kit canónico.
export interface CambioDeProducto {
  trabajo_id: string;
  perfil: PerfilKit;
  item_id: string;
  sku: string;
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
  // Modo simulado: a donde mandar al acudiente (la pasarela falsa).
  url_redireccion: string | null;
  // Wompi: las opciones firmadas de `new WidgetCheckout({...})`. El pago se
  // abre en un modal y el acudiente no sale de Tukit.
  widget: WidgetWompi | null;
}

// Un intento de pago nuevo sobre un pedido que ya existe (pendiente de pago),
// p. ej. desde "Mis pedidos". Misma forma que el pago de `Checkout`.
export interface PagoIniciado {
  pago_id: string;
  referencia_wompi: string;
  estado: string;
  url_redireccion: string | null;
  widget: WidgetWompi | null;
}

// Las opciones del widget de Wompi, con sus nombres. Las arma y firma el
// backend: el secreto de integridad nunca llega al navegador.
export interface WidgetWompi {
  publicKey: string;
  currency: string;
  amountInCents: number;
  reference: string;
  signature: { integrity: string };
  customerData?: { email?: string };
  // Solo lo usa PSE: el banco se lleva la pestana y Wompi vuelve aqui con `?id=`.
  redirectUrl?: string;
}

// El estado del pago tras consultarlo a la pasarela, cuando el acudiente
// regresa de Wompi. `estado_pedido` es el del pedido en Comercio.
export interface ResultadoPago {
  pedido_id: string;
  total: number;
  estado_pago: "iniciado" | "aprobado" | "rechazado" | "reembolsado";
  estado_pedido: string;
  // El kit del que salió el pedido; `null` si el pedido no viene de uno.
  trabajo_id: string | null;
}

// --------------------------------------------------- §2 Subida de listas (P2)
//
// La puerta del acudiente que sube el PDF de cada hijo: cada archivo se percibe
// y se importa al catalogo como una version SIN revisar de esa (colegio, grado),
// ligada al padre por su `contacto_referencia` (el `usuario_id` que Identidad
// emite; NUNCA su correo ni telefono). No se crea ningun trabajo: el padre
// espera a que un administrador apruebe la version y recien ahi se arma su kit.
// Es distinto de `crearTrabajo`, que arma un kit desechable al vuelo.
export interface HijoSubida {
  referencia: string;
  // El colegio se designa de UNA de dos formas, segun como llego el acudiente:
  //   • `colegio_id`: eligio un colegio ALIADO ya conocido (ruta "lista_oficial").
  //   • `colegio_dane` (+ `colegio_nombre`): lo busco en el directorio de Bogota
  //     al subir su archivo; el colegio todavia no existe en Tukit y nacera
  //     cuando un administrador apruebe la version. El UUID se deriva del DANE.
  //   • solo `colegio_nombre`: no lo encontro en el directorio y lo escribio a
  //     mano; el UUID se deriva del nombre normalizado para que dos acudientes
  //     que escriban el mismo colegio converjan a la misma version.
  // El backend deriva el `colegio_id` final; el frontend manda lo que tenga.
  colegio_id?: string;
  colegio_dane?: string;
  colegio_nombre?: string;
  grado: string;
  anio_lectivo?: number;
}

// El resultado por hijo: a que version pendiente quedo ligado y con que grado
// (el grado real lo resuelve la percepcion del PDF, puede diferir del elegido).
export interface SubidaHecha {
  referencia: string;
  version_id: string;
  grado: string;
}

export interface SubidaListas {
  subidas: SubidaHecha[];
  // La UNICA traza al acudiente, o null si no dejo contacto. Es un id, jamas PII.
  contacto_referencia: string | null;
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

  // El acudiente cambió el producto sugerido por una alternativa: `sku_sugerido`
  // es el que venía, para ofrecerle volver a él.
  cambiado_por_acudiente?: boolean;
  sku_sugerido?: string | null;

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
  // `null` cuando el acudiente no declaro presupuesto: no hay tope contra el
  // que medir. Solo `false` significa "se pasa del tope".
  dentro_de_presupuesto: boolean | null;
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
  // De dónde salió el trabajo. `parent_apply` es la ruta rápida: ahí el
  // "recomendado" es el kit que el acudiente eligió al empezar.
  origen?: string;
}

// ---------------------------------------------- §4.1 "Mis solicitudes" del panel
// Una solicitud del acudiente es una de dos cosas —una lista que subio, o un
// trabajo del pipeline— y a veces las dos son la misma (la lista aprobada
// engendra su trabajo). El backend las une y las expone como una union por
// `tipo`, para que el panel discrimine sin adivinar por campos ausentes.
interface SolicitudBase {
  // `colegio_id` viaja como string para casar con el mapa de nombres del panel.
  colegio_id: string;
  // `null` cuando el nombre vive en identidad (colegio aliado), no en catalogo:
  // la web lo resuelve con su propio mapa de colegios.
  colegio_nombre: string | null;
  grado: string;
  // ISO-8601. Clave de orden unificada: la fecha de la lista o del trabajo.
  creado_en: string;
}

// Lista subida, aun sin aprobar: "una persona esta revisando tu lista".
export interface SolicitudRecibida extends SolicitudBase {
  tipo: "recibida";
  // Con esto el acudiente la cancela (`cancelarListaSubida`).
  tarea_id?: string | null;
}

// Lista aprobada: su trabajo ya existe y el kit esta listo.
export interface SolicitudAprobada extends SolicitudBase {
  tipo: "aprobada";
  trabajo_id: string;
}

// Trabajo sin lista subida (ruta rapida o lista verificada directa): se muestra
// su estado en palabras y un enlace segun este publicado o no.
export interface SolicitudEnProceso extends SolicitudBase {
  tipo: "trabajo";
  trabajo_id: string;
  estado: EstadoTrabajo;
}

export type Solicitud = SolicitudRecibida | SolicitudAprobada | SolicitudEnProceso;

// Resultado del endpoint: las solicitudes mas una marca de si se pudieron leer
// las listas subidas. `listas_disponibles: false` significa que catalogo no
// respondio: el panel muestra los trabajos y avisa que faltan las listas, en
// vez de fallar entero.
export interface MisSolicitudes {
  solicitudes: Solicitud[];
  listas_disponibles: boolean;
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
    return "El archivo está vacío.";
  }
  if (archivo.size > TAMANO_MAXIMO_BYTES) {
    return "El archivo supera el límite de 10 MB.";
  }
  return null;
}

// ----------------------------------------------------- §7 Revision (admin)
//
// El §7 lista las rutas y sus requisitos pero no los cuerpos, salvo el de
// `/revision`. Todo lo de abajo excepto `DecisionRevision` es INFERIDO a
// partir de lo que cada requisito del SRS necesita para poder ejecutarse.

// AD-01/AD-02/AD-03: la cola necesita, por trabajo, con que decidir a
// cual entrar primero.
export interface EntradaCola {
  trabajo_id: string;
  estado: EstadoTrabajo;
  /** `preview_onboarding` es la previsualizacion de un revisor, no un acudiente. */
  origen?: string;
  recibido_en: string;
  hijos: number;
  lineas_totales: number;
  lineas_pendientes: number;
  /** Ids de colegio: el nombre lo pone la consola con su directorio. */
  colegios: string[];
  grados: string[];
}

export interface ColaAdmin {
  entradas: EntradaCola[];
}

// AD-04: el detalle del trabajo en admin es el mismo `Trabajo` mas
// lo que la revision necesita y el acudiente no ve: por que cada linea esta
// pendiente y quien la toco.
export interface TrabajoAdmin extends Trabajo {
  recibido_en: string;
  contacto_id: string;
  lineas_pendientes: string[];
  nota_revision?: string | null;
  /** `preview_onboarding`/`canonico_lista` no tienen acudiente a quien avisar. */
  origen?: string;
  /** Los hijos tal como se pidieron; un preview trae su `version_id`. */
  hijos?: HijoDeTrabajo[];
}

export interface HijoDeTrabajo {
  referencia?: string;
  colegio_id?: string;
  grado?: string;
  anio_lectivo?: number;
  version_id?: string;
}

// AD-02: validar es fijar el producto de la linea. Sin `sku` se lee
// como "confirmo el que el sistema eligio".
export interface ValidarLinea {
  sku?: string;
  nota?: string;
}

// AD-02: una marca de "sin coincidencia" que no diga por que no se
// puede revisar despues.
export interface SinCoincidencia {
  motivo: string;
}

// AD-07: alta manual de producto con precio e imagen, que es lo que
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

// AD-05.
export interface MarcarNoDisponible {
  motivo: string;
}

// El unico cuerpo que el §7 si fija.
export interface DecisionRevision {
  decision: "aprobar" | "devolver";
  nota?: string;
}

// ------------------------------------------- Onboarding: percepcion cruda
//
// La evidencia que inteligencia dejo al importar una lista, tal como la sirve
// catalogo en `GET /v1/admin/listas/{version_id}/percepcion` (region 2 del
// revisor de cuatro paneles). Son dos cosas: lo CRUDO que ley el modelo por
// pagina (para poder cotejar contra el PDF original) y lo que se ITEMIZO de
// ahi. El item admite `texto_original` o `descripcion` porque el borde escribe
// `texto_original` pero la percepcion de inteligencia lo nombra `descripcion`;
// se aceptan ambos y `cantidad`/`confianza` pueden faltar (null) mientras la
// revision no los fije.
export interface PercepcionCruda {
  paginas: { pagina: number; crudo: string }[];
  items: {
    texto_original?: string;
    descripcion?: string;
    cantidad: number | null;
    confianza: number | null;
  }[];
}
