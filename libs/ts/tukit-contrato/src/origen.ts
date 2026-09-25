// La frontera entre "de donde salen los datos" y "como se ven".
//
// Hay dos implementaciones: el cliente HTTP contra el backend real y el origen
// simulado que lee las semillas del repositorio. Las pantallas no saben cual
// tienen delante, y por eso el dia que el backend responda no hay que tocar
// ninguna: se cambia una variable de entorno.
//
// La interfaz esta partida en tres a proposito. `catalogo`, `colegios` y
// `listaOficial` son la parte ASUMIDA (ver `catalogo.ts`): si la 1.1 del
// contrato llega distinta, lo que hay que reescribir son tres metodos y no
// el cliente entero.

import type {
  AltaProducto,
  AplicarCanonico,
  Checkout,
  ColaAdmin,
  Contacto,
  DecisionRevision,
  GradoCanonico,
  SolicitudCheckout,
  HijoSubida,
  MarcarNoDisponible,
  PercepcionCruda,
  Preferencias,
  ProductoDadoDeAlta,
  SinCoincidencia,
  SolicitudTrabajo,
  SubidaListas,
  Trabajo,
  TrabajoAdmin,
  TrabajoAplicado,
  TrabajoCreado,
  ValidarLinea,
} from "./contrato";
import type {
  AltaLibro,
  AltaUtil,
  ConceptoCreado,
  CrearConcepto,
  AltaUtilManual,
  AprobarPropuesta,
  CandidatoTienda,
  Catalogo,
  Colegio,
  ColegioDetalle,
  ColegioEditable,
  ColegioNuevoEditable,
  DatosColegioNuevo,
  FiltrosListasAdmin,
  FiltrosProductos,
  ItemListaEditable,
  ListaOficial,
  PaginaProductos,
  Personaje,
  ProductoCatalogoDetalle,
  ProductoEditable,
  PropuestaCola,
  PropuestaEncolada,
  RechazarPropuesta,
  RevisionLista,
  Sugerencia,
  VersionListaAdmin,
} from "./catalogo";
import type { Pedido, TableroComercio } from "./comercio";
import type { BandejaOperacion, Caso, CasoCreado, SolicitudCaso } from "./operacion";

/** Los roles del sistema (filas de `rol` en identidad, ADR 0013). No es un
 *  enum del dominio: el codigo pregunta `puede(...)`, nunca `if rol in (...)`.
 *  Se listan aqui solo para que la UI enrute por rol sin decidir las reglas. */
export type Rol =
  | "acudiente"
  | "colegio_admin"
  | "colegio_docente"
  | "operador"
  | "admin";

/** El tipo de ambito sobre el que se concede un rol (base.py `AmbitoTipo`). */
export type AmbitoTipo = "global" | "colegio" | "sede" | "matricula";

/** Un rol vigente sobre un ambito, tal como lo resuelve identidad. El `id` es
 *  nulo SOLO para el ambito global, misma regla que `asignacion_ambito_coherente`. */
export interface RolAsignado {
  rol: Rol;
  ambito: { tipo: AmbitoTipo; id: string | null };
}

/** Quien es quien pregunta. Lleva el correo propio (para saludar) y nunca el
 *  de nadie mas ni el nombre de un menor: identidad referencia por
 *  identificador (§12.4). */
export interface Sesion {
  usuario_id: string;
  correo: string;
  nombre: string;
  roles: RolAsignado[];
  // Lo que el gateway compara para revocar la sesion (§1).
  version_permisos: number;
}

/** Lo minimo para autenticar. La clave es opaca al contrato. */
export interface Credenciales {
  correo: string;
  clave: string;
}

/** Un archivo de lista, ya leido, con el hijo al que pertenece. */
export interface ArchivoLista {
  referencia: string;
  nombre: string;
  tipo: string;
  tamano: number;
  contenido: Blob;
}

export interface OrigenDatos {
  readonly nombre: "api" | "simulado";

  // §Identidad — autenticacion y sesion (identidad, ADR 0013).
  //
  // El token es opaco al contrato: en `api` es lo que emite identidad/gateway;
  // en `simulado` es un sello base64 sin firma. `iniciarSesion` devuelve la
  // Sesion, y quien llama (un Route Handler) es quien pone la cookie: el origen
  // no toca cookies, igual que el resto de la interfaz no sabe de HTTP.
  iniciarSesion(credenciales: Credenciales): Promise<{ sesion: Sesion; token: string }>;
  sesionActual(token: string): Promise<Sesion | null>;
  cerrarSesion(token: string): Promise<void>;

