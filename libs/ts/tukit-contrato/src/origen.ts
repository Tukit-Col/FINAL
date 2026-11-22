// La frontera entre de dónde salen los datos y cómo se ven.
//
// Decisiones:
// - La implementación es el cliente HTTP contra el backend real, a través del gateway. Las pantallas
//   no lo tocan directo: piden el origen y lo usan, así que mantener este contrato estable las aísla
//   de cómo se habla con el backend.

import type {
  AcudienteResumen,
  AltaProducto,
  AplicarCanonico,
  CambioDeProducto,
  PerfilKit,
  Checkout,
  ColaAdmin,
  Contacto,
  DecisionRevision,
  BorradorKits,
  GradoCanonico,
  SolicitudCheckout,
  CambioDeDescarte,
  OpcionesDeLinea,
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
  TrabajoResumen,
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
  ColegioDesignado,
  ColegioDetalle,
  ColegioEditable,
  ColegioNuevoEditable,
  DatosColegioNuevo,
  DirectorioColegio,
  FiltrosListasAdmin,
  FiltrosProductos,
  ItemListaEditable,
  AvisoLista,
  ListaOficial,
  PaginaProductos,
  Personaje,
  ProductoCatalogo,
  ProductoCatalogoDetalle,
  ProductoEditable,
  PropuestaCola,
  PropuestaEncolada,
  RechazarPropuesta,
  RevisionLista,
  Sugerencia,
  VersionListaAdmin,
} from "./catalogo";
import type {
  Pedido,
  PedidoConHistorial,
  PedidoDelAcudiente,
  RetractoSolicitado,
  SolicitudAvancePedido,
  TableroComercio,
} from "./comercio";
import type { MetricasColegio, ResumenPedidosColegio, SerieMetricas } from "./metricas";
import type {
  BandejaCorreos,
  BandejaOperacion,
  FiltrosCorreos,
  Caso,
  CasoCreado,
  MiCaso,
  MiCasoDetalle,
  SolicitudCaso,
  SolicitudMiCaso,
} from "./operacion";
import type {
  AsignacionCaso,
  CasoDetalleAdmin,
  DestinoDeLote,
  PedidoAdmin,
  PrioridadCaso,
  RespuestaLote,
  RespuestaReconciliacion,
  SolicitudAvanceAdmin,
  VistaPreviaPedido,
} from "./admin";
import type { MisDatos, ResultadoSupresion } from "./privacidad";

export type Rol =
  | "acudiente"
  | "colegio_admin"
  | "colegio_docente"
  | "operador"
  | "admin";

export type AmbitoTipo = "global" | "colegio" | "sede" | "matricula";

export interface RolAsignado {
  rol: Rol;
  ambito: { tipo: AmbitoTipo; id: string | null };
}

export interface Sesion {
  usuario_id: string;
  correo: string;
  nombre: string;
  roles: RolAsignado[];
  version_permisos: number;
}

export interface Credenciales {
  correo: string;
  clave: string;
}

export interface NuevaCuenta extends Credenciales {
  nombre: string;
  celular?: string;
  acepta_terminos?: boolean;
}

export interface HijoNuevo {
  colegio_id: string;
  grado: string;
  apodo?: string;
}

export interface MatriculaAcudiente {
  matricula_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  apodo: string | null;
}

export interface RegistroAcudiente {
  correo: string;
  clave: string;
  celular?: string;
  hijos: HijoNuevo[];
  acepta_terminos?: boolean;
}

export interface HijoAcudiente {
  colegio_id: string;
  colegio_nombre: string;
  grado: string;
}

export interface AcudienteAdmin {
  usuario_id: string;
  correo: string;
  celular: string | null;
  creado_en: string;
  hijos: HijoAcudiente[];
}

export interface ArchivoLista {
  referencia: string;
  nombre: string;
  tipo: string;
  tamano: number;
  contenido: Blob;
}

export interface OrigenDatos {
  readonly nombre: "api";

