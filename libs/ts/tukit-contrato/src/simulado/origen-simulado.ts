// El origen simulado: la misma interfaz que el cliente HTTP, alimentada por
// las semillas del repositorio.
//
// Respeta el ciclo asincrono del §0 en vez de devolver los kits de una: el
// trabajo pasa por `encolado`, `procesando` y `espera_revision`, y solo llega
// a `publicado` cuando alguien lo aprueba en `apps/admin`. Si el acudiente
// nunca viera la espera, la pantalla de espera no se podria probar y el dia
// que el backend real tarde tres minutos se descubriria que no existe.
//
// Los tiempos son segundos y no minutos para que se pueda mirar; se ajustan
// con `TUKIT_SIMULADO_SEGUNDOS`.

import { randomUUID } from "node:crypto";
import type {
  AltaProducto,
  ColaAdmin,
  DecisionRevision,
  Etapa,
  EstadoTrabajo,
  MarcarNoDisponible,
  NombreEtapa,
  PercepcionCruda,
  ProductoDadoDeAlta,
  SinCoincidencia,
  SolicitudTrabajo,
  Trabajo,
  TrabajoAdmin,
  TrabajoCreado,
  ValidarLinea,
} from "../contrato";
import { ETAPAS } from "../contrato";
import type {
  Catalogo,
  Colegio,
  ColegioDetalle,
  ColegioEditable,
  ConceptoCatalogo,
  FiltrosListasAdmin,
  FiltrosProductos,
  ItemListaEditable,
  ItemRevision,
  ListaOficial,
  PaginaProductos,
  Personaje,
  ProductoCatalogo,
  ProductoCatalogoDetalle,
  ProductoEditable,
  PropuestaRevision,
  RevisionLista,
  SedeColegio,
  Sugerencia,
  VersionListaAdmin,
} from "../catalogo";
import { precioMasBarato } from "../catalogo";
import type { Pedido, TableroComercio } from "../comercio";
import type {
  BandejaOperacion,
  Caso,
  CasoCreado,
  CategoriaCaso,
  Prioridad,
  SolicitudCaso,
} from "../operacion";
import { CATEGORIAS_CASO_ACUDIENTE } from "../operacion";
import {
  ErrorTukit,
  type ArchivoLista,
  type Credenciales,
  type OrigenDatos,
  type Sesion,
} from "../origen";
import { CATALOGO, COLEGIOS, listaDe, resolverConcepto } from "./semillas";
import {
  leerTokenSimulado,
  sesionDe,
  tokenSimulado,
  usuarioPorCorreo,
} from "./usuarios";
import { armarKits, degradacionesDe, recomendar, resolverSolicitud } from "./armar";
import {
  actualizar,
  guardar,
  guardarCaso,
  listar,
  obtener,
  type RegistroTrabajo,
} from "./almacen";
import {
  derivarBandeja,
  derivarCaso,
  derivarPedido,
  derivarTablero,
} from "./back-office";

const SEGUNDOS = Number(process.env["TUKIT_SIMULADO_SEGUNDOS"] ?? 12);
// Reparto del tiempo entre etapas, proporcional a lo que cuesta cada una en el
// pipeline real (resolucion es la cara).
const PESO_ETAPA: Record<NombreEtapa, number> = {
  percepcion: 0.18,
  normalizacion: 0.07,
  resolucion: 0.5,
  optimizacion: 0.25,
};

// `false` deja el trabajo en `espera_revision` para siempre, que es el
// comportamiento fiel al contrato: publicar es una decision de una persona.
// Por defecto se auto-aprueba para que la usuaria pueda recorrer el flujo
// completo sin abrir `apps/admin` en otra ventana.
const AUTOAPROBAR = process.env["TUKIT_SIMULADO_AUTOAPROBAR"] !== "false";
const SEGUNDOS_AUTOAPROBACION = Number(process.env["TUKIT_SIMULADO_SEGUNDOS_REVISION"] ?? 8);

// El almacen en memoria de las listas que "inteligencia" habria importado por
// onboarding. No hay percepcion real que corra en el simulado, asi que se
// deriva de la lista oficial del corpus para ese (colegio, grado): sus renglones
// se reparten en dos "paginas" crudas y se itemizan con una confianza sintetica
// alta, que es lo que un revisor veria tras un percibir exitoso. Vive a nivel de
// modulo (no de instancia) para que el detalle sobreviva entre requests, igual
// que el `almacen` de trabajos.
interface VersionImportada {
  version_id: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  numero: number;
  // Nace SIN revisar, igual que `importar_lista` del backend: la percepcion es
  // una hipotesis que un revisor cura antes de que salga al acudiente. `cerrar`
  // la marca revisada; sobre una revisada NO se puede editar (409).
  revisada: boolean;
  documento: Blob;
  percepcion: PercepcionCruda;
  // Los renglones de la revision, derivados de la lista del corpus al importar y
  // luego mutados por editar/agregar. Sobreviven a nivel de la version (no se
  // recomputan) para que un edit persista entre requests.
  items: ItemRevision[];
  // El correlativo de renglones nuevos, para no chocar `orden` al agregar.
  siguiente_orden: number;
}

const VERSIONES = new Map<string, VersionImportada>();

// El backlog de sugerencias de padres (P3c). Un acudiente cuyo (colegio, grado)
// no tiene lista verificada la sugiere aqui; en el backend real es una
// `tarea_importacion` 'pendiente' con origen 'sugerencia_padre'. Se guarda al
// nivel de modulo, como los trabajos y las versiones, para que el asiento
// sobreviva entre requests. NO se guarda correo ni telefono: solo el
// `contacto_referencia` (el usuario_id), fiel a que la PII vive en identidad.
interface SugerenciaEncolada {
  tarea_id: string;
  estado: string;
  colegio_id: string;
  grado: string;
  anio_lectivo: number;
  contacto_referencia: string | null;
  tiene_documento: boolean;
}

const SUGERENCIAS: SugerenciaEncolada[] = [];

// Los SKU dados de baja (borrado suave) por la SPA de admin. No se borran de la
// semilla —que es de solo lectura y compartida— sino que se ocultan del
// listado, igual que el `AD-05` real apaga la oferta sin destruir el registro.
// Vive a nivel de modulo para sobrevivir entre requests, como el resto.
const PRODUCTOS_ELIMINADOS = new Set<string>();

