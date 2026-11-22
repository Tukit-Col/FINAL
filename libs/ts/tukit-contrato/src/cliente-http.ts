import { GRADOS_CANONICOS } from "./contrato";
import { conEspera } from "./espera";
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
  EstadoTrabajo,
  BorradorKits,
  GradoCanonico,
  SolicitudCheckout,
  CambioDeDescarte,
  OpcionesDeLinea,
  HijoSubida,
  Kit,
  LineaKit,
  MarcarNoDisponible,
  MisSolicitudes,
  PercepcionCruda,
  Preferencias,
  PagoIniciado,
  ResultadoPago,
  ProductoDadoDeAlta,
  ProductoKit,
  SinCoincidencia,
  Solicitud,
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
  ConceptoCatalogo,
  DatosColegioNuevo,
  DirectorioColegio,
  FiltrosListasAdmin,
  FiltrosProductos,
  ItemListaEditable,
  ItemRevision,
  AvisoLista,
  ListaOficial,
  OfertaCatalogo,
  PaginaProductos,
  Personaje,
  ProductoCatalogo,
  ProductoCatalogoDetalle,
  ProductoEditable,
  PropuestaCola,
  PropuestaEncolada,
  PropuestaRevision,
  RechazarPropuesta,
  RevisionLista,
  SedeColegio,
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
import { nombreArchivoMisDatos, type MisDatos, type ResultadoSupresion } from "./privacidad";
import {
  ErrorTukit,
  type AcudienteAdmin,
  type ArchivoLista,
  type Credenciales,
  type NuevaCuenta,
  type HijoNuevo,
  type MatriculaAcudiente,
  type OrigenDatos,
  type RegistroAcudiente,
  type Sesion,
} from "./origen";
import {
  cuerpoItem,
  normalizarItemRevision,
  normalizarKit,
  normalizarProductoCatalogo,
  normalizarProductoDetalle,
  normalizarPropuestaRevision,
  normalizarTrabajo,
} from "./normalizar";
import type {
  ColegioDetalleCrudo,
  ConceptoCrudo,
  PersonajeCrudo,
  ProductoCrudo,
  RevisionCruda,
  SugerenciaCruda,
} from "./normalizar";

const TIEMPO_MAXIMO_MS = 300_000;

function ordenGrado(a: string, b: string): number {
  const ia = GRADOS_CANONICOS.indexOf(a);
  const ib = GRADOS_CANONICOS.indexOf(b);
  if (ia === -1 && ib === -1) return a.localeCompare(b);
  if (ia === -1) return 1;
  if (ib === -1) return -1;
  return ia - ib;
}

export interface OpcionesCliente {
  urlBase: string;
  tiempoMaximoMs?: number;
  cabeceras?: (ruta: string) => Promise<Record<string, string>>;
}

export class ClienteApi implements OrigenDatos {
  readonly nombre = "api" as const;
  private readonly urlBase: string;
  private readonly tiempoMaximoMs: number;
  private readonly cabeceras: (ruta: string) => Promise<Record<string, string>>;

  constructor(opciones: OpcionesCliente) {
    this.urlBase = opciones.urlBase.replace(/\/+$/, "");
    this.tiempoMaximoMs = opciones.tiempoMaximoMs ?? TIEMPO_MAXIMO_MS;
    this.cabeceras = opciones.cabeceras ?? (async () => ({}));
  }

  private async conReenviadas(ruta: string, init?: RequestInit): Promise<RequestInit> {
    const reenviadas = Object.entries(await this.cabeceras(ruta));
    if (reenviadas.length === 0) return init ?? {};
    const cabeceras = new Headers(init?.headers);
    for (const [nombre, valor] of reenviadas) {
      if (!cabeceras.has(nombre)) cabeceras.set(nombre, valor);
    }
    return { ...init, headers: cabeceras };
  }

  private async pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
    let respuesta: Response;
    const conReenviadas = await this.conReenviadas(ruta, init);
    try {
      respuesta = await fetch(`${this.urlBase}${ruta}`, {
        ...conReenviadas,
        signal: AbortSignal.timeout(this.tiempoMaximoMs),
        cache: "no-store",
      });
    } catch (causa) {
      const nombre = (causa as { name?: string }).name;
      if (nombre === "TimeoutError") {
        throw new ErrorTukit(
          504,
          "tiempo_agotado",
          "El backend tardo mas de cinco minutos en responder.",
        );
      }
      throw new ErrorTukit(
        503,
        "backend_no_disponible",
        `No pudimos hablar con el backend en ${this.urlBase}. Levanta los servicios (make arriba) y revisa TUKIT_API_URL.`,
      );
    }

    if (respuesta.status === 204) return undefined as T;

    const texto = await respuesta.text();
    let cuerpo: unknown = null;
    try {
      cuerpo = texto ? JSON.parse(texto) : null;
    } catch {
      cuerpo = null;
    }

    if (!respuesta.ok) {
      const detalle = conEspera(
        respuesta.status,
        (cuerpo ?? {}) as Record<string, unknown>,
        respuesta.headers.get("Retry-After"),
      );
      throw new ErrorTukit(
        respuesta.status,
        typeof detalle["error"] === "string" ? detalle["error"] : "error_desconocido",
        typeof detalle["mensaje"] === "string"
          ? detalle["mensaje"]
          : `El backend respondio ${respuesta.status}.`,
        detalle,
      );
    }