  // §2 y §4 — el ciclo asincrono.
  crearTrabajo(solicitud: SolicitudTrabajo, archivos?: ArchivoLista[]): Promise<TrabajoCreado>;
  consultarTrabajo(trabajoId: string): Promise<Trabajo>;

  // §2 — la subida de listas de un acudiente (`POST /v1/listas/subir`). Percibe
  // el PDF de cada hijo y lo importa como una version PENDIENTE, ligada al padre
  // por su `contacto_referencia`. NO crea un trabajo: el padre espera la
  // verificacion. El origen no sabe de HTTP, asi que recibe los archivos ya
  // leidos (`ArchivoLista`) igual que `crearTrabajo`. El contacto viaja para
  // que Identidad lo registre una vez; su correo/telefono nunca se guardan aca.
  subirListas(
    hijos: HijoSubida[],
    archivos: ArchivoLista[],
    contacto?: Contacto,
    preferencias?: Preferencias,
  ): Promise<SubidaListas>;

  // ASUMIDO — superficie de lectura de catalogo (1.1).
  catalogo(): Promise<Catalogo>;
  colegios(): Promise<Colegio[]>;
  listaOficial(colegioId: string, grado: string): Promise<ListaOficial>;

  // §Catalogo (P4c) — la SPA de administracion del catalogo. `personajes`
  // deriva la lista de franquicias con su conteo; `buscarProductos` es la
  // busqueda paginada con filtros; los tres verbos de escritura editan, mueven
  // de concepto y dan de baja (borrado suave) un producto. Todos responden con
  // la forma de detalle (`_producto_publico`) para que el formulario re-pinte
  // sin una segunda lectura. Igual que el resto de catalogo, es ASUMIDO (1.1):
  // el backend lo esta construyendo en paralelo con estas mismas claves.
  personajes(): Promise<Personaje[]>;
  buscarProductos(filtros: FiltrosProductos): Promise<PaginaProductos>;
  editarProducto(sku: string, cambios: ProductoEditable): Promise<ProductoCatalogoDetalle>;
  reclasificarProducto(sku: string, concepto: string): Promise<ProductoCatalogoDetalle>;
  eliminarProducto(sku: string): Promise<void>;

  // §Catalogo (P4c bis) — curaduria PROACTIVA del catalogo. Distinta de la
  // revision de listas de colegio (`cola`/`revisionLista`): aqui el personal
  // llena huecos del catalogo antes de que un acudiente pregunte. `colaPropuestas`
  // lista los candidatos pendientes; `buscarEnTienda` envuelve la busqueda en
  // vivo (VTEX/Shopify) para el alta de utiles; `altaUtil`/`altaLibro` ENCOLAN
  // (no aprueban: la propuesta cae en la cola visible y una persona decide el
  // nivel al aprobar); `aprobarPropuesta`/`rechazarPropuesta` cierran la cola.
  // El rechazo reusa la ruta ya existente `POST /v1/admin/propuestas/{id}/rechazar`.
  colaPropuestas(concepto?: string): Promise<PropuestaCola[]>;
  buscarEnTienda(slug: string, consulta: string, cuantos?: number): Promise<CandidatoTienda[]>;
  // Crea un concepto nuevo (el codigo lo autogenera el backend). Es el otro
  // brazo de la curacion: nace el concepto y despues se le encolan sus niveles.
  crearConcepto(cuerpo: CrearConcepto): Promise<ConceptoCreado>;
  altaUtil(cuerpo: AltaUtil): Promise<PropuestaEncolada>;
  altaUtilManual(cuerpo: AltaUtilManual): Promise<PropuestaEncolada>;
  altaLibro(cuerpo: AltaLibro): Promise<PropuestaEncolada>;
  aprobarPropuesta(id: string, cuerpo: AprobarPropuesta): Promise<{ id: string; estado: string }>;
  rechazarPropuesta(
    id: string,
    cuerpo: RechazarPropuesta,
  ): Promise<{ id: string; estado: string }>;

  // §Ruta rapida del acudiente — un (colegio, grado) YA publicado es la cache
  // bendita: `gradosCanonicos` lista lo que tiene cache (para elegir en vez de
  // subir PDF) y `aplicarCanonico` aplica el nivel + personaje sin re-optimizar
  // ni entrar a la cola, dejando el pedido congelado para comercio.
  gradosCanonicos(colegioId?: string): Promise<GradoCanonico[]>;
  aplicarCanonico(cuerpo: AplicarCanonico): Promise<TrabajoAplicado>;

  // §Checkout — el acudiente paga el kit de un trabajo publicado. Manda solo
  // perfil + correo + direccion; Inteligencia arma la orden en Comercio y
  // devuelve la url de la pasarela a la que redirigir. No expone ids de base.
  iniciarCheckout(trabajoId: string, cuerpo: SolicitudCheckout): Promise<Checkout>;