// Los parches en memoria a los productos de la semilla (PATCH y reclasificar).
// La semilla no se puede mutar (es JSON importado y compartido), asi que los
// cambios se guardan aparte y se aplican encima al leer. `concepto` mueve el
// producto bajo otro codigo de concepto.
interface ParcheProducto {
  cambios: ProductoEditable;
  concepto?: string;
}

const PARCHES = new Map<string, ParcheProducto>();

// Los parches en memoria a la identidad de un colegio (`editarColegio`). La
// semilla de colegios es de solo lectura (no trae contacto ni sitio); los
// cambios del administrador se guardan aparte y se aplican al leer el detalle,
// igual que `PARCHES` con los productos. Vive a nivel de modulo para sobrevivir
// entre requests.
const PARCHES_COLEGIO = new Map<string, ColegioEditable>();

/** Localiza un producto de la semilla y el concepto que lo contiene. */
function ubicarProducto(
  sku: string,
): { producto: ProductoCatalogo; concepto: ConceptoCatalogo } | null {
  for (const concepto of CATALOGO.conceptos) {
    for (const producto of concepto.productos) {
      if (producto.sku === sku) return { producto, concepto };
    }
  }
  return null;
}

/** El concepto efectivo de un producto: el reclasificado si hay parche, si no
 *  el que lo contiene en la semilla. */
function conceptoEfectivo(sku: string, contenedor: ConceptoCatalogo): ConceptoCatalogo {
  const destino = PARCHES.get(sku)?.concepto;
  if (!destino) return contenedor;
  return CATALOGO.conceptos.find((c) => c.codigo === destino) ?? contenedor;
}

/** Cose la forma de detalle (`_producto_publico`) para un producto de la
 *  semilla, aplicando el parche en memoria si existe. */
function detalleProducto(
  producto: ProductoCatalogo,
  contenedor: ConceptoCatalogo,
): ProductoCatalogoDetalle {
  const cambios = PARCHES.get(producto.sku)?.cambios ?? {};
  const fusionado: ProductoCatalogo = {
    ...producto,
    ...("nombre" in cambios && cambios.nombre !== undefined
      ? { nombre: cambios.nombre }
      : {}),
    ...("descripcion" in cambios ? { descripcion: cambios.descripcion ?? null } : {}),
    ...("marca" in cambios ? { marca: cambios.marca ?? null } : {}),
    ...("nivel" in cambios && cambios.nivel !== undefined ? { nivel: cambios.nivel } : {}),
    ...("personaje" in cambios ? { personaje: cambios.personaje ?? null } : {}),
    ...("imagen_url" in cambios ? { imagen_url: cambios.imagen_url ?? null } : {}),
    ...("atributos" in cambios && cambios.atributos !== undefined
      ? { atributos: cambios.atributos }
      : {}),
    ...("quality_score" in cambios && cambios.quality_score !== undefined
      ? { quality_score: cambios.quality_score }
      : {}),
    ...("es_propio" in cambios && cambios.es_propio !== undefined
      ? { es_propio: cambios.es_propio }
      : {}),
  };
  const concepto = conceptoEfectivo(producto.sku, contenedor);
  // La semilla no lleva unidad/empaque por producto; se derivan de los mismos
  // atributos que usa `unidadesDeEmpaque`, con el parche encima si lo hubo.
  const declaradas = fusionado.atributos["cantidades_declaradas"];
  let unidades = cambios.unidades_por_empaque ?? 1;
  if (cambios.unidades_por_empaque === undefined && Array.isArray(declaradas)) {
    for (const token of declaradas) {
      const m = /^(\d+):unidades$/.exec(String(token));
      if (m?.[1]) {
        unidades = Number(m[1]);
        break;
      }
    }
  }
  return {
    ...fusionado,
    unidad_base: cambios.unidad_base ?? "unidad",
    unidades_por_empaque: unidades,
    concepto: { codigo: concepto.codigo, nombre: concepto.nombre_canonico },
    precio_desde: precioMasBarato(fusionado),
    tiendas: fusionado.ofertas.length,
  };
}

/** Todos los productos vivos (no eliminados) en forma de detalle, respetando la
 *  reclasificacion: un producto reclasificado se lista bajo su concepto nuevo. */
function productosVivos(): ProductoCatalogoDetalle[] {
  const salida: ProductoCatalogoDetalle[] = [];
  for (const concepto of CATALOGO.conceptos) {
    for (const producto of concepto.productos) {
      if (PRODUCTOS_ELIMINADOS.has(producto.sku)) continue;
      salida.push(detalleProducto(producto, concepto));
    }
  }
  return salida;
}

/** Solo para pruebas del contrato: el backlog de sugerencias en memoria. */
export function _sugerenciasEncoladas(): readonly SugerenciaEncolada[] {
  return SUGERENCIAS;
}

function transcurrido(registro: RegistroTrabajo): number {
  return (Date.now() - registro.base_ms) / 1000;
}

function estadoDe(registro: RegistroTrabajo): EstadoTrabajo {
  if (registro.aprobado) return "publicado";
  const t = transcurrido(registro);
  if (t < SEGUNDOS * 0.15) return "encolado";
  if (t < SEGUNDOS) return "procesando";
  if (AUTOAPROBAR && t >= SEGUNDOS + SEGUNDOS_AUTOAPROBACION) return "publicado";
  return "espera_revision";
}

function etapasDe(registro: RegistroTrabajo): Etapa[] {
  const t = transcurrido(registro);
  let acumulado = 0;
  return ETAPAS.map((nombre) => {
    const duracion = SEGUNDOS * PESO_ETAPA[nombre];
    const inicio = acumulado;
    acumulado += duracion;
    const estado: Etapa["estado"] = t >= acumulado ? "ok" : t > inicio ? "en_curso" : "pendiente";
    const ms = Math.round(
      (estado === "ok" ? duracion : Math.max(0, t - inicio)) * 1000,
    );
    return { nombre, estado, ms };
  });
}

function ajustesDe(registro: RegistroTrabajo) {
  return {
    validadas: registro.validadas,
    sinCoincidencia: registro.sin_coincidencia,
    skusNoDisponibles: registro.skus_no_disponibles,
  };
}

