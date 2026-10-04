// La frontera entre "de donde salen los datos" y "como se ven".
//
// La implementacion es el cliente HTTP contra el backend real (los 7
// microservicios a traves del gateway). Las pantallas no lo tocan directo:
// piden el origen y lo usan, y por eso mantener este contrato estable las aisla
// de como se hable con el backend.
//
// La interfaz esta partida en tres a proposito. `catalogo`, `colegios` y
// `listaOficial` son la parte ASUMIDA (ver `catalogo.ts`): si la 1.1 del
// contrato llega distinta, lo que hay que reescribir son tres metodos y no
// el cliente entero.

import type {
  AltaProducto,
  AplicarCanonico,
  CambioDeProducto,
  PerfilKit,
  Checkout,
  ColaAdmin,
  Contacto,
  DecisionRevision,
  GradoCanonico,
  SolicitudCheckout,
  HijoSubida,
  MarcarNoDisponible,
  MisSolicitudes,
  PercepcionCruda,
  Preferencias,
  PagoIniciado,
  ResultadoPago,
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
  DirectorioColegio,
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
import type { MetricasColegio, ResumenPedidosColegio, SerieMetricas } from "./metricas";
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

/** Un hijo tal como lo manda el formulario: colegio y grado bastan para armar el
 *  kit; el `apodo` es opcional y es lo unico del menor que viaja (identidad lo
 *  cifra), jamas el nombre legal, por minimizacion (Ley 1581 de 2012, Art. 4). Lo
 *  usan el alta nueva (`RegistroAcudiente`) y el guardado con sesion. */
export interface HijoNuevo {
  colegio_id: string;
  grado: string;
  apodo?: string;
}

/** El ambito de tenencia de UN hijo del portador, tal como lo devuelve
 *  `GET /v1/cuenta/matriculas`. Es lo justo para precargar `/empezar` sin
 *  re-teclear: colegio, grado y el `apodo` (descifrado por identidad, o `null`).
 *  El apodo SI baja porque el PADRE puede ver el de SUS hijos —es el portador del
 *  token—, pero sigue sin traer nombre legal, documento ni `estudiante_id`. */
export interface MatriculaAcudiente {
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  apodo: string | null;
}

/** El alta del acudiente nuevo (camino "soy nuevo usuario"): su credencial, el
 *  celular para el aviso y sus hijos. Del menor solo viaja un `apodo` opcional
 *  —jamas el nombre legal, por minimizacion (Ley 1581 de 2012, Art. 4)—, que
 *  identidad guarda cifrado. */
export interface RegistroAcudiente {
  correo: string;
  clave: string;
  celular?: string;
  hijos: HijoNuevo[];
}

/** Un hijo de un acudiente tal como lo devuelve el padron interno
 *  (`GET /v1/admin/acudientes`). Del menor SOLO viaja el apodo (descifrado por
 *  identidad, o `null` si no tiene) y el ambito de la matricula: nunca nombre
 *  legal, documento ni `estudiante_id`. */
export interface HijoAcudiente {
  apodo: string | null;
  colegio_id: string;
  colegio_nombre: string;
  grado: string;
}

/** Una familia registrada, tal como la ve el equipo interno en el padron
 *  (`GET /v1/admin/acudientes`, solo admin/operador). El minimo para operar y
 *  para que metricas resuelva `usuario_id -> cliente`: nunca clave, documento,
 *  fecha de nacimiento ni nombre legal. */
export interface AcudienteAdmin {
  usuario_id: string;
  correo: string;
  celular: string | null;
  creado_en: string;
  hijos: HijoAcudiente[];
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
  readonly nombre: "api";

  // §Identidad — autenticacion y sesion (identidad, ADR 0013).
  //
  // El token es opaco al contrato: es lo que emite identidad/gateway.
  // `iniciarSesion` devuelve la Sesion, y quien llama (un Route Handler) es
  // quien pone la cookie: el origen no toca cookies, igual que el resto de la
  // interfaz no sabe de HTTP.
  iniciarSesion(credenciales: Credenciales): Promise<{ sesion: Sesion; token: string }>;
  sesionActual(token: string): Promise<Sesion | null>;
  cerrarSesion(token: string): Promise<void>;

  // §Identidad — registro y tenencia del acudiente.
  //
  // `registrarAcudiente` es el alta del camino "soy nuevo usuario": crea la
  // cuenta con credencial usable y persiste las matriculas de sus hijos. No
  // asigna rol (minimo, igual que el contacto): la sesion vale y `destinoDe`
  // cae al destino web por defecto. `matriculasDelAcudiente` lee la tenencia
  // del PROPIO portador del token, para que quien vuelve a `/empezar` con
  // sesion no re-teclee a sus hijos; nunca devuelve datos de menor.
  registrarAcudiente(datos: RegistroAcudiente): Promise<{ usuario_id: string; creado: boolean }>;
  matriculasDelAcudiente(token: string): Promise<MatriculaAcudiente[]>;

  // `guardarMatriculas` es el equivalente autenticado del alta de hijos de
  // `registrarAcudiente` (camino "ya tengo cuenta"): el PORTADOR del token agrega
  // a sus propios hijos sin re-registrar la cuenta. Bearer; idempotente; solo
  // escribe tenencia del portador. Devuelve cuantas materializo.
  guardarMatriculas(token: string, hijos: HijoNuevo[]): Promise<{ total: number }>;

  // §Identidad — padron de acudientes para el equipo interno. Solo admin/
  // operador (identidad gatea: 401 sin token, 403 sin rol). Devuelve las
  // familias registradas con sus hijos; `ids` (opcional) acota a esos usuarios
  // sin relajar el filtro. El token viaja como `Authorization: Bearer`.
  acudientesAdmin(token: string, ids?: string[]): Promise<AcudienteAdmin[]>;

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

  // El acudiente cambia un producto de un kit publicado por el sugerido o una
  // de sus alternativas. `token` es su sesión: si el trabajo tiene dueño, el
  // backend exige que sea la suya.
  cambiarProductoDeKit(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    sku: string,
    token?: string,
  ): Promise<CambioDeProducto>;

  // §Pago — al regreso de la pasarela, sincroniza la transaccion con Wompi y
  // devuelve el estado del pago y del pedido (idempotente).
  sincronizarPago(transaccionId: string): Promise<ResultadoPago>;
  // Un intento de pago nuevo sobre un pedido pendiente (Comercio congela el
  // precio al crear el pedido; aqui no se re-arma la orden).
  iniciarPagoPedido(
    pedidoId: string,
    cuerpo: { correo_cliente: string; url_redireccion?: string },
  ): Promise<PagoIniciado>;
  // Cancela un pedido pendiente. Comercio pregunta antes a Wompi: con un pago
  // aprobado o en curso responde 409 y no cancela.
  cancelarPedido(pedidoId: string): Promise<Pedido>;

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
  // Fija un preview (sin acudiente) como los kits canonicos de su grado: no
  // avisa a nadie. Aprobar la LISTA es aparte (`cerrarLista`).
  fijarCanonico(trabajoId: string, cuerpo: { nota?: string }): Promise<void>;
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
  // Saca de la cola una version SIN revisar (y su PDF). Una revisada responde
  // 409 `lista_ya_revisada`: es la que ve el acudiente.
  eliminarVersionLista(versionId: string): Promise<void>;
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

  // La ficha COMPLETA del directorio DUEB (mismo `GET /v1/directorio/{dane}`),
  // con sector, localidad, rector y las listas de telefonos/correos, para el
  // detalle del colegio en el admin. `null` con el mismo 404 que el anterior.
  directorioCompleto(dane: string): Promise<DirectorioColegio | null>;

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

  // "Mis solicitudes" del panel del acudiente: sus listas subidas + sus
  // trabajos, unidas (`GET /v1/mis-solicitudes` en inteligencia). Viaja el
  // token, no el `usuario_id`: el backend saca la identidad de la sesion que
  // valida, para que el navegador nunca elija de quien pedir las solicitudes.
  misSolicitudes(token: string): Promise<MisSolicitudes>;

  // ASUMIDO — superficie de lectura de `operacion` (tickets del back-office).
  // Ver `operacion.ts`.
  casos(): Promise<BandejaOperacion>;
  caso(casoId: string): Promise<Caso>;

  // ASUMIDO — superficie de ESCRITURA de `operacion`: abrir un caso/PQRS desde
  // el centro de ayuda del acudiente (ADR 0004). El backend lo sirve en
  // `POST /v1/operacion/casos`.
  crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado>;

  // §Metricas — las dos caras de la calidad del algoritmo, para el panel del
  // operador. `metricasColegio` es la medida EN VIVO de un colegio
  // (Inteligencia, `GET /v1/metricas/colegios/{id}`): cobertura y ahorro de hoy.
  // `metricasSerie` es la traza CONGELADA por dia (Operacion,
  // `GET /v1/operacion/metricas`), que `make instantanea-metricas` va llenando
  // sesion a sesion; los filtros acotan por dimension/colegio y por fecha minima.
  metricasColegio(colegioId: string): Promise<MetricasColegio>;

  // §Metricas de pedidos — el cruce `pedido pagado -> trabajo -> hijos -> padre`
  // de un colegio (Inteligencia, `GET /v1/metricas/colegios/{id}/pedidos`).
  // Exige Bearer de operador/admin (misma semantica que `acudientesAdmin`): la
  // respuesta lista los `usuario_id` de los padres que pagaron, que es dato
  // sensible aunque no sea correo. El correo de cada padre lo resuelve el
  // servidor del admin con `acudientesAdmin`, pasando estos `usuario_id`.
  resumenPedidosColegio(token: string, colegioId: string): Promise<ResumenPedidosColegio>;

  metricasSerie(filtros?: {
    dimension?: "catalogo" | "colegio" | "global";
    dimensionId?: string;
    desde?: string;
  }): Promise<SerieMetricas>;
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