  // §7 — revision humana.
  cola(): Promise<ColaAdmin>;
  trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin>;
  validarLinea(trabajoId: string, itemId: string, cuerpo: ValidarLinea): Promise<void>;
  // Fija el producto de UN kit (por-nivel): escribe LINEA, no RESOLUCION, y
  // recalcula el subtotal. A diferencia de `validarLinea` (que confirma el item
  // en los tres kits) esto cambia el producto de un solo perfil.
  fijarProductoLinea(
    trabajoId: string,
    perfil: string,
    itemId: string,
    sku: string,
  ): Promise<void>;
  marcarSinCoincidencia(
    trabajoId: string,
    itemId: string,
    cuerpo: SinCoincidencia,
  ): Promise<void>;
  altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta>;
  marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void>;
  decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void>;
  // Borra un trabajo desechable (preview, encolado, fallido). Un `publicado`
  // esta protegido y el backend responde 409.
  eliminarTrabajo(trabajoId: string): Promise<void>;

  // §Onboarding — inteligencia recibe el PDF de un grado, lo percibe y lo
  // vuelca en catalogo como una version de lista importada (P2). El gateway
  // expone `POST /v1/admin/onboarding` (multipart); el origen no sabe de HTTP,
  // asi que recibe el archivo ya leido (`{contenido, nombre}`) como
  // `crearTrabajo`. Devuelve lo justo para llevar al revisor a la version que
  // se acaba de crear. Los dos GET sirven la evidencia de esa version:
  // `documento` el PDF crudo (region 1), `percepcion` lo que el modelo ley
  // por pagina mas lo itemizado (region 2). Las rutas de edicion/aprobacion de
  // P1 NO viven aqui: son un eslabon aparte.
  onboarding(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo: { contenido: Blob; nombre: string },
  ): Promise<{ version_id: string; grado: string; items: number }>;
  documento(versionId: string): Promise<Blob | ArrayBuffer | string>;
  percepcion(versionId: string): Promise<PercepcionCruda>;

  // §Sugerencia — un acudiente cuyo (colegio, grado) no tiene lista verificada
  // sugiere la suya al backlog del administrador (P3c). El gateway expone
  // `POST /v1/admin/sugerencias` hacia catalogo, que crea una tarea de
  // importacion 'pendiente' con origen 'sugerencia_padre'. La traza al
  // acudiente es SOLO `contacto_referencia` (el usuario_id que identidad emite);
  // el correo y el telefono nunca cruzan aqui —viven solo en identidad. El
  // archivo llega ya leido (`{contenido, nombre}`), igual que en `onboarding`,
  // porque el origen no sabe de HTTP. Es una semilla para P4b: la rama visual
  // la arma esa fase, esto es el asiento del contrato.
  sugerirColegio(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo?: { contenido: Blob; nombre: string },
    contacto_referencia?: string,
  ): Promise<{ tarea_id: string; estado: string }>;

  // §Admin — revision y edicion de listas (P4). La superficie de escritura que
  // el `admin_http.py` de catalogo ya sirve bajo `/v1/admin`, mas dos rutas que
  // un slice de backend construye en paralelo (`PATCH /v1/colegios/{id}` y
  // `GET /v1/admin/sugerencias`). `listasAdmin` es el indice de versiones a
  // curar; `revisionLista` la vista de cuatro regiones (renglones + propuestas).
  // `editar/agregar` solo valen sobre una version SIN revisar (el backend alza
  // 409 `lista_ya_revisada` si no); `cerrar` aprueba; `nuevaVersion` clona la
  // vigente en una nueva sin revisar para corregir una lista ya publicada.
  listasAdmin(filtros?: FiltrosListasAdmin): Promise<VersionListaAdmin[]>;
  revisionLista(versionId: string): Promise<RevisionLista>;
  editarItemLista(
    versionId: string,
    itemId: string,
    cambios: ItemListaEditable,
  ): Promise<void>;
  agregarItemLista(versionId: string, item: ItemListaEditable): Promise<{ item_id: string }>;
  quitarItemLista(versionId: string, itemId: string): Promise<void>;
  cerrarLista(versionId: string): Promise<void>;
  nuevaVersion(
    colegioId: string,
    grado: string,
    anioLectivo: number,
  ): Promise<{ version_id: string }>;

  // Completar el perfil del colegio NUEVO de una version antes de aprobarla,
  // para que se de de alta completo (logo, direccion, contacto...) y no solo
  // con nombre y grado. Manda el `PATCH /v1/admin/listas/{version_id}/colegio`
  // (solo los campos presentes; el backend hace merge sobre `colegio_datos`) y
  // devuelve los datos ya combinados. Solo vale sobre una version SIN revisar y
  // con un colegio nuevo por crear (el backend alza 409 si no).
  completarColegioDeVersion(
    versionId: string,
    cambios: ColegioNuevoEditable,
  ): Promise<DatosColegioNuevo>;