function construir(registro: RegistroTrabajo): Trabajo {
  const estado = estadoDe(registro);
  const resueltos = resolverSolicitud(registro.solicitud);
  const kits = armarKits(registro.solicitud, resueltos, ajustesDe(registro));

  return {
    trabajo_id: registro.trabajo_id,
    estado,
    etapas: etapasDe(registro),
    // Mientras no este publicado, `kits` va vacio: el acudiente nunca ve un
    // kit sin revisar (§4).
    kits: estado === "publicado" ? kits : [],
    recomendado:
      estado === "publicado"
        ? recomendar(kits, registro.solicitud.preferencias, registro.solicitud.hijos.length)
        : null,
    degradaciones: estado === "publicado" ? degradacionesDe(kits) : [],
  };
}

export class OrigenSimulado implements OrigenDatos {
  readonly nombre = "simulado" as const;

  // ------------------------------------------------------------ §Identidad
  async iniciarSesion(cred: Credenciales): Promise<{ sesion: Sesion; token: string }> {
    const u = usuarioPorCorreo(cred.correo);
    // El simulado NO verifica la clave: identidad hoy tampoco tiene una
    // credencial utilizable (`clave_hash="sin-credencial"`, ver api.py). Se
    // acepta cualquier clave para un correo sembrado y se dice en pantalla,
    // para no fingir un control de acceso que el backend aun no ofrece.
    if (!u) {
      throw new ErrorTukit(
        401,
        "credenciales_invalidas",
        "Ese correo no está en el corpus de demostración.",
        { campo: "correo" },
      );
    }
    return { sesion: sesionDe(u), token: tokenSimulado(u.correo) };
  }

  async sesionActual(token: string): Promise<Sesion | null> {
    const correo = leerTokenSimulado(token);
    const u = correo ? usuarioPorCorreo(correo) : null;
    return u ? sesionDe(u) : null;
  }

  async cerrarSesion(_token: string): Promise<void> {
    // La cookie la borra el Route Handler; el token simulado no tiene estado
    // en servidor que invalidar.
  }

  async crearTrabajo(
    solicitud: SolicitudTrabajo,
    archivos: ArchivoLista[] = [],
  ): Promise<TrabajoCreado> {
    if (!solicitud.contacto?.correo || !solicitud.contacto?.celular) {
      throw new ErrorTukit(
        400,
        "contacto_requerido",
        "Necesitamos tu correo y tu celular para avisarte cuando el kit esté listo.",
        { campo: "contacto" },
      );
    }
    if (solicitud.hijos.length === 0) {
      throw new ErrorTukit(400, "hijos_requeridos", "Agrega al menos un hijo.", {
        campo: "hijos",
      });
    }

    for (const archivo of archivos) {
      // §2.1: un archivo es la lista de UN grado. La senal buena es cuantos
      // grados distintos aparecen, y la reporta el modelo de percepcion, que
      // aqui no corre. El tamano es la misma "guarda barata previa" que el
      // contrato admite, y sirve para que la ruta de error no quede sin
      // probar: los PDF completos del corpus (39 y 22 paginas) caen aqui.
      if (archivo.tamano > 4 * 1024 * 1024) {
        throw new ErrorTukit(
          422,
          "lista_de_varios_grados",
          "Este archivo parece traer la lista de varios grados. Sube solo las páginas del grado de tu hijo.",
          { grados_detectados: [], paginas: 0 },
        );
      }
    }

    // Con archivo no hay percepcion que corra, asi que el origen simulado usa
    // la lista del colegio y el grado que el acudiente ya declaro. Es la
    // unica parte del simulado que no se puede derivar del archivo, y va
    // dicha en pantalla para que no se confunda con el comportamiento real.
    for (const hijo of solicitud.hijos) {
      if (!listaDe(hijo.colegio_id, hijo.grado)) {
        throw new ErrorTukit(
          422,
          "lista_no_encontrada",
          `No tenemos la lista de ${hijo.grado} para ese colegio en el corpus simulado.`,
          { campo: "hijos" },
        );
      }
    }

    const ahora = Date.now();
    const registro: RegistroTrabajo = {
      trabajo_id: randomUUID(),
      solicitud,
      base_ms: ahora,
      creado_ms: ahora,
      origen_entrada: archivos.length > 0 ? "archivo" : "lista_oficial",
      archivos: archivos.map((a) => a.nombre),
      aprobado: false,
      nota_revision: null,
      validadas: [],
      sin_coincidencia: {},
      skus_no_disponibles: [],
      productos_manuales: {},
    };
    guardar(registro);

    return {
      trabajo_id: registro.trabajo_id,
      estado: "encolado",
      estimado_segundos: Math.round(SEGUNDOS + SEGUNDOS_AUTOAPROBACION),
      consultar_en: `/v1/trabajos/${registro.trabajo_id}`,
    };
  }

  async consultarTrabajo(trabajoId: string): Promise<Trabajo> {
    const registro = obtener(trabajoId);
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
    return construir(registro);
  }

  async catalogo(): Promise<Catalogo> {
    return CATALOGO;
  }

  async colegios(): Promise<Colegio[]> {
    return COLEGIOS;
  }

  async listaOficial(colegioId: string, grado: string): Promise<ListaOficial> {
    const lista = listaDe(colegioId, grado);
    if (!lista) {
      throw new ErrorTukit(404, "lista_no_existe", "No tenemos esa lista todavía.");
    }
    return lista;
  }

  // ----------------------------------------------- §Catalogo — admin (P4c)
  async personajes(): Promise<Personaje[]> {
    // Se agrega sobre los productos VIVOS: cada personaje distinto con su
    // conteo y los conceptos bajo los que aparece. Los productos sin personaje
    // (`null`) no cuentan.
    const porNombre = new Map<string, { productos: number; conceptos: Set<string> }>();
    for (const p of productosVivos()) {
      const nombre = p.personaje;
      if (!nombre) continue;
      const entrada = porNombre.get(nombre) ?? { productos: 0, conceptos: new Set<string>() };
      entrada.productos += 1;
      // El codigo del concepto (C001, C009, ...) y no su nombre: es lo que el
      // backend real emite y lo que la compuerta de 4 anclas del /empezar
      // compara. Con el nombre, la compuerta pasaria contra el API y fallaria
      // en silencio contra el simulado.
      if (p.concepto.codigo) entrada.conceptos.add(p.concepto.codigo);
      porNombre.set(nombre, entrada);
    }
    return [...porNombre.entries()]
      .map(([nombre, v]) => ({
        nombre,
        productos: v.productos,
        conceptos: [...v.conceptos].sort(),
      }))
      // Por nombre ascendente, igual que el backend (api.py ordena por nombre).
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }

