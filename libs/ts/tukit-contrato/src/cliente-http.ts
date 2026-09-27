// Cliente HTTP contra el backend real, sobre `/v1`.
//
// Corre SOLO en el servidor de Next: la URL del backend no sale al navegador
// y el tiempo de espera largo que el pipeline necesita no se puede pedir desde
// un `rewrite`, que corta a los 30 s. Es la misma razon que ya estaba escrita
// en el proxy del prototipo, y se conserva.

import { GRADOS_CANONICOS } from "./contrato";
import type {
  AcudienteResumen,
  AltaProducto,
  AplicarCanonico,
  Checkout,
  ColaAdmin,
  Contacto,
  DecisionRevision,
  EstadoTrabajo,
  GradoCanonico,
  SolicitudCheckout,
  HijoSubida,
  Kit,
  LineaKit,
  MarcarNoDisponible,
  PercepcionCruda,
  Preferencias,
  ProductoDadoDeAlta,
  ProductoKit,
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
  ColegioDetalle,
  ColegioEditable,
  ColegioNuevoEditable,
  ConceptoCatalogo,
  DatosColegioNuevo,
  FiltrosListasAdmin,
  FiltrosProductos,
  ItemListaEditable,
  ItemRevision,
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
import type { Pedido, TableroComercio } from "./comercio";
import type { MetricasColegio, SerieMetricas } from "./metricas";
import type { BandejaOperacion, Caso, CasoCreado, SolicitudCaso } from "./operacion";
import {
  ErrorTukit,
  type ArchivoLista,
  type Credenciales,
  type NuevaCuenta,
  type OrigenDatos,
  type Sesion,
} from "./origen";

// El pipeline tarda minutos, no segundos, y eso es deliberado (§0).
const TIEMPO_MAXIMO_MS = 300_000;

function ordenGrado(a: string, b: string): number {
  const ia = GRADOS_CANONICOS.indexOf(a);
  const ib = GRADOS_CANONICOS.indexOf(b);
  // Un grado que no esté en la lista canónica va al final, en orden alfabético.
  if (ia === -1 && ib === -1) return a.localeCompare(b);
  if (ia === -1) return 1;
  if (ib === -1) return -1;
  return ia - ib;
}

export interface OpcionesCliente {
  urlBase: string;
  tiempoMaximoMs?: number;
}

export class ClienteApi implements OrigenDatos {
  readonly nombre = "api" as const;
  private readonly urlBase: string;
  private readonly tiempoMaximoMs: number;

  constructor(opciones: OpcionesCliente) {
    this.urlBase = opciones.urlBase.replace(/\/+$/, "");
    this.tiempoMaximoMs = opciones.tiempoMaximoMs ?? TIEMPO_MAXIMO_MS;
  }

  private async pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
    let respuesta: Response;
    try {
      respuesta = await fetch(`${this.urlBase}${ruta}`, {
        ...init,
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
      const detalle = (cuerpo ?? {}) as Record<string, unknown>;
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

  // El Bearer de la sesion del acudiente cuando el Route Handler lo reenvia
  // desde la cookie; vacio en el flujo anonimo. Se esparce sobre las cabeceras.
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

  // ------------------------------------------------------------ §Identidad
  //
  // El cliente NO habla con identidad directamente: pega al gateway
  // (`urlBase`), y el gateway rutea a identidad `/v1/sesiones*`, valida el
  // token y compara `version_permisos` (§1, edges C4 web→gateway→identidad).
  // El error 503 de `pedir` ("levanta los servicios") cubre el login cuando el
  // backend esta caido, gratis.
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

  // ------------------------------------------------------------------ §2, §4
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

    // Entrada (b): `multipart/form-data` con el JSON en el campo `hijos` y un
    // `archivo` por hijo, tal como lo escribe el §2.
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

  async consultarTrabajo(trabajoId: string): Promise<Trabajo> {
    const crudo = await this.pedir<Trabajo>(`/v1/trabajos/${encodeURIComponent(trabajoId)}`);
    return normalizarTrabajo(crudo);
  }

  // §2 — la subida de listas de un acudiente. `multipart/form-data` hacia
  // inteligencia: `hijos` y `contacto` como JSON, y un `archivo`+`referencia`
  // por hijo APAREADOS por orden, igual que `crearTrabajo` con archivos.
  // Inteligencia percibe cada PDF y lo importa como version pendiente; devuelve
  // a que version quedo ligado cada hijo. No crea un trabajo.
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
    // Las preferencias del paso 3 son del HOGAR: viajan una vez y quedan con
    // cada version importada, para que el kit de la aprobacion las use.
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

  // ------------------------------------------------------- ASUMIDO (v1.1)
  //
  // El fichero `catalogo.ts` infirio una superficie 1.1 que el backend no
  // implemento tal cual: no hay un `/v1/catalogo` de una pieza, ni colegios
  // colgando de catalogo, ni una lista por `(colegio, grado)`. Lo que SI existe
  // es lo que sirve el corpus real, y a eso se pega el cliente. La reconciliacion
  // vive aqui, en el borde HTTP, para no tocar ni el contrato ni las pantallas.

  // El catalogo de pantalla junta tres lecturas reales y las cose en la forma
  // que el contrato asumio (§12): el resumen curado, las tiendas y —lo que el
  // backend NO sirve de una pieza— los conceptos con sus productos anidados.
  //
  // El backend los separa a proposito: `/v1/catalogo/conceptos` devuelve el
  // concepto con `productos` como un CONTEO, no como el arreglo que el contrato
  // pide; el arreglo solo existe producto a producto en `/v1/catalogo/productos`
  // (con `concepto.codigo` en cada fila) y solo trae `ofertas` cuando se pide
  // `con_ofertas=true`. Asi que se traen todos los productos con ofertas y se
  // agrupan aqui por concepto. Es la misma reconciliacion 1.0→1.1 del resto del
  // fichero, en el borde HTTP, para no tocar ni el contrato ni la pantalla.
  async catalogo(): Promise<Catalogo> {
    const [resumen, tiendasResp, conceptosResp, productos] = await Promise.all([
      this.pedir<Catalogo["resumen"]>("/v1/catalogo/resumen"),
      this.pedir<{ tiendas: Catalogo["tiendas"] }>("/v1/catalogo/tiendas"),
      this.pedir<{ conceptos: ConceptoCrudo[] }>("/v1/catalogo/conceptos?por_pagina=200"),
      this.todosLosProductos(),
    ]);

    // Los productos se indexan por su codigo de concepto para colgarlos del
    // concepto al que pertenecen. Un concepto sin productos se queda con `[]`,
    // que es exactamente lo que la pantalla usa para pintarlo como hueco.
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
      // El backend nombra el campo `nombre`; el contrato lo llama
      // `nombre_canonico`. Se acepta cualquiera de los dos.
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

  // Trae TODOS los productos activos con sus ofertas, paginando contra el tope
  // real del backend (200). El corpus tiene ~406, asi que son dos o tres
  // vueltas; se para cuando la pagina viene incompleta o ya se juntaron `total`.
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

  // Identidad sirve los colegios (`/v1/colegios`) y los grados existen aparte
  // (`/v1/grados`), pero los grados VERIFICADOS de un colegio (los que habilitan
  // la ruta rapida "lista oficial") se derivan de las listas REVISADAS reales de
  // catalogo, no del catalogo global de grados: ofrecer un grado sin lista
  // revisada manda al acudiente a un trabajo que falla con `sin_lista_oficial`.
  //
  // Pero el colegio SI se puede elegir aunque no tenga ningun grado revisado: la
  // ruta "subir archivo" (y la sugerencia de alianza) existe justo para el
  // colegio que todavia no es aliado. Antes esto filtraba fuera todo colegio con
  // `grados.length === 0`, y como la semilla deja casi todas las listas sin
  // revisar, el selector mostraba 1 de 17 colegios y el onboarding del admin
  // —que precisamente quiere ver los NO aliados— quedaba vacio. `es_partner`
  // sigue marcando quien tiene grados verificados; la lista ya no se recorta.
  //
  // Los grados verificados se ordenan pedagogicamente; un colegio sin ellos
  // llega con `grados: []` y solo es usable por la ruta de archivo.
  async colegios(): Promise<Colegio[]> {
    const [colegiosResp, listasResp] = await Promise.all([
      this.pedir<{ colegios: { colegio_id: string; nombre: string; logo_url?: string | null }[] }>(
        "/v1/colegios",
      ),
      // El selector arranca VACIO y solo se llena con lo verificado, asi que
      // pedimos `?revisada=true` y el filtro lo resuelve el servidor: una lista
      // importada pero sin revisar no habilita el grado —la ruta rapida a
      // optimizacion solo aplica a listas verificadas—. El tope de página del
      // backend es 200 (POR_PAGINA_MAXIMO); las revisadas caben en una, y si
      // algún día pasan de 200 habría que paginar (por eso se comprueba `total`).
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
          // El backend no lleva la trazabilidad `fuente`/`atribucion_dudosa`
          // (es una senal del cargador de listas, no del dominio); se reportan
          // neutros para no fingir un dato que no existe.
          fuente: "backend",
          atribucion_dudosa: false,
          // El logo lo sirve identidad; `null` cuando el colegio no cargo marca.
          logo_url: c.logo_url ?? null,
          grados,
          es_partner: grados.length > 0,
        };
      });
  }

  // Trae la lista publicada de un (colegio, grado): primero la localiza en el
  // indice `/v1/listas` y luego pide su detalle por id.
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

  // ----------------------------------------------- §Catalogo — admin (P4c)
  //
  // La SPA de administracion del catalogo. `personajes` sale de una lectura
  // dedicada del backend; los tres verbos de escritura pegan al producto por su
  // SKU (PATCH parcial, POST reclasificar, DELETE baja suave) y devuelven la
  // forma de detalle `_producto_publico`, que se normaliza en el borde igual que
  // `normalizarProductoCatalogo`. `buscarProductos` arma el querystring con solo
  // los filtros presentes.
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

  // ------------------------------------ §Catalogo — curaduria proactiva (P4c bis)
  //
  // La cola de curaduria del catalogo, sus altas y sus decisiones. Vive bajo
  // `/v1/admin/catalogo/*` (que el gateway rutea a catalogo), salvo el rechazo,
  // que reusa la ruta ya existente `/v1/admin/propuestas/{id}/rechazar`. El
  // backend envuelve la cola en `{total, propuestas}` y la busqueda en
  // `{candidatos}`; aca se propaga solo el arreglo, igual que `personajes`.
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
    // Ruta EXISTENTE (no estrena prefijo): `/v1/admin/propuestas` ya se rutea a
    // catalogo por su propio prefijo, asi que el rechazo no cuelga de
    // `/v1/admin/catalogo`.
    return this.pedir<{ id: string; estado: string }>(
      `/v1/admin/propuestas/${encodeURIComponent(id)}/rechazar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      },
    );
  }

  // ------------------------------------------------------------------ §7
  async cola(): Promise<ColaAdmin> {
    // El backend responde `{trabajos:[{creado_en, lineas_a_revisar, ...}]}`;
    // el contrato pide `{entradas:[{recibido_en, lineas_pendientes, ...}]}`.
    // Se normaliza aqui, igual que `trabajoAdmin`/`producto`, en vez de dejar
    // el cast crudo (que dejaba `entradas` undefined y reventaba la cola).
    // `colegios`/`grados`/`lineas_totales` no viajan en la cola: viven en
    // catalogo y unirlos aqui cruzaria la frontera de servicios. Se reportan
    // vacios en vez de fingir un dato que este endpoint no tiene.
    const crudo = await this.pedir<{
      trabajos?: {
        trabajo_id: string;
        estado: EstadoTrabajo;
        creado_en: string;
        hijos: number;
        lineas_a_revisar: number;
      }[];
    }>("/v1/admin/cola");
    return {
      entradas: (crudo.trabajos ?? []).map((t) => ({
        trabajo_id: t.trabajo_id,
        estado: t.estado,
        recibido_en: t.creado_en,
        hijos: t.hijos,
        lineas_totales: t.lineas_a_revisar,
        lineas_pendientes: t.lineas_a_revisar,
        colegios: [],
        grados: [],
      })),
    };
  }

  async trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin> {
    const crudo = await this.pedir<TrabajoAdmin>(
      `/v1/admin/trabajos/${encodeURIComponent(trabajoId)}`,
    );
    // El backend ya manda `lineas_pendientes` con el nombre del contrato, asi
    // que no hay remapeo como en `cola()`. El `?? []` es cinturon y tirantes:
    // un backend viejo que lo omita degrada a "sin pendientes" en vez de
    // tumbar el detalle con un `.length` sobre `undefined`.
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
      // `grados`/`preferencias` son recientes: un backend que aún no los sirva
      // no debe romper el panel. Se rellenan vacíos, mismo cinturón que la cola.
      (r.acudientes ?? []).map((a) => ({
        ...(a as AcudienteResumen),
        grados: a.grados ?? [],
        preferencias: a.preferencias ?? {},
      })),
    );
  }

  // Nombres de acudientes ADULTOS por id, para poner cara al panel del colegio.
  // Es PII (§Anexo M): identidad exige `usuario:leer:nombre`, asi que el panel
  // reenvia el Bearer de la sesion del admin (leido de la cookie por el Server
  // Component). Devuelve un mapa id→nombre; un id sin nombre no aparece.
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

  iniciarCheckout(trabajoId: string, cuerpo: SolicitudCheckout): Promise<Checkout> {
    return this.pedir<Checkout>(
      `/v1/trabajos/${encodeURIComponent(trabajoId)}/ordenar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cuerpo),
      },
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

  eliminarTrabajo(trabajoId: string): Promise<void> {
    return this.pedir<void>(`/v1/admin/trabajos/${encodeURIComponent(trabajoId)}`, {
      method: "DELETE",
    });
  }

  // ---------------------------------------------------------- §Onboarding (P2)
  //
  // Inteligencia expone la ruta publica `POST /v1/admin/onboarding` como
  // `multipart/form-data`: el PDF va en `archivo` y el destino (`colegio_id`,
  // `grado`, `anio_lectivo`) en campos aparte, igual que `crearTrabajo` con
  // archivos. Inteligencia percibe y escribe en catalogo por su cuenta; el
  // cliente solo recibe la version creada.
  async onboarding(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo: { contenido: Blob; nombre: string },
  ): Promise<{ version_id: string; grado: string; items: number }> {
    const forma = new FormData();
    forma.append("colegio_id", colegio_id);
    forma.append("grado", grado);
    forma.append("anio_lectivo", String(anio_lectivo));
    forma.append("archivo", archivo.contenido, archivo.nombre);
    return this.pedir<{ version_id: string; grado: string; items: number }>(
      "/v1/admin/onboarding",
      { method: "POST", body: forma },
    );
  }

  // Un acudiente sugiere la lista de su (colegio, grado) cuando no hay una
  // verificada. A diferencia de `onboarding` (multipart hacia inteligencia),
  // esto es JSON hacia catalogo por el gateway: el PDF va en base64 dentro de
  // `evidencia`, y la traza al acudiente es SOLO `contacto_referencia`. Nunca
  // se envia correo ni telefono: esa PII vive solo en identidad.
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

  // Un Blob a base64 sin `data:` prefijo, para meter el PDF en el JSON de la
  // sugerencia. Se lee como bytes y se codifica en bloques para no reventar la
  // pila con `String.fromCharCode(...bytes)` en archivos grandes.
  private async aBase64(blob: Blob): Promise<string> {
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let binario = "";
    const bloque = 0x8000;
    for (let i = 0; i < bytes.length; i += bloque) {
      binario += String.fromCharCode(...bytes.subarray(i, i + bloque));
    }
    return btoa(binario);
  }

  // ------------------------------------------- §Admin — revision de listas (P4)
  //
  // La superficie de escritura que `admin_http.py` sirve bajo `/v1/admin`. El
  // indice y la vista de revision se cosen en el borde a las formas del
  // contrato: el backend anida `concepto` en `{codigo, nombre}` y aca se aplana
  // a `concepto_codigo`/`concepto_nombre`, y el precio de una propuesta ya llega
  // en pesos enteros. Las mutaciones (editar/agregar/cerrar/nueva) mandan JSON y
  // devuelven lo justo que la pantalla necesita para re-pintar.
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
    // `procedencia`/`tiene_contacto` son recientes en el contrato: un backend
    // que aun no los sirva no debe romper la cola. Se rellenan a null/false, el
    // mismo cinturon-y-tirantes que `trabajoAdmin` usa con `lineas_pendientes`.
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
    // El backend responde 200 con `{item_id, actualizado}`; se descarta, el
    // metodo es void y la pantalla re-lee la revision.
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
    // El POST del backend responde 201 con `{item_id, orden}`; solo se propaga
    // `item_id`, que es lo que el contrato promete.
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
    // El backend responde 204 sin cuerpo; guarda 409 `lista_ya_revisada`.
    return this.pedir<void>(
      `/v1/admin/listas/${encodeURIComponent(versionId)}/items/${encodeURIComponent(itemId)}`,
      { method: "DELETE" },
    );
  }

  eliminarVersion(versionId: string): Promise<void> {
    // El backend responde 204 sin cuerpo; guarda 409 `lista_ya_revisada`.
    return this.pedir<void>(`/v1/admin/listas/${encodeURIComponent(versionId)}`, {
      method: "DELETE",
    });
  }

  cerrarLista(versionId: string): Promise<void> {
    // Responde 200 con `{version_id, revisada, ya_estaba?}`; se descarta.
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
    // El backend exige `anio_lectivo` como query y responde 201 con
    // `{version_id, numero, revisada}`; se propaga solo `version_id`.
    const resp = await this.pedir<{ version_id: string; numero?: number; revisada?: boolean }>(
      `/v1/admin/listas/${encodeURIComponent(colegioId)}/${encodeURIComponent(grado)}/nueva-version?anio_lectivo=${anioLectivo}`,
      { method: "POST" },
    );
    return { version_id: resp.version_id };
  }

  async completarColegioDeVersion(
    versionId: string,
    cambios: ColegioNuevoEditable,
  ): Promise<DatosColegioNuevo> {
    // El backend hace merge de los campos presentes sobre `colegio_datos` de la
    // tarea y responde `{version_id, colegio_datos}`; se propaga solo el bloque
    // de datos ya combinado, que es lo que la pantalla vuelve a pintar.
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
    // El directorio alza 404 cuando el DANE no esta (colegio de otra ciudad o
    // escrito a mano); eso NO es un error de la revision, es "no hay que
    // pre-llenar", asi que se degrada a null en vez de propagar.
    try {
      return await this.pedir<DatosColegioNuevo>(
        `/v1/directorio/${encodeURIComponent(dane)}`,
      );
    } catch (causa) {
      if (causa instanceof ErrorTukit && causa.estado === 404) return null;
      throw causa;
    }
  }

  // ------------------------------------------ §Admin — identidad del colegio (P4)
  //
  // El detalle vive en identidad (`/v1/colegios/{id}`) y el PATCH lo sirve el
  // slice que construye la edicion en paralelo. Los dos responden con la misma
  // forma de detalle, que se cose a `ColegioDetalle` en el borde.
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

  // La vista previa de una version curada (region 4). Un slice de backend sirve
  // `POST /v1/admin/onboarding/{version_id}/preview` con el destino en el
  // cuerpo; responde `{trabajo_id, estado}` y se propaga solo `trabajo_id`, que
  // es lo que la pantalla necesita para leer luego `trabajoAdmin(trabajo_id)`.
  // Es el mismo patron de `crearTrabajo` (POST con cuerpo) y `trabajoAdmin`
  // (leer del id devuelto).
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

  // El backlog de sugerencias. Se lee tal cual del backend y se recorta a los
  // campos SEGUROS: nunca correo ni telefono —esa PII vive solo en identidad—.
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

  // La evidencia de una version importada. `documento` es el PDF crudo
  // (`application/pdf`), asi que NO pasa por `pedir` (que espera JSON): se lee
  // como Blob. `percepcion` si es JSON y se cose a `PercepcionCruda` en el
  // borde, tolerando que un item venga con `descripcion` en vez de
  // `texto_original` y que falten `cantidad`/`confianza`.
  async documento(versionId: string): Promise<Blob> {
    let respuesta: Response;
    try {
      respuesta = await fetch(
        `${this.urlBase}/v1/admin/listas/${encodeURIComponent(versionId)}/documento`,
        { signal: AbortSignal.timeout(this.tiempoMaximoMs), cache: "no-store" },
      );
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

  // ------------------------------------------------- ASUMIDO (comercio 1.x)
  pedidos(): Promise<TableroComercio> {
    return this.pedir<TableroComercio>("/v1/comercio/pedidos");
  }

  pedido(pedidoId: string): Promise<Pedido> {
    return this.pedir<Pedido>(`/v1/comercio/pedidos/${encodeURIComponent(pedidoId)}`);
  }

  // El historial del acudiente para su dashboard. Comercio responde
  // `{total, pedidos}`; la pantalla solo usa la lista, asi que se propaga esa.
  async misPedidos(usuarioId: string): Promise<Pedido[]> {
    const resp = await this.pedir<{ total: number; pedidos: Pedido[] }>(
      `/v1/comercio/mis-pedidos?usuario_id=${encodeURIComponent(usuarioId)}`,
    );
    return resp.pedidos ?? [];
  }

  // Las solicitudes de kit del acudiente (trabajos del pipeline). Inteligencia
  // valida la sesion, asi que se identifica por el Bearer que reenvia el Route
  // Handler. Responde `{total, trabajos}`; la pantalla solo usa la lista.
  async misTrabajos(token?: string): Promise<TrabajoResumen[]> {
    const resp = await this.pedir<{ total: number; trabajos: TrabajoResumen[] }>("/v1/trabajos", {
      headers: { ...this.autoriza(token) },
    });
    return resp.trabajos ?? [];
  }

  // ------------------------------------------------ ASUMIDO (operacion 1.x)
  casos(): Promise<BandejaOperacion> {
    return this.pedir<BandejaOperacion>("/v1/operacion/casos");
  }

  caso(casoId: string): Promise<Caso> {
    return this.pedir<Caso>(`/v1/operacion/casos/${encodeURIComponent(casoId)}`);
  }

  crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado> {
    return this.pedir<CasoCreado>("/v1/operacion/casos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(solicitud),
    });
  }

  // -------------------------------------------------------------- Metricas
  // La medida en vivo de un colegio (Inteligencia) y la serie congelada por dia
  // (Operacion). Ambas ya tienen forma de contrato en el backend, asi que se
  // propagan tal cual; los filtros de la serie se traducen a query params.
  metricasColegio(colegioId: string): Promise<MetricasColegio> {
    return this.pedir<MetricasColegio>(
      `/v1/metricas/colegios/${encodeURIComponent(colegioId)}`,
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

// --------------------------------------------------- Normalización de kits
//
// El producto de una línea de kit sale del backend más flaco que el
// `ProductoKit` del contrato: trae un `precio` (o `precio_cop` en las
// alternativas) plano y NO trae `ofertas[]` ni `confianza`. Para que las
// pantallas (que confían en el contrato) funcionen, se rellena aquí la forma
// que falta, sin inventar datos: la oferta sintética lleva el precio real y una
// tienda vacía, y la confianza cae a 1 —el backend ya filtró por debajo de TAU
// o lo mandó a revisión—. Es el mismo trabajo de costura que hace `colegios()`,
// en el mismo borde.

function normalizarProducto(p: unknown): ProductoKit | null {
  if (!p || typeof p !== "object") return null;
  const crudo = p as Record<string, unknown>;
  // El precio viene como `precio` (producto elegido) o `precio_cop`
  // (alternativa); se toma el primero que exista.
  const precio =
    typeof crudo["precio"] === "number"
      ? (crudo["precio"] as number)
      : typeof crudo["precio_cop"] === "number"
        ? (crudo["precio_cop"] as number)
        : null;

  // Si ya trae ofertas (una futura versión del backend), se respetan; si no, se
  // sintetiza una con el precio plano.
  const ofertasCrudas = crudo["ofertas"];
  const ofertas = Array.isArray(ofertasCrudas)
    ? (ofertasCrudas as ProductoKit["ofertas"])
    : precio !== null
      ? [{ tienda: "", precio, vigente_hasta: null }]
      : [];

  return {
    sku: String(crudo["sku"] ?? ""),
    nombre: String(crudo["nombre"] ?? ""),
    marca: (crudo["marca"] as string | null) ?? null,
    nivel: crudo["nivel"] as ProductoKit["nivel"],
    personaje: (crudo["personaje"] as string | null) ?? null,
    imagen_url: (crudo["imagen_url"] as string | null) ?? null,
    confianza: typeof crudo["confianza"] === "number" ? (crudo["confianza"] as number) : 1,
    ofertas,
  };
}

function normalizarLinea(linea: LineaKit): LineaKit {
  return {
    ...linea,
    producto_elegido: normalizarProducto(linea.producto_elegido),
    alternativas: Array.isArray(linea.alternativas)
      ? linea.alternativas.map(normalizarProducto).filter((p): p is ProductoKit => p !== null)
      : [],
  };
}

function normalizarKit(kit: Kit): Kit {
  return { ...kit, lineas: (kit.lineas ?? []).map(normalizarLinea) };
}

function normalizarTrabajo(trabajo: Trabajo): Trabajo {
  return { ...trabajo, kits: (trabajo.kits ?? []).map(normalizarKit) };
}

// --------------------------------------------- Normalización del catálogo
//
// Las formas crudas que sirve el backend de catálogo. Se declaran laxas (todo
// opcional) porque son lo que entra por HTTP, no lo que el contrato promete: el
// concepto viene con `productos` como conteo (que se ignora), y el producto
// solo trae `ofertas` cuando se pidió `con_ofertas=true`. `catalogo()` las cose
// en `ConceptoCatalogo`/`ProductoCatalogo`.

interface ConceptoCrudo {
  codigo: string;
  nombre_canonico?: string;
  nombre?: string;
  sinonimos?: string[];
  categoria: string;
  tipo_item: ConceptoCatalogo["tipo_item"];
  atributos_discriminantes?: string[];
  atributos_descriptivos?: string[];
  admite_personaje?: boolean;
  frecuencia_demanda?: number;
}

interface ProductoCrudo {
  sku: string;
  ean?: string | null;
  nombre: string;
  descripcion?: string | null;
  marca?: string | null;
  nivel: ProductoCatalogo["nivel"];
  personaje?: string | null;
  imagen_url?: string | null;
  atributos?: Record<string, unknown>;
  quality_score?: number;
  es_propio?: boolean;
  concepto?: { codigo: string; nombre: string } | null;
  ofertas?: OfertaCatalogo[];
  // Solo los sirve `_producto_publico` (detalle o busqueda paginada), no el
  // producto colgado de un concepto en `/v1/catalogo/conceptos`.
  unidad_base?: ProductoCatalogoDetalle["unidad_base"];
  unidades_por_empaque?: number;
  precio_desde?: number | null;
  tiendas?: number;
}

interface PersonajeCrudo {
  nombre: string;
  productos?: number;
  conceptos?: string[];
}

function normalizarProductoCatalogo(p: ProductoCrudo): ProductoCatalogo {
  return {
    sku: p.sku,
    ean: p.ean ?? null,
    nombre: p.nombre,
    descripcion: p.descripcion ?? null,
    marca: p.marca ?? null,
    nivel: p.nivel,
    personaje: p.personaje ?? null,
    imagen_url: p.imagen_url ?? null,
    atributos: p.atributos ?? {},
    quality_score: typeof p.quality_score === "number" ? p.quality_score : 0,
    es_propio: Boolean(p.es_propio),
    // Sin `con_ofertas=true` el backend no adjunta el arreglo; la pantalla
    // recorre `ofertas` en varios sitios, así que se garantiza que exista.
    ofertas: Array.isArray(p.ofertas) ? p.ofertas : [],
  };
}

// La forma de detalle (`_producto_publico`): el producto normalizado MAS los
// campos que solo llegan con la busqueda paginada o el detalle puntual. Un
// backend que aun no los sirva cae a valores neutros y el precio se deriva de
// las ofertas, igual que `precioMasBarato`, para no fingir un dato ausente.
function normalizarProductoDetalle(p: ProductoCrudo): ProductoCatalogoDetalle {
  const base = normalizarProductoCatalogo(p);
  const ofertados = base.ofertas
    .map((o) => o.precio)
    .filter((x): x is number => typeof x === "number");
  const precioDesde =
    typeof p.precio_desde === "number"
      ? p.precio_desde
      : ofertados.length > 0
        ? Math.min(...ofertados)
        : null;
  return {
    ...base,
    unidad_base: p.unidad_base ?? "unidad",
    unidades_por_empaque:
      typeof p.unidades_por_empaque === "number" ? p.unidades_por_empaque : 1,
    concepto: p.concepto ?? { codigo: "", nombre: "" },
    precio_desde: precioDesde,
    tiendas: typeof p.tiendas === "number" ? p.tiendas : base.ofertas.length,
  };
}

// ------------------------------------------ Normalización de la revision (P4)
//
// Las formas crudas que sirve `admin_http.py`. El renglon (`_item_publico`) y
// la propuesta anidan el concepto; aca se aplana el renglon a
// `concepto_codigo`/`concepto_nombre` y se deja la propuesta como el contrato
// la promete (crudo). El colegio (`ver_colegio` de identidad) y la sugerencia
// se declaran laxos porque entran por HTTP.

interface ItemRevisionCrudo {
  item_id: string;
  orden: number;
  texto_original: string;
  cantidad: number;
  unidad?: ItemRevision["unidad"];
  tipo_item: ItemRevision["tipo_item"];
  modo_adquisicion?: ItemRevision["modo_adquisicion"];
  instruccion_colegio?: string | null;
  url_externa?: string | null;
  atributos?: Record<string, unknown>;
  requiere_revision?: boolean;
  concepto?: { codigo: string; nombre: string } | null;
}

interface PropuestaRevisionCruda {
  id: string;
  texto_origen: string;
  item_id?: string | null;
  nombre: string;
  marca?: string | null;
  imagen_url?: string | null;
  precio?: number | null;
  nivel_sugerido?: PropuestaRevision["nivel_sugerido"];
  puntaje?: number;
  concepto?: { codigo: string; nombre: string } | { sugerido: string | null };
}

interface RevisionCruda {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  revisada?: boolean;
  items?: ItemRevisionCrudo[];
  propuestas?: PropuestaRevisionCruda[];
  colegio_datos?: DatosColegioNuevo | null;
}

interface ColegioDetalleCrudo {
  colegio_id: string;
  nombre: string;
  logo_url?: string | null;
  sitio_web?: string | null;
  contacto_nombre?: string | null;
  contacto_email?: string | null;
  contacto_telefono?: string | null;
  direccion?: string | null;
  sedes?: { sede_id: string; nombre: string }[];
}

interface SugerenciaCruda {
  tarea_id: string;
  estado: string;
  colegio_id?: string | null;
  grado?: string | null;
  anio_lectivo?: number | null;
  contacto_referencia?: string | null;
  tiene_documento?: boolean;
}

function normalizarItemRevision(i: ItemRevisionCrudo): ItemRevision {
  return {
    id: i.item_id,
    orden: i.orden,
    texto_original: i.texto_original,
    cantidad: i.cantidad,
    unidad: i.unidad ?? null,
    tipo_item: i.tipo_item,
    modo_adquisicion: i.modo_adquisicion ?? null,
    instruccion_colegio: i.instruccion_colegio ?? null,
    url_externa: i.url_externa ?? null,
    atributos: i.atributos ?? {},
    requiere_revision: Boolean(i.requiere_revision),
    concepto_codigo: i.concepto?.codigo ?? null,
    concepto_nombre: i.concepto?.nombre ?? null,
  };
}

function normalizarPropuestaRevision(p: PropuestaRevisionCruda): PropuestaRevision {
  return {
    id: p.id,
    texto_origen: p.texto_origen,
    item_id: p.item_id ?? null,
    nombre: p.nombre,
    marca: p.marca ?? null,
    imagen_url: p.imagen_url ?? null,
    precio: typeof p.precio === "number" ? p.precio : null,
    nivel_sugerido: p.nivel_sugerido ?? null,
    puntaje: typeof p.puntaje === "number" ? p.puntaje : 0,
    concepto: p.concepto ?? { sugerido: null },
  };
}

// El cuerpo de editar/agregar un renglon: se traduce `concepto` (el codigo del
// contrato) al `concepto_codigo` que `_valores_de_renglon` espera, y se manda
// solo lo que vino (los `undefined` no viajan porque `JSON.stringify` los omite).
function cuerpoItem(item: ItemListaEditable): Record<string, unknown> {
  const cuerpo: Record<string, unknown> = {
    texto_original: item.texto_original,
    cantidad: item.cantidad,
    unidad: item.unidad,
    tipo_item: item.tipo_item,
    modo_adquisicion: item.modo_adquisicion,
    instruccion_colegio: item.instruccion_colegio,
    url_externa: item.url_externa,
    atributos: item.atributos,
    requiere_revision: item.requiere_revision,
  };
  if ("concepto" in item) cuerpo["concepto_codigo"] = item.concepto;
  return cuerpo;
}