    return cuerpo as T;
  }

  private autoriza(token?: string): Record<string, string> {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private json(ruta: string, cuerpo: unknown, metodo = "POST"): Promise<void> {
    return this.pedir<void>(ruta, {
      method: metodo,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  async iniciarSesion(cred: Credenciales): Promise<{ sesion: Sesion; token: string }> {
    return this.pedir<{ sesion: Sesion; token: string }>("/v1/sesiones", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cred),
    });
  }

  crearCuenta(cuenta: NuevaCuenta): Promise<{ sesion: Sesion; token: string }> {
    return this.pedir<{ sesion: Sesion; token: string }>("/v1/cuenta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuenta),
    });
  }

  sesionActual(token: string): Promise<Sesion | null> {
    return this.pedir<Sesion | null>("/v1/sesiones/actual", {
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  cerrarSesion(token: string): Promise<void> {
    return this.pedir<void>("/v1/sesiones/cierre", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  registrarAcudiente(datos: RegistroAcudiente): Promise<{ usuario_id: string; creado: boolean }> {
    return this.pedir<{ usuario_id: string; creado: boolean }>("/v1/registro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });
  }

  async matriculasDelAcudiente(token: string): Promise<MatriculaAcudiente[]> {
    const cuerpo = await this.pedir<{ total: number; matriculas: MatriculaAcudiente[] }>(
      "/v1/cuenta/matriculas",
      { headers: { Authorization: `Bearer ${token}` } },
    );
    return cuerpo.matriculas;
  }

  async guardarMatriculas(token: string, hijos: HijoNuevo[]): Promise<{ total: number }> {
    return this.pedir<{ total: number }>("/v1/cuenta/matriculas", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ hijos }),
    });
  }

  async quitarMatricula(token: string, matriculaId: string): Promise<void> {
    await this.pedir<void>(`/v1/cuenta/matriculas/${encodeURIComponent(matriculaId)}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  cambiarMatricula(
    token: string,
    matriculaId: string,
    cambio: { colegio_id: string; grado: string; apodo?: string | null },
  ): Promise<{ total: number }> {
    return this.pedir<{ total: number }>(`/v1/cuenta/matriculas/${encodeURIComponent(matriculaId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(cambio),
    });
  }

  cancelarSolicitud(token: string, trabajoId: string): Promise<{ trabajo_id: string; estado: string }> {
    return this.pedir(`/v1/trabajos/${encodeURIComponent(trabajoId)}/cancelar`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  cancelarListaSubida(token: string, tareaId: string): Promise<{ tarea_id: string; retiradas: number }> {
    return this.pedir(`/v1/mis-solicitudes/listas/${encodeURIComponent(tareaId)}/cancelar`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  async acudientesAdmin(token: string, ids?: string[]): Promise<AcudienteAdmin[]> {
    const qs = new URLSearchParams();
    if (ids && ids.length) qs.set("ids", ids.join(","));
    const cadena = qs.toString();
    const cuerpo = await this.pedir<{ total: number; acudientes: AcudienteAdmin[] }>(
      `/v1/admin/acudientes${cadena ? `?${cadena}` : ""}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    return cuerpo.acudientes.map((a) => ({
      ...a,
      hijos: (a.hijos ?? []).map((h) => {
        const { apodo: _apodo, ...sinApodo } = h as typeof h & { apodo?: unknown };
        return sinApodo;
      }),
    }));
  }

  async crearTrabajo(
    solicitud: SolicitudTrabajo,
    archivos: ArchivoLista[] = [],
    token?: string,
  ): Promise<TrabajoCreado> {
    if (archivos.length === 0) {
      return this.pedir<TrabajoCreado>("/v1/trabajos", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...this.autoriza(token) },
        body: JSON.stringify(solicitud),
      });
    }

    const forma = new FormData();
    forma.append("hijos", JSON.stringify(solicitud));
    for (const archivo of archivos) {
      forma.append("archivo", archivo.contenido, archivo.nombre);
      forma.append("referencia", archivo.referencia);
    }
    return this.pedir<TrabajoCreado>("/v1/trabajos", {
      method: "POST",
      headers: this.autoriza(token),
      body: forma,
    });
  }

  async consultarTrabajo(trabajoId: string, token?: string): Promise<Trabajo> {
    const crudo = await this.pedir<Trabajo>(`/v1/trabajos/${encodeURIComponent(trabajoId)}`, {
      headers: this.autoriza(token),
    });
    return normalizarTrabajo(crudo);
  }

  async subirListas(
    hijos: HijoSubida[],
    archivos: ArchivoLista[],
    contacto?: Contacto,
    preferencias?: Preferencias,
    token?: string,
  ): Promise<SubidaListas> {
    const forma = new FormData();
    forma.append("hijos", JSON.stringify(hijos));
    if (contacto) forma.append("contacto", JSON.stringify(contacto));
    if (preferencias) forma.append("preferencias", JSON.stringify(preferencias));
    for (const archivo of archivos) {
      forma.append("archivo", archivo.contenido, archivo.nombre);
      forma.append("referencia", archivo.referencia);
    }
    return this.pedir<SubidaListas>("/v1/listas/subir", {
      method: "POST",
      headers: this.autoriza(token),
      body: forma,
    });
  }

  async catalogo(): Promise<Catalogo> {
    const [resumen, tiendasResp, conceptosResp, productos] = await Promise.all([
      this.pedir<Catalogo["resumen"]>("/v1/catalogo/resumen"),
      this.pedir<{ tiendas: Catalogo["tiendas"] }>("/v1/catalogo/tiendas"),
      this.pedir<{ conceptos: ConceptoCrudo[] }>("/v1/catalogo/conceptos?por_pagina=200"),
      this.todosLosProductos(),
    ]);

    const porConcepto = new Map<string, ProductoCatalogo[]>();
    for (const p of productos) {
      const codigo = p.concepto?.codigo;
      if (!codigo) continue;
      const lista = porConcepto.get(codigo) ?? [];
      lista.push(normalizarProductoCatalogo(p));
      porConcepto.set(codigo, lista);
    }

    const conceptos: ConceptoCatalogo[] = (conceptosResp.conceptos ?? []).map((c) => ({
      codigo: c.codigo,
      nombre_canonico: c.nombre_canonico ?? c.nombre ?? c.codigo,
      sinonimos: c.sinonimos ?? [],
      categoria: c.categoria,
      tipo_item: c.tipo_item,
      atributos_discriminantes: c.atributos_discriminantes ?? [],
      atributos_descriptivos: c.atributos_descriptivos ?? [],
      admite_personaje: Boolean(c.admite_personaje),
      frecuencia_demanda: c.frecuencia_demanda ?? 0,
      productos: porConcepto.get(c.codigo) ?? [],
    }));

    return {
      resumen,
      tiendas: tiendasResp.tiendas ?? [],
      conceptos,
    };
  }

  private async todosLosProductos(): Promise<ProductoCrudo[]> {
    const POR_PAGINA = 200;
    const todos: ProductoCrudo[] = [];
    for (let pagina = 1; ; pagina += 1) {
      const resp = await this.pedir<{ total: number; productos: ProductoCrudo[] }>(
        `/v1/catalogo/productos?con_ofertas=true&por_pagina=${POR_PAGINA}&pagina=${pagina}`,
      );
      const lote = resp.productos ?? [];
      todos.push(...lote);
      if (lote.length < POR_PAGINA || todos.length >= (resp.total ?? todos.length)) break;
    }
    return todos;
  }

  async colegios(): Promise<Colegio[]> {
    const [colegiosResp, listasResp] = await Promise.all([
      this.pedir<{
        colegios: {
          colegio_id: string;
          nombre: string;
          dane?: string | null;
          logo_url?: string | null;
        }[];
      }>("/v1/colegios"),
      this.pedir<{
        total: number;
        listas: { colegio_id: string; grado: string; revisada: boolean }[];
      }>("/v1/listas?revisada=true&por_pagina=200"),
    ]);

    const gradosPorColegio = new Map<string, Set<string>>();
    for (const lista of listasResp.listas ?? []) {
      const set = gradosPorColegio.get(lista.colegio_id) ?? new Set<string>();
      set.add(lista.grado);
      gradosPorColegio.set(lista.colegio_id, set);
    }

    return (colegiosResp.colegios ?? [])
      .map((c) => {
        const grados = [...(gradosPorColegio.get(c.colegio_id) ?? [])].sort(ordenGrado);
        return {
          colegio_id: c.colegio_id,
          nombre: c.nombre,
          fuente: "backend",
          atribucion_dudosa: false,
          logo_url: c.logo_url ?? null,
          dane: c.dane ?? null,
          grados,
          es_partner: grados.length > 0,
        };
      });
  }

  async listaOficial(colegioId: string, grado: string): Promise<ListaOficial> {
    const indice = await this.pedir<{
      listas: { lista_id: string; grado: string; anio_lectivo: number; version: number }[];
    }>(
      `/v1/listas?colegio_id=${encodeURIComponent(colegioId)}&grado=${encodeURIComponent(grado)}&por_pagina=1`,
    );
    const encontrada = indice.listas?.[0];
    if (!encontrada) {
      throw new ErrorTukit(404, "lista_no_existe", "No tenemos esa lista todavía.");
    }
    const detalle = await this.pedir<{
      colegio_id: string;
      grado: string;
      anio_lectivo: number;
      version: number;
      version_id: string;
      items: ListaOficial["items"];
    }>(`/v1/listas/${encodeURIComponent(encontrada.lista_id)}`);
    return {
      colegio_id: detalle.colegio_id,
      grado: detalle.grado,
      anio_lectivo: detalle.anio_lectivo,
      version: detalle.version,
      version_id: detalle.version_id,
      items: detalle.items ?? [],
    };
  }

  async personajes(): Promise<Personaje[]> {
    const resp = await this.pedir<{ personajes?: PersonajeCrudo[] }>(
      "/v1/catalogo/personajes",
    );
    return (resp.personajes ?? []).map((p) => ({
      nombre: p.nombre,
      productos: typeof p.productos === "number" ? p.productos : 0,
      ...(Array.isArray(p.conceptos) ? { conceptos: p.conceptos } : {}),
    }));
  }

  async buscarProductos(filtros: FiltrosProductos): Promise<PaginaProductos> {
    const qs = new URLSearchParams();
    if (filtros.concepto) qs.set("concepto", filtros.concepto);
    if (filtros.nivel) qs.set("nivel", filtros.nivel);
    if (filtros.personaje) qs.set("personaje", filtros.personaje);
    if (filtros.con_personaje !== undefined)
      qs.set("con_personaje", String(filtros.con_personaje));
    if (filtros.busqueda) qs.set("busqueda", filtros.busqueda);
    if (filtros.con_precio !== undefined) qs.set("con_precio", String(filtros.con_precio));
    if (filtros.con_ofertas !== undefined) qs.set("con_ofertas", String(filtros.con_ofertas));
    if (filtros.pagina !== undefined) qs.set("pagina", String(filtros.pagina));
    if (filtros.por_pagina !== undefined) qs.set("por_pagina", String(filtros.por_pagina));
    const cadena = qs.toString();
    const resp = await this.pedir<{
      total?: number;
      pagina?: number;
      por_pagina?: number;
      productos?: ProductoCrudo[];
    }>(`/v1/catalogo/productos${cadena ? `?${cadena}` : ""}`);
    const productos = (resp.productos ?? []).map(normalizarProductoDetalle);
    return {
      total: typeof resp.total === "number" ? resp.total : productos.length,
      pagina: typeof resp.pagina === "number" ? resp.pagina : (filtros.pagina ?? 1),
      por_pagina:
        typeof resp.por_pagina === "number"
          ? resp.por_pagina
          : (filtros.por_pagina ?? productos.length),
      productos,
    };
  }

  async editarProducto(
    sku: string,
    cambios: ProductoEditable,
  ): Promise<ProductoCatalogoDetalle> {
    const crudo = await this.pedir<ProductoCrudo>(
      `/v1/catalogo/productos/${encodeURIComponent(sku)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cambios),
      },
    );
    return normalizarProductoDetalle(crudo);
  }

  async reclasificarProducto(
    sku: string,
    concepto: string,
  ): Promise<ProductoCatalogoDetalle> {
    const crudo = await this.pedir<ProductoCrudo>(
      `/v1/catalogo/productos/${encodeURIComponent(sku)}/reclasificar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ concepto }),
      },
    );
    return normalizarProductoDetalle(crudo);
  }

  eliminarProducto(sku: string): Promise<void> {
    return this.pedir<void>(`/v1/catalogo/productos/${encodeURIComponent(sku)}`, {
      method: "DELETE",
    });
  }

  async colaPropuestas(concepto?: string): Promise<PropuestaCola[]> {
    const qs = concepto ? `?concepto=${encodeURIComponent(concepto)}` : "";
    const resp = await this.pedir<{ total?: number; propuestas?: PropuestaCola[] }>(
      `/v1/admin/catalogo/propuestas${qs}`,
    );
    return resp.propuestas ?? [];
  }

  async buscarEnTienda(
    slug: string,
    consulta: string,
    cuantos?: number,
  ): Promise<CandidatoTienda[]> {
    const qs = new URLSearchParams({ consulta });
    if (cuantos !== undefined) qs.set("cuantos", String(cuantos));
    const resp = await this.pedir<{ candidatos?: CandidatoTienda[] }>(
      `/v1/admin/catalogo/tiendas/${encodeURIComponent(slug)}/buscar?${qs.toString()}`,
    );
    return resp.candidatos ?? [];
  }

  crearConcepto(cuerpo: CrearConcepto): Promise<ConceptoCreado> {
    return this.pedir<ConceptoCreado>("/v1/admin/catalogo/conceptos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  altaUtil(cuerpo: AltaUtil): Promise<PropuestaEncolada> {
    return this.pedir<PropuestaEncolada>("/v1/admin/catalogo/propuestas/util", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  altaUtilManual(cuerpo: AltaUtilManual): Promise<PropuestaEncolada> {
    return this.pedir<PropuestaEncolada>("/v1/admin/catalogo/propuestas/util-manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  altaLibro(cuerpo: AltaLibro): Promise<PropuestaEncolada> {
    return this.pedir<PropuestaEncolada>("/v1/admin/catalogo/propuestas/libro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  aprobarPropuesta(
    id: string,
    cuerpo: AprobarPropuesta,
  ): Promise<{ id: string; estado: string }> {
    return this.pedir<{ id: string; estado: string }>(
      `/v1/admin/catalogo/propuestas/${encodeURIComponent(id)}/aprobar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      },
    );
  }

  rechazarPropuesta(
    id: string,
    cuerpo: RechazarPropuesta,
  ): Promise<{ id: string; estado: string }> {
    return this.pedir<{ id: string; estado: string }>(
      `/v1/admin/propuestas/${encodeURIComponent(id)}/rechazar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      },
    );
  }

  async cola(): Promise<ColaAdmin> {
    const crudo = await this.pedir<{
      trabajos?: {
        trabajo_id: string;
        estado: EstadoTrabajo;
        origen?: string;
        creado_en: string;
        hijos: number;
        colegios?: string[];
        grados?: string[];
        lineas_a_revisar: number;
        edicion_de?: string | null;
      }[];
    }>("/v1/admin/cola");
    return {
      entradas: (crudo.trabajos ?? []).map((t) => ({
        trabajo_id: t.trabajo_id,
        estado: t.estado,
        origen: t.origen,
        recibido_en: t.creado_en,
        hijos: t.hijos,
        lineas_totales: t.lineas_a_revisar,
        lineas_pendientes: t.lineas_a_revisar,
        colegios: t.colegios ?? [],
        grados: t.grados ?? [],
        edicion_de: t.edicion_de ?? null,
      })),
    };
  }

  async trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin> {
    const crudo = await this.pedir<TrabajoAdmin>(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}`,
    );
    return {
      ...crudo,
      kits: crudo.kits.map(normalizarKit),
      lineas_pendientes: crudo.lineas_pendientes ?? [],
    };
  }

  acudientesDeColegio(colegioId: string): Promise<AcudienteResumen[]> {
    return this.pedir<{ acudientes: Partial<AcudienteResumen>[] }>(
      `/v1/admin/colegios/${encodeURIComponent(colegioId)}/acudientes`,
    ).then((r) =>
      (r.acudientes ?? []).map((a) => ({
        ...(a as AcudienteResumen),
        grados: a.grados ?? [],
        preferencias: a.preferencias ?? {},
      })),
    );
  }

  async nombresDeUsuarios(ids: string[], token: string): Promise<Record<string, string>> {
    if (ids.length === 0) return {};
    const cola = ids.map((id) => `ids=${encodeURIComponent(id)}`).join("&");
    const r = await this.pedir<{ nombres?: Record<string, string> }>(
      `/v1/usuarios/nombres?${cola}`,
      { headers: this.autoriza(token) },
    );
    return r.nombres ?? {};
  }

  validarLinea(trabajoId: string, itemId: string, cuerpo: ValidarLinea): Promise<void> {
    return this.json(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/lineas/${encodeURIComponent(itemId)}/validar`,
      cuerpo,
    );
  }

  fijarProductoLinea(
    trabajoId: string,
    perfil: string,
    itemId: string,
    sku: string,
  ): Promise<void> {
    return this.json(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}/lineas/${encodeURIComponent(itemId)}/producto`,
      { sku },
      "PUT",
    );
  }

  async gradosCanonicos(colegioId?: string): Promise<GradoCanonico[]> {
    const cola = colegioId ? `?colegio_id=${encodeURIComponent(colegioId)}` : "";
    const resp = await this.pedir<{ grados?: GradoCanonico[] }>(`/v1/grados-canonicos${cola}`);
    return resp.grados ?? [];
  }

  aplicarCanonico(cuerpo: AplicarCanonico, token?: string): Promise<TrabajoAplicado> {
    return this.pedir<TrabajoAplicado>("/v1/trabajos/aplicar-canonico", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify(cuerpo),
    });
  }

  iniciarCheckout(trabajoId: string, cuerpo: SolicitudCheckout, token?: string): Promise<Checkout> {
    return this.pedir<Checkout>(
      `/v1/trabajos/${encodeURIComponent(trabajoId)}/ordenar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...this.autoriza(token) },
        body: JSON.stringify(cuerpo),
      },
    );
  }

  cambiarProductoDeKit(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    sku: string,
    token?: string,
  ): Promise<CambioDeProducto> {
    const ruta =
      `/v1/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}` +
      `/lineas/${encodeURIComponent(itemId)}/producto`;
    return this.pedir<CambioDeProducto>(ruta, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ sku }),
    });
  }

  descartarLineaDeKit(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    descartado: boolean,
    token?: string,
  ): Promise<CambioDeDescarte> {
    const ruta =
      `/v1/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}` +
      `/lineas/${encodeURIComponent(itemId)}/descarte`;
    return this.pedir<CambioDeDescarte>(ruta, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ descartado }),
    });
  }

  opcionesDeLinea(
    trabajoId: string,
    perfil: PerfilKit,
    itemId: string,
    token?: string,
  ): Promise<OpcionesDeLinea> {
    const ruta =
      `/v1/trabajos/${encodeURIComponent(trabajoId)}/kits/${encodeURIComponent(perfil)}` +
      `/lineas/${encodeURIComponent(itemId)}/opciones`;
    return this.pedir<OpcionesDeLinea>(ruta, { headers: this.autoriza(token) });
  }

  miPedido(token: string, pedidoId: string): Promise<PedidoDelAcudiente> {
    return this.pedir<PedidoDelAcudiente>(`/v1/comercio/mis-pedidos/${encodeURIComponent(pedidoId)}`, {
      headers: this.autoriza(token),
    });
  }

  iniciarPagoPedido(
    token: string,
    pedidoId: string,
    cuerpo: { correo_cliente: string; url_redireccion?: string },
  ): Promise<PagoIniciado> {
    return this.pedir<PagoIniciado>(
      `/v1/comercio/mis-pedidos/${encodeURIComponent(pedidoId)}/pago`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...this.autoriza(token) },
        body: JSON.stringify(cuerpo),
      },
    );
  }

  cancelarPedido(token: string, pedidoId: string): Promise<Pedido> {
    return this.pedir<Pedido>(
      `/v1/comercio/mis-pedidos/${encodeURIComponent(pedidoId)}/cancelar`,
      { method: "POST", headers: this.autoriza(token) },
    );
  }

  retractarPedido(token: string, pedidoId: string, motivo: string): Promise<RetractoSolicitado> {
    return this.pedir<RetractoSolicitado>(
      `/v1/comercio/mis-pedidos/${encodeURIComponent(pedidoId)}/retracto`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...this.autoriza(token) },
        body: JSON.stringify({ motivo }),
      },
    );
  }

  misDatos(token: string): Promise<MisDatos> {
    return this.pedir<MisDatos>("/v1/cuenta/mis-datos", { headers: this.autoriza(token) });
  }

  async exportarMisDatos(token: string): Promise<{ contenido: string; nombreArchivo: string }> {
    const datos = await this.pedir<unknown>("/v1/cuenta/mis-datos/exportar", {
      headers: this.autoriza(token),
    });
    return { contenido: JSON.stringify(datos, null, 2), nombreArchivo: nombreArchivoMisDatos(new Date()) };
  }

  suprimirMisDatos(token: string, confirmacion: string): Promise<ResultadoSupresion> {
    return this.pedir<ResultadoSupresion>("/v1/cuenta/supresion", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify({ confirmacion }),
    });
  }

  revocarConsentimientos(token: string): Promise<{ revocados: number }> {
    return this.pedir<{ revocados: number }>("/v1/cuenta/consentimientos/revocar", {
      method: "POST",
      headers: this.autoriza(token),
    });
  }

  async misCasos(token: string): Promise<MiCaso[]> {
    const resp = await this.pedir<{ total: number; casos: MiCaso[] }>("/v1/operacion/mis-casos", {
      headers: this.autoriza(token),
    });
    return resp.casos ?? [];
  }

  miCaso(token: string, casoId: string): Promise<MiCasoDetalle> {
    return this.pedir<MiCasoDetalle>(`/v1/operacion/mis-casos/${encodeURIComponent(casoId)}`, {
      headers: this.autoriza(token),
    });
  }

  abrirMiCaso(token: string, solicitud: SolicitudMiCaso): Promise<CasoCreado> {
    return this.pedir<CasoCreado>("/v1/operacion/mis-casos", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify(solicitud),
    });
  }

  async comentarMiCaso(token: string, casoId: string, texto: string): Promise<void> {
    await this.pedir<unknown>(`/v1/operacion/mis-casos/${encodeURIComponent(casoId)}/comentarios`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify({ texto }),
    });
  }

  sincronizarPago(transaccionId: string): Promise<ResultadoPago> {
    return this.pedir<ResultadoPago>(
      `/v1/pagos/${encodeURIComponent(transaccionId)}/sincronizar`,
      { method: "POST" },
    );
  }

  marcarSinCoincidencia(
    trabajoId: string,
    itemId: string,
    cuerpo: SinCoincidencia,
  ): Promise<void> {
    return this.json(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/lineas/${encodeURIComponent(itemId)}/sin-coincidencia`,
      cuerpo,
    );
  }

  altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
    return this.pedir<ProductoDadoDeAlta>("/v1/admin/productos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
  }

  marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
    return this.json(`/v1/admin/productos/${encodeURIComponent(sku)}/no-disponible`, cuerpo);
  }

  decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
    return this.json(`/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/revision`, cuerpo);
  }

  fijarCanonico(trabajoId: string, cuerpo: { nota?: string }): Promise<void> {
    return this.json(`/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/canonico`, cuerpo);
  }

  abrirBorradorKits(trabajoId: string): Promise<BorradorKits> {
    return this.pedir<BorradorKits>(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}/borrador`,
      { method: "POST" },
    );
  }

  eliminarTrabajo(trabajoId: string): Promise<void> {
    return this.pedir<void>(`/v1/admin/trabajos/${encodeURIComponent(trabajoId)}`, {
      method: "DELETE",
    });
  }

  async onboarding(
    token: string,
    colegio: string | ColegioDesignado,
    grado: string,
    anio_lectivo: number,
    archivo: { contenido: Blob; nombre: string },
  ): Promise<{ version_id: string; grado: string; items: number }> {
    const forma = new FormData();
    const designado = typeof colegio === "string" ? { colegio_id: colegio } : colegio;
    for (const [campo, valor] of Object.entries(designado)) forma.append(campo, valor);
    forma.append("grado", grado);
    forma.append("anio_lectivo", String(anio_lectivo));
    forma.append("archivo", archivo.contenido, archivo.nombre);
    return this.pedir<{ version_id: string; grado: string; items: number }>(
      "/v1/admin/onboarding",
      { method: "POST", headers: this.autoriza(token), body: forma },
    );
  }

  async sugerirColegio(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo?: { contenido: Blob; nombre: string },
    contacto_referencia?: string,
  ): Promise<{ tarea_id: string; estado: string }> {
    const documento_base64 = archivo ? await this.aBase64(archivo.contenido) : null;
    return this.pedir<{ tarea_id: string; estado: string }>("/v1/admin/sugerencias", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        colegio_id,
        grado,
        anio_lectivo,
        contacto_referencia: contacto_referencia ?? null,
        evidencia: { documento_base64 },
      }),
    });
  }

  private async aBase64(blob: Blob): Promise<string> {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binario = "";
    const bloque = 0x8000;
    for (let i = 0; i < bytes.length; i += bloque) {
      binario += String.fromCharCode(...bytes.subarray(i, i + bloque));
    }
    return btoa(binario);
  }

  async listasAdmin(filtros: FiltrosListasAdmin = {}): Promise<VersionListaAdmin[]> {
    const qs = new URLSearchParams();
    if (filtros.revisada !== undefined) qs.set("revisada", String(filtros.revisada));
    if (filtros.colegio_id) qs.set("colegio_id", filtros.colegio_id);
    if (filtros.grado) qs.set("grado", filtros.grado);
    if (filtros.anio_lectivo !== undefined) qs.set("anio_lectivo", String(filtros.anio_lectivo));
    const cadena = qs.toString();
    const resp = await this.pedir<{ listas?: Partial<VersionListaAdmin>[] }>(
      `/v1/admin/listas${cadena ? `?${cadena}` : ""}`,
    );
    return (resp.listas ?? []).map((v) => ({
      ...(v as VersionListaAdmin),
      procedencia: v.procedencia ?? null,
      tiene_contacto: v.tiene_contacto ?? false,
      colegio_nombre: v.colegio_nombre ?? null,
    }));
  }

  async revisionLista(versionId: string): Promise<RevisionLista> {
    const crudo = await this.pedir<RevisionCruda>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/revision`,
    );
    return {
      version_id: crudo.version_id,
      colegio_id: crudo.colegio_id,
      grado: crudo.grado,
      anio_lectivo: crudo.anio_lectivo,
      numero: crudo.numero,
      revisada: Boolean(crudo.revisada),
      items: (crudo.items ?? []).map(normalizarItemRevision),
      propuestas: (crudo.propuestas ?? []).map(normalizarPropuestaRevision),
      colegio_datos: crudo.colegio_datos ?? null,
    };
  }

  editarItemLista(
    versionId: string,
    itemId: string,
    cambios: ItemListaEditable,
  ): Promise<void> {
    return this.pedir<void>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/items/${encodeURIComponent(itemId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpoItem(cambios)),
      },
    );
  }

  async agregarItemLista(
    versionId: string,
    item: ItemListaEditable,
  ): Promise<{ item_id: string }> {
    const resp = await this.pedir<{ item_id: string; orden?: number }>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/items`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpoItem(item)),
      },
    );
    return { item_id: resp.item_id };
  }

  quitarItemLista(versionId: string, itemId: string): Promise<void> {
    return this.pedir<void>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/items/${encodeURIComponent(itemId)}`,
      { method: "DELETE" },
    );
  }

  eliminarVersionLista(versionId: string): Promise<void> {
    return this.pedir<void>(`/v1/admin/listas/${encodeURIComponent(versionId)}`, {
      method: "DELETE",
    });
  }

  cerrarLista(versionId: string): Promise<void> {
    return this.pedir<void>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/cerrar`,
      { method: "POST" },
    );
  }

  async nuevaVersion(
    colegioId: string,
    grado: string,
    anioLectivo: number,
  ): Promise<{ version_id: string }> {
    const resp = await this.pedir<{ version_id: string; numero?: number; revisada?: boolean }>(
      `/v1/admin/listas/${encodeURIComponent(colegioId)}/${encodeURIComponent(grado)}/nueva-version?anio_lectivo=${anioLectivo}`,
      { method: "POST" },
    );
    return { version_id: resp.version_id };
  }

  async avisosLista(versionId: string): Promise<AvisoLista[]> {
    const resp = await this.pedir<{ version_id: string; avisos: AvisoLista[] }>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/avisos`,
    );
    return resp.avisos;
  }

  async descartarAviso(versionId: string, itemId: string, clave: string): Promise<void> {
    await this.pedir<unknown>(`/v1/admin/listas/${encodeURIComponent(versionId)}/avisos/descartar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_id: itemId, clave }),
    });
  }

  async noComprarRepetido(
    versionId: string,
    itemId: string,
    repiteA: number,
  ): Promise<{ version_id: string }> {
    const resp = await this.pedir<{ version_id: string; numero: number }>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/items/${encodeURIComponent(itemId)}/no-comprar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repite_a: repiteA }),
      },
    );
    return { version_id: resp.version_id };
  }

  async completarColegioDeVersion(
    versionId: string,
    cambios: ColegioNuevoEditable,
  ): Promise<DatosColegioNuevo> {
    const resp = await this.pedir<{ version_id: string; colegio_datos: DatosColegioNuevo }>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/colegio`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cambios),
      },
    );
    return resp.colegio_datos;
  }

  async directorioColegio(dane: string): Promise<DatosColegioNuevo | null> {
    try {
      return await this.pedir<DatosColegioNuevo>(
        `/v1/directorio/${encodeURIComponent(dane)}`,
      );
    } catch (causa) {
      if (causa instanceof ErrorTukit && causa.estado === 404) return null;
      throw causa;
    }
  }

  async directorioCompleto(dane: string): Promise<DirectorioColegio | null> {
    try {
      return await this.pedir<DirectorioColegio>(
        `/v1/directorio/${encodeURIComponent(dane)}?completo=true`,
      );
    } catch (causa) {
      if (causa instanceof ErrorTukit && causa.estado === 404) return null;
      throw causa;
    }
  }

  colegio(colegioId: string): Promise<ColegioDetalle> {
    return this.pedirColegioDetalle(
      `/v1/colegios/${encodeURIComponent(colegioId)}`,
    );
  }

  editarColegio(colegioId: string, cambios: ColegioEditable): Promise<ColegioDetalle> {
    return this.pedirColegioDetalle(`/v1/colegios/${encodeURIComponent(colegioId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cambios),
    });
  }

  async previewDeVersion(
    versionId: string,
    ctx: { colegioId: string; grado: string; anioLectivo: number },
  ): Promise<{ trabajo_id: string }> {
    const resp = await this.pedir<{ trabajo_id: string; estado: string }>(
      `/v1/admin/onboarding/${encodeURIComponent(versionId)}/preview`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          colegio_id: ctx.colegioId,
          grado: ctx.grado,
          anio_lectivo: ctx.anioLectivo,
        }),
      },
    );
    return { trabajo_id: resp.trabajo_id };
  }

  private async pedirColegioDetalle(
    ruta: string,
    init?: RequestInit,
  ): Promise<ColegioDetalle> {
    const c = await this.pedir<ColegioDetalleCrudo>(ruta, init);
    return {
      colegio_id: c.colegio_id,
      nombre: c.nombre,
      dane: c.dane ?? null,
      logo_url: c.logo_url ?? null,
      sitio_web: c.sitio_web ?? null,
      contacto_nombre: c.contacto_nombre ?? null,
      contacto_email: c.contacto_email ?? null,
      contacto_telefono: c.contacto_telefono ?? null,
      direccion: c.direccion ?? null,
      sedes: (c.sedes ?? []).map(
        (s): SedeColegio => ({ sede_id: s.sede_id, nombre: s.nombre }),
      ),
    };
  }

  async sugerencias(): Promise<Sugerencia[]> {
    const resp = await this.pedir<{ sugerencias?: SugerenciaCruda[] }>(
      "/v1/admin/sugerencias",
    );
    return (resp.sugerencias ?? []).map((s) => ({
      tarea_id: s.tarea_id,
      estado: s.estado,
      colegio_id: s.colegio_id ?? null,
      grado: s.grado ?? null,
      anio_lectivo: s.anio_lectivo ?? null,
      contacto_referencia: s.contacto_referencia ?? null,
      tiene_documento: Boolean(s.tiene_documento),
    }));
  }

  async documento(versionId: string): Promise<Blob> {
    let respuesta: Response;
    const ruta = `/v1/admin/listas/${encodeURIComponent(versionId)}/documento`;
    const conReenviadas = await this.conReenviadas(ruta);
    try {
      respuesta = await fetch(`${this.urlBase}${ruta}`, {
        ...conReenviadas,
        signal: AbortSignal.timeout(this.tiempoMaximoMs),
        cache: "no-store",
      });
    } catch (causa) {
      const nombre = (causa as { name?: string }).name;
      if (nombre === "TimeoutError") {
        throw new ErrorTukit(504, "tiempo_agotado", "El backend tardo demasiado en responder.");
      }
      throw new ErrorTukit(
        503,
        "backend_no_disponible",
        `No pudimos hablar con el backend en ${this.urlBase}. Levanta los servicios (make arriba) y revisa TUKIT_API_URL.`,
      );
    }
    if (respuesta.status === 404) {
      throw new ErrorTukit(404, "sin_evidencia", "Esta lista no tiene documento adjunto.");
    }
    if (respuesta.status === 429) {
      const cuerpo = (await respuesta.json().catch(() => ({}))) as Record<string, unknown>;
      const detalle = conEspera(429, cuerpo, respuesta.headers.get("Retry-After"));
      throw new ErrorTukit(429, String(detalle["error"]), String(detalle["mensaje"]), detalle);
    }
    if (!respuesta.ok) {
      throw new ErrorTukit(
        respuesta.status,
        "error_documento",
        `El backend respondio ${respuesta.status} al pedir el documento.`,
      );
    }
    return respuesta.blob();
  }

  async percepcion(versionId: string): Promise<PercepcionCruda> {
    const crudo = await this.pedir<{
      version_id: string;
      paginas?: { pagina: number; crudo: string }[];
      items?: {
        texto_original?: string;
        descripcion?: string;
        cantidad?: number | null;
        confianza?: number | null;
      }[];
    }>(`/v1/admin/listas/${encodeURIComponent(versionId)}/percepcion`);
    return {
      paginas: (crudo.paginas ?? []).map((p) => ({ pagina: p.pagina, crudo: p.crudo })),
      items: (crudo.items ?? []).map((i) => ({
        texto_original: i.texto_original ?? i.descripcion,
        descripcion: i.descripcion,
        cantidad: i.cantidad ?? null,
        confianza: i.confianza ?? null,
      })),
    };
  }

  pedidos(token: string): Promise<TableroComercio> {
    return this.pedir<TableroComercio>("/v1/comercio/pedidos", {
      headers: this.autoriza(token),
    });
  }

  pedido(token: string, pedidoId: string): Promise<PedidoConHistorial> {
    return this.pedir<PedidoConHistorial>(
      `/v1/comercio/pedidos/${encodeURIComponent(pedidoId)}`,
      { headers: this.autoriza(token) },
    );
  }

  avanzarPedido(
    token: string,
    pedidoId: string,
    cuerpo: SolicitudAvancePedido,
  ): Promise<PedidoConHistorial> {
    return this.pedir<PedidoConHistorial>(
      `/v1/ordenes/${encodeURIComponent(pedidoId)}/avanzar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", ...this.autoriza(token) },
        body: JSON.stringify(cuerpo),
      },
    );
  }

  async misPedidos(token: string): Promise<Pedido[]> {
    const resp = await this.pedir<{ total: number; pedidos: Pedido[] }>(
      "/v1/comercio/mis-pedidos",
      { headers: this.autoriza(token) },
    );
    return resp.pedidos ?? [];
  }

  async misTrabajos(token?: string): Promise<TrabajoResumen[]> {
    const resp = await this.pedir<{ total: number; trabajos: TrabajoResumen[] }>("/v1/trabajos", {
      headers: { ...this.autoriza(token) },
    });
    return resp.trabajos ?? [];
  }

  async misSolicitudes(token: string): Promise<MisSolicitudes> {
    const cuerpo = await this.pedir<{ solicitudes?: Solicitud[]; listas_disponibles?: boolean }>(
      "/v1/mis-solicitudes",
      { headers: { Authorization: `Bearer ${token}` } },
    );
    return {
      solicitudes: cuerpo.solicitudes ?? [],
      listas_disponibles: cuerpo.listas_disponibles ?? true,
    };
  }

  casos(token?: string, usuarioId?: string): Promise<BandejaOperacion> {
    const qs = usuarioId ? `?usuario_id=${encodeURIComponent(usuarioId)}` : "";
    return this.pedir<BandejaOperacion>(`/v1/operacion/casos${qs}`, { headers: this.autoriza(token) });
  }

  correos(token: string, filtros: FiltrosCorreos = {}): Promise<BandejaCorreos> {
    const qs = new URLSearchParams();
    for (const [clave, valor] of Object.entries(filtros)) {
      if (valor !== undefined && valor !== "") qs.set(clave, String(valor));
    }
    const sufijo = qs.size ? `?${qs}` : "";
    return this.pedir<BandejaCorreos>(`/v1/operacion/correos${sufijo}`, { headers: this.autoriza(token) });
  }

  caso(casoId: string, token?: string): Promise<Caso> {
    return this.pedir<Caso>(`/v1/operacion/casos/${encodeURIComponent(casoId)}`, {
      headers: this.autoriza(token),
    });
  }

  pedidoAdmin(token: string, pedidoId: string): Promise<PedidoAdmin> {
    return this.pedir<PedidoAdmin>(`/v1/comercio/pedidos/${encodeURIComponent(pedidoId)}`, {
      headers: this.autoriza(token),
    });
  }

  avanzarPedidoAdmin(
    token: string,
    pedidoId: string,
    cuerpo: SolicitudAvanceAdmin,
  ): Promise<PedidoAdmin> {
    return this.pedir<PedidoAdmin>(`/v1/ordenes/${encodeURIComponent(pedidoId)}/avanzar`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify(cuerpo),
    });
  }

  casoAdmin(token: string, casoId: string): Promise<CasoDetalleAdmin> {
    return this.pedir<CasoDetalleAdmin>(`/v1/operacion/casos/${encodeURIComponent(casoId)}`, {
      headers: this.autoriza(token),
    });
  }

  private postCaso(token: string, casoId: string, accion: string, cuerpo: unknown): Promise<CasoDetalleAdmin> {
    return this.pedir<CasoDetalleAdmin>(`/v1/operacion/casos/${encodeURIComponent(casoId)}/${accion}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify(cuerpo),
    });
  }

  responderCaso(token: string, casoId: string, texto: string): Promise<CasoDetalleAdmin> {
    return this.postCaso(token, casoId, "responder", { texto });
  }

  cambiarEstadoCaso(token: string, casoId: string, destino: string): Promise<CasoDetalleAdmin> {
    return this.postCaso(token, casoId, "estado", { destino });
  }

  vincularPedidoCaso(token: string, casoId: string, pedidoId: string): Promise<CasoDetalleAdmin> {
    return this.postCaso(token, casoId, "pedido", { pedido_id: pedidoId });
  }

  reconciliarPagoPedido(token: string, pedidoId: string): Promise<RespuestaReconciliacion> {
    return this.pedir<RespuestaReconciliacion>(
      `/v1/comercio/pedidos/${encodeURIComponent(pedidoId)}/reconciliar-pago`,
      { method: "POST", headers: this.autoriza(token) },
    );
  }

  vistaPreviaPedido(token: string, pedidoId: string, destino: string): Promise<VistaPreviaPedido> {
    return this.pedir<VistaPreviaPedido>(
      `/v1/comercio/pedidos/${encodeURIComponent(pedidoId)}/vista-previa?destino=${encodeURIComponent(destino)}`,
      { headers: this.autoriza(token) },
    );
  }

  avanzarLote(
    token: string,
    cuerpo: { pedido_ids: string[]; destino: DestinoDeLote },
  ): Promise<RespuestaLote> {
    return this.pedir<RespuestaLote>("/v1/comercio/pedidos/avanzar-lote", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...this.autoriza(token) },
      body: JSON.stringify(cuerpo),
    });
  }

  asignarCaso(token: string, casoId: string, asignar: AsignacionCaso): Promise<CasoDetalleAdmin> {
    return this.postCaso(token, casoId, "asignar", { asignar });
  }

  cambiarPrioridadCaso(token: string, casoId: string, prioridad: PrioridadCaso): Promise<CasoDetalleAdmin> {
    return this.postCaso(token, casoId, "prioridad", { prioridad });
  }

  notaInternaCaso(token: string, casoId: string, texto: string): Promise<CasoDetalleAdmin> {
    return this.postCaso(token, casoId, "nota", { texto });
  }

  async productoPublico(sku: string): Promise<ProductoCatalogo | null> {
    try {
      const crudo = await this.pedir<ProductoCrudo>(`/v1/catalogo/productos/${encodeURIComponent(sku)}`);
      return normalizarProductoCatalogo(crudo);
    } catch (causa) {
      if (causa instanceof ErrorTukit && causa.estado === 404) return null;
      throw causa;
    }
  }

  crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado> {
    return this.pedir<CasoCreado>("/v1/operacion/casos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(solicitud),
    });
  }

  metricasColegio(colegioId: string): Promise<MetricasColegio> {
    return this.pedir<MetricasColegio>(
      `/v1/metricas/colegios/${encodeURIComponent(colegioId)}`,
    );
  }

  resumenPedidosColegio(token: string, colegioId: string): Promise<ResumenPedidosColegio> {
    return this.pedir<ResumenPedidosColegio>(
      `/v1/metricas/colegios/${encodeURIComponent(colegioId)}/pedidos`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
  }

  metricasSerie(filtros?: {
    dimension?: "catalogo" | "colegio" | "global";
    dimensionId?: string;
    desde?: string;
  }): Promise<SerieMetricas> {
    const params = new URLSearchParams();
    if (filtros?.dimension) params.set("dimension", filtros.dimension);
    if (filtros?.dimensionId) params.set("dimension_id", filtros.dimensionId);
    if (filtros?.desde) params.set("desde", filtros.desde);
    const cola = params.toString();
    return this.pedir<SerieMetricas>(`/v1/operacion/metricas${cola ? `?${cola}` : ""}`);
  }
}