  async buscarProductos(filtros: FiltrosProductos): Promise<PaginaProductos> {
    let items = productosVivos();
    if (filtros.concepto) items = items.filter((p) => p.concepto.codigo === filtros.concepto);
    if (filtros.nivel) items = items.filter((p) => p.nivel === filtros.nivel);
    if (filtros.personaje) items = items.filter((p) => p.personaje === filtros.personaje);
    if (filtros.con_personaje !== undefined)
      items = items.filter((p) => (p.personaje !== null) === filtros.con_personaje);
    if (filtros.con_precio !== undefined)
      items = items.filter((p) => (p.precio_desde !== null) === filtros.con_precio);
    if (filtros.con_ofertas !== undefined)
      items = items.filter((p) => (p.ofertas.length > 0) === filtros.con_ofertas);
    if (filtros.busqueda?.trim()) {
      const q = filtros.busqueda.toLowerCase();
      items = items.filter(
        (p) =>
          p.nombre.toLowerCase().includes(q) ||
          (p.marca ?? "").toLowerCase().includes(q) ||
          p.sku.toLowerCase().includes(q),
      );
    }

    const total = items.length;
    const porPagina = filtros.por_pagina ?? 24;
    const pagina = filtros.pagina ?? 1;
    const desde = (pagina - 1) * porPagina;
    return {
      total,
      pagina,
      por_pagina: porPagina,
      productos: items.slice(desde, desde + porPagina),
    };
  }

  async editarProducto(
    sku: string,
    cambios: ProductoEditable,
  ): Promise<ProductoCatalogoDetalle> {
    const ubicado = this.exigirProducto(sku);
    const previo: ParcheProducto = PARCHES.get(sku) ?? { cambios: {} };
    PARCHES.set(sku, { ...previo, cambios: { ...previo.cambios, ...cambios } });
    const contenedor = conceptoEfectivo(sku, ubicado.concepto);
    return detalleProducto(ubicado.producto, contenedor);
  }

  async reclasificarProducto(
    sku: string,
    concepto: string,
  ): Promise<ProductoCatalogoDetalle> {
    const ubicado = this.exigirProducto(sku);
    if (!CATALOGO.conceptos.some((c) => c.codigo === concepto)) {
      throw new ErrorTukit(
        404,
        "concepto_no_existe",
        "Ese concepto no está en el catálogo.",
        { campo: "concepto" },
      );
    }
    const previo: ParcheProducto = PARCHES.get(sku) ?? { cambios: {} };
    PARCHES.set(sku, { ...previo, cambios: previo.cambios, concepto });
    return detalleProducto(ubicado.producto, conceptoEfectivo(sku, ubicado.concepto));
  }

  async eliminarProducto(sku: string): Promise<void> {
    this.exigirProducto(sku);
    PRODUCTOS_ELIMINADOS.add(sku);
  }

  // Un producto de la semilla vivo, o 404. Centraliza la guarda de los tres
  // verbos de escritura del catalogo.
  private exigirProducto(sku: string): { producto: ProductoCatalogo; concepto: ConceptoCatalogo } {
    if (PRODUCTOS_ELIMINADOS.has(sku)) {
      throw new ErrorTukit(404, "producto_no_existe", "Ese producto ya no está en el catálogo.");
    }
    const ubicado = ubicarProducto(sku);
    if (!ubicado) {
      throw new ErrorTukit(404, "producto_no_existe", "Ese producto no existe en el catálogo.");
    }
    return ubicado;
  }

  async cola(): Promise<ColaAdmin> {
    const entradas = listar()
      .map((registro) => {
        const trabajo = construir(registro);
        const resueltos = resolverSolicitud(registro.solicitud);
        const kits = armarKits(registro.solicitud, resueltos, ajustesDe(registro));
        const referencia = kits[0];
        const lineas = referencia?.lineas ?? [];
        return {
          trabajo_id: registro.trabajo_id,
          estado: trabajo.estado,
          recibido_en: new Date(registro.creado_ms).toISOString(),
          hijos: registro.solicitud.hijos.length,
          lineas_totales: lineas.length,
          lineas_pendientes: lineas.filter(
            (l) =>
              l.estado_resolucion === "AMBIGUO" ||
              l.estado_resolucion === "SIN_MATCH" ||
              l.estado_resolucion === "HUECO_CATALOGO",
          ).length,
          colegios: [...new Set(registro.solicitud.hijos.map((h) => h.colegio_id))],
          grados: [...new Set(registro.solicitud.hijos.map((h) => h.grado))],
        };
      })
      // Lo que ya se publico sale de la cola; lo demas se ordena por lo que
      // mas trabajo pide, que es lo que `AD-01` quiere priorizar.
      .sort((a, b) => b.lineas_pendientes - a.lineas_pendientes);
    return { entradas };
  }

  async trabajoAdmin(trabajoId: string): Promise<TrabajoAdmin> {
    const registro = obtener(trabajoId);
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
    const base = construir(registro);
    const resueltos = resolverSolicitud(registro.solicitud);
    const kits = armarKits(registro.solicitud, resueltos, ajustesDe(registro));
    const referencia = kits[0];

    return {
      ...base,
      // El admin SI ve los kits antes de publicar: esa es su tarea. El §4
      // vacia `kits` para el acudiente, no para la revision (§7, `AD-03`).
      kits,
      recomendado: recomendar(kits, registro.solicitud.preferencias, registro.solicitud.hijos.length),
      degradaciones: degradacionesDe(kits),
      recibido_en: new Date(registro.creado_ms).toISOString(),
      // Nunca el correo: la notificacion lo referencia por identificador.
      contacto_id: `id-${registro.trabajo_id.slice(0, 8)}`,
      lineas_pendientes: (referencia?.lineas ?? [])
        .filter(
          (l) =>
            l.estado_resolucion === "AMBIGUO" ||
            l.estado_resolucion === "SIN_MATCH" ||
            l.estado_resolucion === "HUECO_CATALOGO",
        )
        .map((l) => l.item_id),
      nota_revision: registro.nota_revision,
    };
  }

  async validarLinea(trabajoId: string, itemId: string, _cuerpo: ValidarLinea): Promise<void> {
    const registro = actualizar(trabajoId, (r) => {
      if (!r.validadas.includes(itemId)) r.validadas.push(itemId);
      delete r.sin_coincidencia[itemId];
    });
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
  }