  iniciarSesion(credenciales: Credenciales): Promise<{ sesion: Sesion; token: string }>;
  crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }>;
  sesionActual(token: string): Promise<Sesion | null>;
  cerrarSesion(token: string): Promise<void>;

  registrarAcudiente(datos: RegistroAcudiente): Promise<{ usuario_id: string; creado: boolean }>;
  matriculasDelAcudiente(token: string): Promise<MatriculaAcudiente[]>;

  guardarMatriculas(token: string, hijos: HijoNuevo[]): Promise<{ total: number }>;

  quitarMatricula(token: string, matriculaId: string): Promise<void>;
  cambiarMatricula(
    token: string,
    matriculaId: string,
    cambio: { colegio_id: string; grado: string; apodo?: string | null },
  ): Promise<{ total: number }>;

  cancelarSolicitud(token: string, trabajoId: string): Promise<{ trabajo_id: string; estado: string }>;
  cancelarListaSubida(token: string, tareaId: string): Promise<{ tarea_id: string; retiradas: number }>;

  acudientesAdmin(token: string, ids?: string[]): Promise<AcudienteAdmin[]>;

  crearTrabajo(
    solicitud: SolicitudTrabajo,
    archivos?: ArchivoLista[],
    token?: string,
  ): Promise<TrabajoCreado>;
  consultarTrabajo(trabajoId: string, token?: string): Promise<Trabajo>;

  subirListas(
    hijos: HijoSubida[],
    archivos: ArchivoLista[],
    contacto?: Contacto,
    preferencias?: Preferencias,
    token?: string,
  ): Promise<SubidaListas>;

  catalogo(): Promise<Catalogo>;
  colegios(): Promise<Colegio[]>;
  listaOficial(colegioId: string, grado: string): Promise<ListaOficial>;

  personajes(): Promise<Personaje[]>;
  buscarProductos(filtros: FiltrosProductos): Promise<PaginaProductos>;
  editarProducto(sku: string, cambios: ProductoEditable): Promise<ProductoCatalogoDetalle>;
  reclasificarProducto(sku: string, concepto: string): Promise<ProductoCatalogoDetalle>;
  eliminarProducto(sku: string): Promise<void>;

  colaPropuestas(concepto?: string): Promise<PropuestaCola[]>;
  buscarEnTienda(slug: string, consulta: string, cuantos?: number): Promise<CandidatoTienda[]>;
  crearConcepto(cuerpo: CrearConcepto): Promise<ConceptoCreado>;
  altaUtil(cuerpo: AltaUtil): Promise<PropuestaEncolada>;
  altaUtilManual(cuerpo: AltaUtilManual): Promise<PropuestaEncolada>;
  altaLibro(cuerpo: AltaLibro): Promise<PropuestaEncolada>;
  aprobarPropuesta(id: string, cuerpo: AprobarPropuesta): Promise<{ id: string; estado: string }>;
  rechazarPropuesta(
    id: string,
    cuerpo: RechazarPropuesta,
  ): Promise<{ id: string; estado: string }>;

  gradosCanonicos(colegioId?: string): Promise<GradoCanonico[]>;
  aplicarCanonico(cuerpo: AplicarCanonico, token?: string): Promise<TrabajoAplicado>;

  iniciarCheckout(trabajoId: string, cuerpo: SolicitudCheckout, token?: string): Promise<Checkout>;

  cambiarProductoDeKit(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    sku: string,
    token?: string,
  ): Promise<CambioDeProducto>;

  descartarLineaDeKit(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    descartado: boolean,
    token?: string,
  ): Promise<CambioDeDescarte>;
  opcionesDeLinea(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    token?: string,
  ): Promise<OpcionesDeLinea>;

  sincronizarPago(transaccionId: string): Promise<ResultadoPago>;
  miPedido(token: string, pedidoId: string): Promise<PedidoDelAcudiente>;
  iniciarPagoPedido(
    token: string,
    pedidoId: string,
    cuerpo: { correo_cliente: string; url_redireccion?: string },
  ): Promise<PagoIniciado>;
  cancelarPedido(token: string, pedidoId: string): Promise<Pedido>;
  retractarPedido(token: string, pedidoId: string, motivo: string): Promise<RetractoSolicitado>;

  misDatos(token: string): Promise<MisDatos>;
  exportarMisDatos(token: string): Promise<{ contenido: string; nombreArchivo: string }>;
  suprimirMisDatos(token: string, confirmacion: string): Promise<ResultadoSupresion>;
  revocarConsentimientos(token: string): Promise<{ revocados: number }>;

  misCasos(token: string): Promise<MiCaso[]>;
  miCaso(token: string, casoId: string): Promise<MiCasoDetalle>;
  abrirMiCaso(token: string, solicitud: SolicitudMiCaso): Promise<CasoCreado>;
  comentarMiCaso(token: string, casoId: string, texto: string): Promise<void>;

  cola(): Promise<ColaAdmin>;
  trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin>;
  acudientesDeColegio(colegioId: string): Promise<AcudienteResumen[]>;
  nombresDeUsuarios(ids: string[], token: string): Promise<Record<string, string>>;
  validarLinea(trabajoId: string, itemId: string, cuerpo: ValidarLinea): Promise<void>;
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
  fijarCanonico(trabajoId: string, cuerpo: { nota?: string }): Promise<void>;
  abrirBorradorKits(trabajoId: string): Promise<BorradorKits>;
  eliminarTrabajo(trabajoId: string): Promise<void>;

  onboarding(
    token: string,
    colegio: string | ColegioDesignado,
    grado: string,
    anio_lectivo: number,
    archivo: { contenido: Blob; nombre: string },
  ): Promise<{ version_id: string; grado: string; items: number }>;
  documento(versionId: string): Promise<Blob | ArrayBuffer | string>;
  percepcion(versionId: string): Promise<PercepcionCruda>;

  sugerirColegio(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo?: { contenido: Blob; nombre: string },
    contacto_referencia?: string,
  ): Promise<{ tarea_id: string; estado: string }>;

  listasAdmin(filtros?: FiltrosListasAdmin): Promise<VersionListaAdmin[]>;
  revisionLista(versionId: string): Promise<RevisionLista>;
  editarItemLista(
    versionId: string,
    itemId: string,
    cambios: ItemListaEditable,
  ): Promise<void>;
  agregarItemLista(versionId: string, item: ItemListaEditable): Promise<{ item_id: string }>;
  quitarItemLista(versionId: string, itemId: string): Promise<void>;
  eliminarVersionLista(versionId: string): Promise<void>;
  cerrarLista(versionId: string): Promise<void>;
  nuevaVersion(
    colegioId: string,
    grado: string,
    anioLectivo: number,
  ): Promise<{ version_id: string }>;

  avisosLista(versionId: string): Promise<AvisoLista[]>;
  descartarAviso(versionId: string, itemId: string, clave: string): Promise<void>;
  noComprarRepetido(versionId: string, itemId: string, repiteA: number): Promise<{ version_id: string }>;

  completarColegioDeVersion(
    versionId: string,
    cambios: ColegioNuevoEditable,
  ): Promise<DatosColegioNuevo>;

  directorioColegio(dane: string): Promise<DatosColegioNuevo | null>;

  directorioCompleto(dane: string): Promise<DirectorioColegio | null>;

  colegio(colegioId: string): Promise<ColegioDetalle>;
  editarColegio(colegioId: string, cambios: ColegioEditable): Promise<ColegioDetalle>;

  previewDeVersion(
    versionId: string,
    ctx: { colegioId: string; grado: string; anioLectivo: number },
  ): Promise<{ trabajo_id: string }>;

  sugerencias(): Promise<Sugerencia[]>;

  pedidos(token: string): Promise<TableroComercio>;
  pedido(token: string, pedidoId: string): Promise<PedidoConHistorial>;
  avanzarPedido(
    token: string,
    pedidoId: string,
    cuerpo: SolicitudAvancePedido,
  ): Promise<PedidoConHistorial>;

  misPedidos(token: string): Promise<Pedido[]>;

  misTrabajos(token?: string): Promise<TrabajoResumen[]>;

  misSolicitudes(token: string): Promise<MisSolicitudes>;

  casos(token?: string, usuarioId?: string): Promise<BandejaOperacion>;
  caso(casoId: string, token?: string): Promise<Caso>;
  correos(token: string, filtros?: FiltrosCorreos): Promise<BandejaCorreos>;

  pedidoAdmin(token: string, pedidoId: string): Promise<PedidoAdmin>;
  avanzarPedidoAdmin(token: string, pedidoId: string, cuerpo: SolicitudAvanceAdmin): Promise<PedidoAdmin>;
  casoAdmin(token: string, casoId: string): Promise<CasoDetalleAdmin>;
  responderCaso(token: string, casoId: string, texto: string): Promise<CasoDetalleAdmin>;
  cambiarEstadoCaso(token: string, casoId: string, destino: string): Promise<CasoDetalleAdmin>;
  vincularPedidoCaso(token: string, casoId: string, pedidoId: string): Promise<CasoDetalleAdmin>;
  reconciliarPagoPedido(token: string, pedidoId: string): Promise<RespuestaReconciliacion>;
  vistaPreviaPedido(token: string, pedidoId: string, destino: string): Promise<VistaPreviaPedido>;
  avanzarLote(
    token: string,
    cuerpo: { pedido_ids: string[]; destino: DestinoDeLote },
  ): Promise<RespuestaLote>;
  asignarCaso(token: string, casoId: string, asignar: AsignacionCaso): Promise<CasoDetalleAdmin>;
  cambiarPrioridadCaso(token: string, casoId: string, prioridad: PrioridadCaso): Promise<CasoDetalleAdmin>;
  notaInternaCaso(token: string, casoId: string, texto: string): Promise<CasoDetalleAdmin>;
  productoPublico(sku: string): Promise<ProductoCatalogo | null>;

  crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado>;

  metricasColegio(colegioId: string): Promise<MetricasColegio>;

  resumenPedidosColegio(token: string, colegioId: string): Promise<ResumenPedidosColegio>;

  metricasSerie(filtros?: {
    dimension?: "catalogo" | "colegio" | "global";
    dimensionId?: string;
    desde?: string;
  }): Promise<SerieMetricas>;
}

export function destinoDe(sesion: Sesion): { app: "web" | "colegio" | "admin"; ruta: string } {
  const roles = new Set(sesion.roles.map((r) => r.rol));
  if (roles.has("admin") || roles.has("operador")) return { app: "admin", ruta: "/" };
  if (roles.has("colegio_admin") || roles.has("colegio_docente"))
    return { app: "colegio", ruta: "/portal" };
  return { app: "web", ruta: "/dashboard" };
}

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