  // El bloque DUEB de un colegio del directorio de Bogota (`GET
  // /v1/directorio/{dane}`), para pre-llenar el perfil del colegio nuevo de una
  // version cuando la subida solo dejo el nombre. `null` si el DANE no esta en
  // el directorio (colegio de otra ciudad o escrito a mano): quien llama degrada
  // a solo nombre+dane.
  directorioColegio(dane: string): Promise<DatosColegioNuevo | null>;

  // El detalle de un colegio y la edicion de su identidad. `colegio` lee
  // `GET /v1/colegios/{id}`; `editarColegio` manda el `PATCH /v1/colegios/{id}`
  // (solo los campos presentes) y devuelve el colegio ya actualizado.
  colegio(colegioId: string): Promise<ColegioDetalle>;
  editarColegio(colegioId: string, cambios: ColegioEditable): Promise<ColegioDetalle>;

  // §Admin — vista previa de una version (region 4). El administrador, parado
  // sobre una version curada, pide los tres kits que saldrian de ella sin crear
  // un trabajo de acudiente: se arma un trabajo de preview para ese
  // (colegio, grado) y se devuelve su `trabajo_id`. La pantalla lee luego el
  // `trabajoAdmin(trabajo_id)` de siempre para pintar los 3 kits. El gateway
  // sirve `POST /v1/admin/onboarding/{version_id}/preview`; el origen no sabe
  // de HTTP, asi que recibe el destino ya resuelto en `ctx`.
  previewDeVersion(
    versionId: string,
    ctx: { colegioId: string; grado: string; anioLectivo: number },
  ): Promise<{ trabajo_id: string }>;

  // El backlog de sugerencias de padres, con la UNICA traza permitida
  // (`contacto_referencia`): nunca correo ni telefono.
  sugerencias(): Promise<Sugerencia[]>;

  // ASUMIDO — superficie de lectura de `comercio` (logistica del back-office).
  // Ver `comercio.ts`: el contrato v1.0 aun no publica esto.
  pedidos(): Promise<TableroComercio>;
  pedido(pedidoId: string): Promise<Pedido>;

  // El historial de UN acudiente, para su panel (`/v1/comercio/mis-pedidos`).
  // A diferencia de `pedidos()` (el tablero de logistica, TODOS los pedidos),
  // esto filtra por el `usuario_id` del portador de la sesion —que quien llama
  // resuelve antes con `sesionActual`—, no por token: comercio no puede validar
  // la sesion de identidad sin cruzar la frontera (regla 1). Devuelve la lista
  // sin resumen; el dashboard no lo necesita.
  misPedidos(usuarioId: string): Promise<Pedido[]>;

  // ASUMIDO — superficie de lectura de `operacion` (tickets del back-office).
  // Ver `operacion.ts`.
  casos(): Promise<BandejaOperacion>;
  caso(casoId: string): Promise<Caso>;

  // ASUMIDO — superficie de ESCRITURA de `operacion`: abrir un caso/PQRS desde
  // el centro de ayuda del acudiente (ADR 0004). El backend real lo servira en
  // `POST /v1/operacion/casos`; hoy lo atiende el simulado.
  crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado>;
}

/** A donde mandar a alguien despues de entrar, segun sus roles (ADR 0008: tres
 *  apps por rol — web=acudiente, colegio=B2B, admin=personal interno).
 *
 *  La regla vive en UN solo sitio, no en los componentes, igual que el resto
 *  del contrato: "las pantallas no deciden reglas". Precedencia: el equipo
 *  interno gana sobre el colegio y este sobre el acudiente, porque a alguien de
 *  Tukit se le podria sembrar tambien un rol menor. `app` es logico; quien
 *  llama resuelve el origen concreto (:3001, etc.) sin hardcodearlo aqui. */
export function destinoDe(sesion: Sesion): { app: "web" | "colegio" | "admin"; ruta: string } {
  const roles = new Set(sesion.roles.map((r) => r.rol));
  if (roles.has("admin") || roles.has("operador")) return { app: "admin", ruta: "/" };
  if (roles.has("colegio_admin") || roles.has("colegio_docente"))
    return { app: "colegio", ruta: "/portal" };
  return { app: "web", ruta: "/dashboard" };
}

/** Error de dominio con la forma del §11, para que la UI no invente mensajes. */
export class ErrorTukit extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "ErrorTukit";
  }
}