  async marcarSinCoincidencia(
    trabajoId: string,
    itemId: string,
    cuerpo: SinCoincidencia,
  ): Promise<void> {
    if (!cuerpo.motivo?.trim()) {
      throw new ErrorTukit(
        400,
        "motivo_requerido",
        "Escribe por qué no hay coincidencia: una marca sin motivo no se puede revisar después.",
        { campo: "motivo" },
      );
    }
    const registro = actualizar(trabajoId, (r) => {
      r.sin_coincidencia[itemId] = cuerpo.motivo;
      r.validadas = r.validadas.filter((id) => id !== itemId);
    });
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
  }

  async altaProducto(cuerpo: AltaProducto): Promise<ProductoDadoDeAlta> {
    if (!Number.isInteger(cuerpo.precio) || cuerpo.precio <= 0) {
      throw new ErrorTukit(
        400,
        "precio_invalido",
        "El precio va en pesos enteros y tiene que ser positivo.",
        { campo: "precio" },
      );
    }
    const sku = `TK-MAN-${Math.random().toString(36).slice(2, 8).toUpperCase()}`;
    if (cuerpo.trabajo_id && cuerpo.item_id) {
      const itemId = cuerpo.item_id;
      actualizar(cuerpo.trabajo_id, (r) => {
        r.productos_manuales[itemId] = {
          sku,
          nombre: cuerpo.nombre,
          precio: cuerpo.precio,
        };
        if (!r.validadas.includes(itemId)) r.validadas.push(itemId);
        delete r.sin_coincidencia[itemId];
      });
    }
    return { sku };
  }

  async marcarNoDisponible(sku: string, cuerpo: MarcarNoDisponible): Promise<void> {
    if (!cuerpo.motivo?.trim()) {
      throw new ErrorTukit(400, "motivo_requerido", "Di por qué no está disponible.", {
        campo: "motivo",
      });
    }
    // El `AD-05` real apaga la oferta en catalogo, o sea para todos los
    // trabajos. Aqui se propaga a todos los que estan en la cola, que es el
    // efecto observable.
    for (const registro of listar()) {
      actualizar(registro.trabajo_id, (r) => {
        if (!r.skus_no_disponibles.includes(sku)) r.skus_no_disponibles.push(sku);
      });
    }
  }

  async decidirRevision(trabajoId: string, cuerpo: DecisionRevision): Promise<void> {
    const registro = obtener(trabajoId);
    if (!registro) throw new ErrorTukit(404, "trabajo_no_existe", "Ese trabajo no existe.");
    if (registro.aprobado) {
      throw new ErrorTukit(
        409,
        "trabajo_ya_publicado",
        "Este trabajo ya se publicó: no se puede volver a revisar.",
      );
    }
    actualizar(trabajoId, (r) => {
      r.nota_revision = cuerpo.nota ?? null;
      if (cuerpo.decision === "aprobar") {
        r.aprobado = true;
      } else {
        // Devolver reabre el trabajo sin avisar al acudiente: el reloj vuelve
        // a empezar y el estado baja a `procesando`.
        r.base_ms = Date.now();
      }
    });
  }

  // ---------------------------------------------------------- §Onboarding (P2)
  //
  // El simulado no percibe un PDF de verdad: si tiene la lista oficial de ese
  // (colegio, grado) en el corpus, la usa como si el modelo la hubiera leido;
  // asi el revisor de cuatro paneles se puede recorrer sin Gemini. Guarda el
  // documento y la percepcion derivada bajo un `version_id` para que los dos
  // GET los devuelvan despues.
  async onboarding(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo: { contenido: Blob; nombre: string },
  ): Promise<{ version_id: string; grado: string; items: number }> {
    const lista = listaDe(colegio_id, grado);
    if (!lista) {
      throw new ErrorTukit(
        422,
        "lista_no_encontrada",
        `No tenemos la lista de ${grado} para ese colegio en el corpus simulado.`,
        { grados_detectados: [] },
      );
    }

    // Los renglones se reparten en dos paginas crudas, para que la region 2
    // tenga mas de una pagina que cotejar. `crudo` es el texto tal cual, sin
    // itemizar; `items` es lo ya extraido con confianza sintetica alta.
    const mitad = Math.ceil(lista.items.length / 2);
    const paginas = [0, 1].map((p) => ({
      pagina: p + 1,
      crudo: lista.items
        .slice(p * mitad, (p + 1) * mitad)
        .map((it) => `${it.cantidad} ${it.texto_original}`)
        .join("\n"),
    }));
    const items: PercepcionCruda["items"] = lista.items.map((it) => ({
      texto_original: it.texto_original,
      descripcion: it.texto_original,
      cantidad: it.cantidad,
      confianza: 0.92,
    }));

    // Los renglones de la revision se derivan de la lista del corpus y se
    // resuelven a concepto con el mismo `resolverConcepto` del simulado; el que
    // no llega al umbral queda sin concepto y marcado a revision, igual que
    // `importar_lista` con `clasificar`. Se guardan en la version para que las
    // ediciones persistan.
    const itemsRevision: ItemRevision[] = lista.items.map((it, i) => {
      const { concepto, confianza } = resolverConcepto(it.texto_original);
      const resuelto = confianza >= 0.5 ? concepto : null;
      return {
        id: randomUUID(),
        orden: it.orden ?? i + 1,
        texto_original: it.texto_original,
        cantidad: it.cantidad,
        unidad: "unidad",
        tipo_item: it.tipo_item,
        modo_adquisicion: (it.modo_adquisicion as ItemRevision["modo_adquisicion"]) ?? null,
        instruccion_colegio: null,
        url_externa: null,
        atributos: {},
        requiere_revision: resuelto === null,
        concepto_codigo: resuelto?.codigo ?? null,
        concepto_nombre: resuelto?.nombre_canonico ?? null,
      };
    });

    const versionId = randomUUID();
    const numero =
      [...VERSIONES.values()].filter(
        (v) => v.colegio_id === colegio_id && v.grado === grado,
      ).length + 1;
    VERSIONES.set(versionId, {
      version_id: versionId,
      colegio_id,
      grado,
      anio_lectivo,
      numero,
      revisada: false,
      documento: archivo.contenido,
      percepcion: { paginas, items },
      items: itemsRevision,
      siguiente_orden: itemsRevision.length + 1,
    });

    return { version_id: versionId, grado, items: items.length };
  }

  async sugerirColegio(
    colegio_id: string,
    grado: string,
    anio_lectivo: number,
    archivo?: { contenido: Blob; nombre: string },
    contacto_referencia?: string,
  ): Promise<{ tarea_id: string; estado: string }> {
    // Se ANOTA la sugerencia sin echar mano de correo/telefono: solo el
    // identificador del contacto y si venia con documento. El estado nace
    // 'pendiente', igual que la tarea real que un administrador atenderia.
    const tarea_id = randomUUID();
    SUGERENCIAS.push({
      tarea_id,
      estado: "pendiente",
      colegio_id,
      grado,
      anio_lectivo,
      contacto_referencia: contacto_referencia ?? null,
      tiene_documento: archivo !== undefined,
    });
    return { tarea_id, estado: "pendiente" };
  }

  // ----------------------------------------------- §Admin — revision de listas (P4)
  //
  // El indice de versiones a curar sale de las que `onboarding` importo (las que
  // un revisor veria en la cola). La vista de revision lee los renglones que la
  // version guardo; editar/agregar los mutan y `cerrar` la marca revisada. La
  // puerta es la misma que el backend: sobre una version YA revisada no se
  // escribe (409 `lista_ya_revisada`).
  async listasAdmin(filtros: FiltrosListasAdmin = {}): Promise<VersionListaAdmin[]> {
    let versiones = [...VERSIONES.values()];
    if (filtros.revisada !== undefined)
      versiones = versiones.filter((v) => v.revisada === filtros.revisada);
    if (filtros.colegio_id)
      versiones = versiones.filter((v) => v.colegio_id === filtros.colegio_id);
    if (filtros.grado) versiones = versiones.filter((v) => v.grado === filtros.grado);
    if (filtros.anio_lectivo !== undefined)
      versiones = versiones.filter((v) => v.anio_lectivo === filtros.anio_lectivo);
    // Lo sin revisar primero (es lo que pide trabajo), igual que el backend
    // ordena por `revisada_en IS NULL DESC`.
    return versiones
      .sort((a, b) => Number(a.revisada) - Number(b.revisada))
      .map((v) => ({
        version_id: v.version_id,
        colegio_id: v.colegio_id,
        grado: v.grado,
        anio_lectivo: v.anio_lectivo,
        numero: v.numero,
        revisada: v.revisada,
        items: v.items.length,
      }));
  }

  async revisionLista(versionId: string): Promise<RevisionLista> {
    const version = this.exigirVersion(versionId);
    return {
      version_id: version.version_id,
      colegio_id: version.colegio_id,
      grado: version.grado,
      anio_lectivo: version.anio_lectivo,
      numero: version.numero,
      revisada: version.revisada,
      // Los renglones se copian para que quien llame no mute el estado interno.
      items: version.items.map((i) => ({ ...i })),
      // El simulado no corre la cola de propuestas de producto: no hay
      // candidatos pendientes que decidir, asi que la revision nace sin ellos.
      propuestas: [] as PropuestaRevision[],
    };
  }

  async editarItemLista(
    versionId: string,
    itemId: string,
    cambios: ItemListaEditable,
  ): Promise<void> {
    const version = this.exigirSinRevisar(versionId);
    const item = version.items.find((i) => i.id === itemId);
    if (!item) {
      throw new ErrorTukit(404, "item_no_existe", "Ese renglon no esta en esta version.");
    }
    aplicarCambiosItem(item, cambios);
  }

  async agregarItemLista(
    versionId: string,
    item: ItemListaEditable,
  ): Promise<{ item_id: string }> {
    const version = this.exigirSinRevisar(versionId);
    if (!item.texto_original) {
      throw new ErrorTukit(
        422,
        "texto_requerido",
        "Un renglon nuevo necesita texto_original.",
        { campo: "texto_original" },
      );
    }
    const nuevo: ItemRevision = {
      id: randomUUID(),
      orden: version.siguiente_orden,
      texto_original: item.texto_original,
      cantidad: item.cantidad ?? 1,
      unidad: "unidad",
      tipo_item: "util",
      modo_adquisicion: null,
      instruccion_colegio: null,
      url_externa: null,
      atributos: {},
      requiere_revision: item.concepto == null,
      concepto_codigo: null,
      concepto_nombre: null,
    };
    aplicarCambiosItem(nuevo, item);
    version.items.push(nuevo);
    version.siguiente_orden += 1;
    return { item_id: nuevo.id };
  }

  async cerrarLista(versionId: string): Promise<void> {
    const version = this.exigirVersion(versionId);
    // Idempotente, como el backend: cerrar una ya revisada no es error.
    version.revisada = true;
  }

  async nuevaVersion(
    colegioId: string,
    grado: string,
    anioLectivo: number,
  ): Promise<{ version_id: string }> {
    // Clona la ultima version de ese (colegio, grado) en una nueva SIN revisar,
    // igual que el backend clona la vigente para corregir sin borrar el pasado.
    const previas = [...VERSIONES.values()].filter(
      (v) => v.colegio_id === colegioId && v.grado === grado,
    );
    const vigente = previas.sort((a, b) => b.numero - a.numero)[0];
    if (!vigente) {
      throw new ErrorTukit(
        404,
        "lista_no_existe",
        "No hay ninguna lista para ese colegio, grado y ano.",
      );
    }
    const versionId = randomUUID();
    VERSIONES.set(versionId, {
      version_id: versionId,
      colegio_id: colegioId,
      grado,
      anio_lectivo: anioLectivo,
      numero: vigente.numero + 1,
      revisada: false,
      documento: vigente.documento,
      percepcion: vigente.percepcion,
      items: vigente.items.map((i) => ({ ...i, id: randomUUID() })),
      siguiente_orden: vigente.siguiente_orden,
    });
    return { version_id: versionId };
  }

  // Una version importada, o 404. Leer una revisada es legitimo; solo escribir
  // no lo es (eso lo cuida `exigirSinRevisar`).
  private exigirVersion(versionId: string): VersionImportada {
    const version = VERSIONES.get(versionId);
    if (!version) {
      throw new ErrorTukit(404, "version_no_existe", "No hay ninguna version con ese identificador.");
    }
    return version;
  }

  // La misma puerta que `_exigir_sin_revisar` del backend: existe (404) y no
  // esta revisada (409). Editar/agregar solo valen sobre una version sin revisar.
  private exigirSinRevisar(versionId: string): VersionImportada {
    const version = this.exigirVersion(versionId);
    if (version.revisada) {
      throw new ErrorTukit(
        409,
        "lista_ya_revisada",
        "Esa version ya fue revisada. Para corregirla, crea una version nueva.",
      );
    }
    return version;
  }

  // ---------------------------------------------- §Admin — identidad del colegio (P4)
  async colegio(colegioId: string): Promise<ColegioDetalle> {
    return detalleColegio(colegioId);
  }

  async editarColegio(colegioId: string, cambios: ColegioEditable): Promise<ColegioDetalle> {
    // Que exista en la semilla, para no parchar una identidad inventada.
    detalleColegio(colegioId);
    const previo = PARCHES_COLEGIO.get(colegioId) ?? {};
    PARCHES_COLEGIO.set(colegioId, { ...previo, ...cambios });
    return detalleColegio(colegioId);
  }

  // §Admin — vista previa de una version (region 4). El administrador pide los
  // tres kits que saldrian de esta version sin crear un trabajo de acudiente.
  // Se reusa la MISMA maquinaria de kits que `crearTrabajo`/`trabajoAdmin`:
  // se siembra un `RegistroTrabajo` de preview para el (colegio, grado) de la
  // version (con `ctx` como fuente del destino) y se guarda en el almacen, de
  // modo que un `trabajoAdmin(trabajo_id)` posterior arme los 3 kits desde la
  // lista del corpus, sin ninguna forma fabricada aparte.
  async previewDeVersion(
    versionId: string,
    ctx: { colegioId: string; grado: string; anioLectivo: number },
  ): Promise<{ trabajo_id: string }> {
    // La version tiene que existir: se previsualiza algo curado, no un id al aire.
    this.exigirVersion(versionId);
    // Sin lista del corpus para ese (colegio, grado) no hay kits que armar:
    // `resolverSolicitud` volveria vacio y `trabajoAdmin` daria tres kits sin
    // lineas. Se falla temprano, igual que `crearTrabajo`/`onboarding`.
    if (!listaDe(ctx.colegioId, ctx.grado)) {
      throw new ErrorTukit(
        422,
        "lista_no_encontrada",
        `No tenemos la lista de ${ctx.grado} para ese colegio en el corpus simulado.`,
        { grados_detectados: [] },
      );
    }

    const ahora = Date.now();
    const registro: RegistroTrabajo = {
      trabajo_id: randomUUID(),
      // Un solo hijo => `armarKits` produce los 3 kits (Ahorrador/Fan/Premium)
      // de esa lista. El destino sale de `ctx`, que el gateway resolvio de la
      // version. El contacto es sintetico: la preview no notifica a nadie y
      // `trabajoAdmin` no lo usa (solo deriva `contacto_id` del trabajo_id).
      solicitud: {
        contacto: { correo: "preview@tukit", celular: "0000000000" },
        hijos: [{ referencia: "preview", colegio_id: ctx.colegioId, grado: ctx.grado }],
      },
      base_ms: ahora,
      creado_ms: ahora,
      origen_entrada: "lista_oficial",
      archivos: [],
      aprobado: false,
      nota_revision: null,
      validadas: [],
      sin_coincidencia: {},
      skus_no_disponibles: [],
      productos_manuales: {},
    };
    guardar(registro);
    return { trabajo_id: registro.trabajo_id };
  }

  // -------------------------------------------------------- §Admin — sugerencias (P4)
  async sugerencias(): Promise<Sugerencia[]> {
    // Se sirve el backlog en memoria recortado a los campos SEGUROS: nunca
    // correo ni telefono (que ni siquiera existen en el asiento), solo la
    // referencia opaca al contacto.
    return SUGERENCIAS.map((s) => ({
      tarea_id: s.tarea_id,
      estado: s.estado,
      colegio_id: s.colegio_id,
      grado: s.grado,
      anio_lectivo: s.anio_lectivo,
      contacto_referencia: s.contacto_referencia,
      tiene_documento: s.tiene_documento,
    }));
  }

  async documento(versionId: string): Promise<Blob> {
    const version = VERSIONES.get(versionId);
    if (!version) {
      throw new ErrorTukit(404, "sin_evidencia", "Esta lista no tiene documento adjunto.");
    }
    return version.documento;
  }

  async percepcion(versionId: string): Promise<PercepcionCruda> {
    const version = VERSIONES.get(versionId);
    if (!version) {
      throw new ErrorTukit(404, "sin_evidencia", "Esta lista no tiene percepción guardada.");
    }
    return version.percepcion;
  }

  // ASUMIDO — superficie de lectura de `comercio`. Los pedidos se derivan de
  // los trabajos publicados (ver `back-office.ts`): un trabajo aprobado se
  // vuelve pedido, igual que en la saga del §Procesos.
  async pedidos(): Promise<TableroComercio> {
    return derivarTablero();
  }

  async pedido(pedidoId: string): Promise<Pedido> {
    const pedido = derivarPedido(pedidoId);
    if (!pedido) throw new ErrorTukit(404, "pedido_no_existe", "Ese pedido no existe.");
    return pedido;
  }

  // El historial del acudiente. Los pedidos simulados se derivan de los
  // trabajos publicados y no llevan `usuario_id` (la demo es de un solo hogar),
  // asi que se devuelve el tablero completo: es el mismo conjunto que el padre
  // veria en su panel. El backend real si filtra por `usuario_id`.
  async misPedidos(_usuarioId: string): Promise<Pedido[]> {
    return derivarTablero().pedidos;
  }

  // ASUMIDO — superficie de lectura de `operacion`. Los casos se derivan de las
  // fallas observables de cada trabajo (SIN_MATCH → mapeo, HUECO → stock).
  async casos(): Promise<BandejaOperacion> {
    return derivarBandeja();
  }

  async caso(casoId: string): Promise<Caso> {
    const caso = derivarCaso(casoId);
    if (!caso) throw new ErrorTukit(404, "caso_no_existe", "Ese caso no existe.");
    return caso;
  }

  // Superficie de ESCRITURA de `operacion`: abrir una PQRS desde el centro de
  // ayuda. El backend real lo hara en `POST /v1/operacion/casos`; aqui se anexa
  // al almacen para que el mismo caso aparezca en la bandeja de `apps/admin`,
  // igual que la pausa humana del §7 usa el fichero para cruzar los dos procesos.
  async crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado> {
    const asunto = solicitud.asunto?.trim();
    const descripcion = solicitud.descripcion?.trim();

    if (!CATEGORIAS_CASO_ACUDIENTE.includes(solicitud.categoria)) {
      throw new ErrorTukit(
        400,
        "categoria_invalida",
        "Elige un tipo de solicitud de la lista.",
        { campo: "categoria" },
      );
    }
    if (!asunto) {
      throw new ErrorTukit(400, "asunto_requerido", "Escribe un asunto corto.", {
        campo: "asunto",
      });
    }
    if (!descripcion || descripcion.length < 10) {
      throw new ErrorTukit(
        400,
        "descripcion_corta",
        "Cuéntanos un poco más: con menos de diez caracteres no podemos ayudarte.",
        { campo: "descripcion" },
      );
    }
    if (!solicitud.contacto?.correo || !solicitud.contacto?.celular) {
      throw new ErrorTukit(
        400,
        "contacto_requerido",
        "Déjanos un correo y un celular para responderte.",
        { campo: "contacto" },
      );
    }

    // Si el acudiente pegó un identificador de trabajo, se comprueba que exista
    // para no colgar el caso de una referencia inventada. No es obligatorio.
    let trabajoId: string | null = solicitud.trabajo_id?.trim() || null;
    if (trabajoId && !obtener(trabajoId)) {
      throw new ErrorTukit(
        404,
        "trabajo_no_existe",
        "No encontramos ese número de kit. Revísalo o déjalo en blanco.",
        { campo: "trabajo_id" },
      );
    }

    const ahora = new Date();
    const caso: Caso = {
      caso_id: `CAS-${randomUUID().slice(0, 8).toUpperCase()}`,
      origen: "acudiente",
      categoria: solicitud.categoria,
      estado: "abierto",
      prioridad: prioridadDe(solicitud.categoria),
      asunto,
      abierto_en: ahora.toISOString(),
      vence_en: vencimientoDe(solicitud.categoria, ahora),
      trabajo_id: trabajoId,
      pedido_id: null,
      asignado_a: null,
    };
    guardarCaso(caso);

    return {
      caso_id: caso.caso_id,
      estado: caso.estado,
      categoria: caso.categoria,
      recibido_en: caso.abierto_en,
      vence_en: caso.vence_en,
    };
  }
}

// Una PQRS (queja/reclamo/petición) tiene reloj legal y sube de prioridad; una
// sugerencia no corre prisa. Reglas mínimas, no una matriz de SLA completa.
function prioridadDe(categoria: CategoriaCaso): Prioridad {
  if (categoria === "pago" || categoria === "reclamo") return "alta";
  if (categoria === "sugerencia") return "baja";
  return "media";
}

// Término de respuesta de la Ley 1755 para PQRS: 15 días hábiles. Se aproxima a
// 15 días corridos —el simulado no lleva calendario de festivos—, y solo para
// las categorías que son PQRS de verdad; una sugerencia no tiene término.
function vencimientoDe(categoria: CategoriaCaso, desde: Date): string | null {
  const conTermino: CategoriaCaso[] = ["peticion", "queja", "reclamo", "pago", "entrega"];
  if (!conTermino.includes(categoria)) return null;
  const vence = new Date(desde);
  vence.setDate(vence.getDate() + 15);
  return vence.toISOString();
}

// Aplica un `ItemListaEditable` sobre un renglon en sitio: solo lo presente
// viaja (los `undefined` no tocan el campo). `concepto` es el CODIGO; se resuelve
// contra el catalogo para llenar tambien el nombre, y `null` desliga el renglon
// y lo manda a revision, igual que la invariante del modelo del backend.
function aplicarCambiosItem(item: ItemRevision, cambios: ItemListaEditable): void {
  if (cambios.texto_original !== undefined) item.texto_original = cambios.texto_original;
  if (cambios.cantidad !== undefined) item.cantidad = cambios.cantidad;
  if (cambios.unidad !== undefined) item.unidad = cambios.unidad;
  if (cambios.tipo_item !== undefined && cambios.tipo_item !== null)
    item.tipo_item = cambios.tipo_item;
  if (cambios.modo_adquisicion !== undefined) item.modo_adquisicion = cambios.modo_adquisicion;
  if (cambios.instruccion_colegio !== undefined)
    item.instruccion_colegio = cambios.instruccion_colegio;
  if (cambios.url_externa !== undefined) item.url_externa = cambios.url_externa;
  if (cambios.atributos !== undefined) item.atributos = cambios.atributos;
  if ("concepto" in cambios) {
    if (cambios.concepto == null) {
      item.concepto_codigo = null;
      item.concepto_nombre = null;
      item.requiere_revision = true;
    } else {
      const concepto = CATALOGO.conceptos.find((c) => c.codigo === cambios.concepto);
      item.concepto_codigo = cambios.concepto;
      item.concepto_nombre = concepto?.nombre_canonico ?? null;
      item.requiere_revision = false;
    }
  }
  if (cambios.requiere_revision !== undefined) item.requiere_revision = cambios.requiere_revision;
}

// El detalle de un colegio: la fila de la semilla mas el parche en memoria si
// lo hubo. La semilla de colegios no lleva contacto ni sitio (esos nacen en
// `null`); las sedes no viven en el corpus simulado, asi que van vacias.
function detalleColegio(colegioId: string): ColegioDetalle {
  const base = COLEGIOS.find((c) => c.colegio_id === colegioId);
  if (!base) {
    throw new ErrorTukit(404, "colegio_no_existe", "No hay ningun colegio con ese identificador.");
  }
  const parche = PARCHES_COLEGIO.get(colegioId) ?? {};
  return {
    colegio_id: base.colegio_id,
    nombre: base.nombre,
    logo_url: "logo_url" in parche ? (parche.logo_url ?? null) : base.logo_url,
    sitio_web: parche.sitio_web ?? null,
    contacto_nombre: parche.contacto_nombre ?? null,
    contacto_email: parche.contacto_email ?? null,
    contacto_telefono: parche.contacto_telefono ?? null,
    direccion: null,
    sedes: [] as SedeColegio[],
  };
}
