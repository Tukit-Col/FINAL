// Arma los tres kits del §5 a partir de una lista oficial del corpus.
//
// No es un mock de pantalla: recorre los renglones reales de la lista, los
// resuelve contra los conceptos reales del catalogo y se abstiene donde el
// catalogo real no tiene nada. De ahi que la pantalla muestre huecos: 17 de
// los 99 conceptos no tienen ni un producto, y taparlos aqui haria que la UI
// se viera mejor de lo que el sistema esta.

import type {
  Consolidacion,
  Degradacion,
  Kit,
  LineaKit,
  Nivel,
  PerfilKit,
  Preferencias,
  ProductoKit,
  Recomendacion,
  SolicitudTrabajo,
  Sustituto,
  TipoItem,
} from "../contrato";
import { PESOS_POR_DEFECTO } from "../contrato";
import type { ConceptoCatalogo, ItemListaOficial, ProductoCatalogo } from "../catalogo";
import { precioMasBarato, unidadesDeEmpaque } from "../catalogo";
import { formatearPesos } from "../dinero";
import { CATALOGO, listaDe, resolverConcepto } from "./semillas";

export interface ItemResuelto {
  itemId: string;
  hijo: string;
  item: ItemListaOficial;
  concepto: ConceptoCatalogo | null;
  confianza: number;
}

/** Los renglones de todos los hijos, ya resueltos a concepto una sola vez. */
export function resolverSolicitud(solicitud: SolicitudTrabajo): ItemResuelto[] {
  const resueltos: ItemResuelto[] = [];
  solicitud.hijos.forEach((hijo, indice) => {
    const lista = listaDe(hijo.colegio_id, hijo.grado);
    if (!lista) return;
    const prefijo = `h${indice + 1}`;
    for (const item of lista.items) {
      const texto = item.texto_generico ?? item.texto_original;
      const { concepto, confianza } = resolverConcepto(texto);
      resueltos.push({
        itemId: `${prefijo}-${String(item.orden).padStart(3, "0")}`,
        hijo: hijo.referencia,
        item,
        concepto,
        confianza,
      });
    }
  });
  return resueltos;
}

// --------------------------------------------------------- Elegir producto

function aProductoKit(producto: ProductoCatalogo, confianza: number): ProductoKit {
  return {
    sku: producto.sku,
    nombre: producto.nombre,
    marca: producto.marca,
    nivel: producto.nivel,
    personaje: producto.personaje,
    imagen_url: producto.imagen_url,
    confianza,
    ofertas: producto.ofertas
      .filter((o) => typeof o.precio === "number")
      .map((o) => ({
        tienda: o.tienda,
        precio: o.precio as number,
        vigente_hasta: null,
      })),
  };
}

const ORDEN: Record<Nivel, number> = { economico: 0, confiable: 1, premium: 2 };

function porPrecio(a: ProductoCatalogo, b: ProductoCatalogo): number {
  const pa = precioMasBarato(a);
  const pb = precioMasBarato(b);
  if (pa === null) return 1;
  if (pb === null) return -1;
  return pa - pb;
}

/**
 * Cual de los productos del concepto se lleva cada perfil.
 *
 * Los tres son puntos distintos del mismo frente, no tres catalogos: un kit
 * `Ahorrador` puede quedarse con un producto de nivel `premium` si resulto
 * mas barato por empaque, que es exactamente lo que dice el §1.3.
 */
function elegirProducto(
  concepto: ConceptoCatalogo,
  perfil: PerfilKit,
  personajes: readonly string[],
): ProductoCatalogo | null {
  const conPrecio = concepto.productos.filter((p) => precioMasBarato(p) !== null);
  const candidatos = conPrecio.length > 0 ? conPrecio : concepto.productos;
  if (candidatos.length === 0) return null;

  if (perfil === "Fan") {
    const pedidos = candidatos.filter(
      (p) => p.personaje && personajes.includes(p.personaje.toLowerCase()),
    );
    if (pedidos.length > 0) return [...pedidos].sort(porPrecio)[0] ?? null;
    const conPersonaje = candidatos.filter((p) => p.personaje);
    if (conPersonaje.length > 0) return [...conPersonaje].sort(porPrecio)[0] ?? null;
  }

  if (perfil === "Premium") {
    const ordenados = [...candidatos].sort(
      (a, b) => ORDEN[b.nivel] - ORDEN[a.nivel] || porPrecio(a, b),
    );
    return ordenados[0] ?? null;
  }

  return [...candidatos].sort(porPrecio)[0] ?? null;
}

function alternativasDe(
  concepto: ConceptoCatalogo,
  elegido: ProductoCatalogo,
  confianza: number,
): ProductoKit[] {
  const vistos = new Set([elegido.nivel]);
  const otras: ProductoCatalogo[] = [];
  for (const p of [...concepto.productos].sort(porPrecio)) {
    if (p.sku === elegido.sku || vistos.has(p.nivel)) continue;
    vistos.add(p.nivel);
    otras.push(p);
    if (otras.length === 2) break;
  }
  return otras.map((p) => aProductoKit(p, confianza));
}

// El grafo de sustituibilidad vive en la base y aqui no esta. Lo que si se
// puede ofrecer sin inventarlo es otro concepto de la MISMA categoria que si
// tenga productos: es la version pobre de la misma idea —"no tengo block
// oficio, pero el carta le sirve"— y va marcada como aproximada.
function sustitutosDe(concepto: ConceptoCatalogo): Sustituto[] {
  return CATALOGO.conceptos
    .filter(
      (c) =>
        c.codigo !== concepto.codigo &&
        c.categoria === concepto.categoria &&
        c.productos.length > 0,
    )
    .slice(0, 2)
    .map((c) => ({
      concepto: c.codigo,
      nombre: c.nombre_canonico,
      grado: 0.5,
      motivo: `Misma categoria (${c.categoria}) y si lo tenemos en catalogo.`,
    }));
}

// ----------------------------------------------------------- Armar una linea

const MODOS_SURTIBLES = new Set(["mercado_abierto", "libro_libre"]);

function instruccionDe(item: ItemListaOficial): string {
  switch (item.modo_adquisicion) {
    case "venta_directa_editorial":
      return "La editorial lo vende directamente a las familias en el colegio.";
    case "edicion_exclusiva":
      return "Edicion exclusiva para la institucion. Se adquiere con la editorial.";
    case "plataforma":
      return "Se paga en la plataforma del proveedor con un link o un codigo de acceso.";
    case "diferido":
      return "El colegio lo va a solicitar durante el ano, segun las necesidades de la clase.";
    default:
      return "El colegio lo gestiona directamente.";
  }
}

function armarLinea(
  resuelto: ItemResuelto,
  perfil: PerfilKit,
  personajes: readonly string[],
  ajustes: AjustesAdmin,
): LineaKit {
  const { item, itemId, hijo, concepto, confianza } = resuelto;
  const tipo = item.tipo_item as TipoItem;
  const base: LineaKit = {
    item_id: itemId,
    hijo,
    descripcion: item.texto_original,
    tipo,
    cantidad_pedida: item.cantidad,
    subtotal_linea: null,
  };

  // (1) Lo que no es un producto comprable. El tipo manda sobre todo lo demas.
  if (tipo === "licencia_digital") {
    return {
      ...base,
      modo_adquisicion: "plataforma",
      url_externa: "https://pagoslearning.com/",
      nota: "Se adquiere directamente con el proveedor. No va en el carrito.",
    };
  }
  if (tipo === "no_comprar") {
    return {
      ...base,
      unidades_a_comprar: 0,
      nota: "El colegio indica usar el que ya tienes.",
    };
  }
  if (tipo === "diferido") {
    return { ...base, modo_adquisicion: "diferido", instruccion_colegio: instruccionDe(item) };
  }
  if (tipo === "uniforme") {
    return { ...base, nota: "Los uniformes quedan fuera del alcance de la version 1." };
  }

  // (2) Lo que el colegio cerro: se muestra con su instruccion y no se cobra.
  if (!MODOS_SURTIBLES.has(item.modo_adquisicion)) {
    return {
      ...base,
      modo_adquisicion: item.modo_adquisicion as LineaKit["modo_adquisicion"],
      informativa: true,
      instruccion_colegio: instruccionDe(item),
      precio: null,
      ...(item.libro
        ? {
            edicion: {
              isbn13: "",
              titulo: item.libro.titulo,
              editorial: item.libro.editorial ?? "",
              anio_edicion: 2026,
            },
          }
        : {}),
    };
  }

  // (3) El admin la marco sin coincidencia a mano.
  const marcada = ajustes.sinCoincidencia[itemId];
  if (marcada) {
    return { ...base, estado_resolucion: "SIN_MATCH", mensaje: marcada, informativa: false };
  }

  // (4) No se entendio el renglon.
  if (!concepto) {
    return {
      ...base,
      estado_resolucion: "SIN_MATCH",
      mensaje: "No logramos entender este renglon de la lista.",
    };
  }

  const elegido = elegirProducto(concepto, perfil, personajes);

  // (5) Se entendio y el catalogo no lo tiene. Es HUECO_CATALOGO, no SIN_MATCH.
  if (!elegido) {
    return {
      ...base,
      estado_resolucion: "HUECO_CATALOGO",
      concepto: `${concepto.codigo} ${concepto.nombre_canonico}`,
      mensaje: `Entendimos que pides ${concepto.nombre_canonico} y hoy no lo tenemos.`,
      sustitutos: sustitutosDe(concepto),
    };
  }

  const empaqueElegido = unidadesDeEmpaque(elegido);
  const unidadesACcomprar = Math.ceil(item.cantidad / empaqueElegido.cantidad);
  const precio = precioMasBarato(elegido);
  const noDisponible = ajustes.skusNoDisponibles.includes(elegido.sku);

  if (noDisponible) {
    return {
      ...base,
      estado_resolucion: "HUECO_CATALOGO",
      concepto: `${concepto.codigo} ${concepto.nombre_canonico}`,
      mensaje: `Se nos agoto ${elegido.nombre}. Estamos buscando reemplazo.`,
      sustitutos: sustitutosDe(concepto),
    };
  }

  // (6) Zona gris: hay candidatos y ninguno domina. Va a revision humana.
  const validada = ajustes.validadas.includes(itemId);
  const estado = !validada && confianza < 0.6 ? "AMBIGUO" : "RESUELTO_AUTO";

  const esTexto = tipo === "texto" || tipo === "libro_libre";
  return {
    ...base,
    estado_resolucion: estado,
    modo_adquisicion: item.modo_adquisicion as LineaKit["modo_adquisicion"],
    informativa: false,
    unidad_base: empaqueElegido.unidad,
    unidades_por_empaque: empaqueElegido.cantidad,
    unidades_a_comprar: unidadesACcomprar,
    producto_elegido: aProductoKit(elegido, validada ? 1 : confianza),
    alternativas: alternativasDe(concepto, elegido, confianza),
    ...(item.libro
      ? {
          edicion: {
            isbn13: "",
            titulo: item.libro.titulo,
            editorial: item.libro.editorial ?? "",
            anio_edicion: 2026,
          },
        }
      : {}),
    // La regla inversa de la consolidacion: los borradores se juntan y los
    // textos nunca, y el sistema dice por que.
    ...(esTexto
      ? {
          no_consolidable: true,
          motivo_no_consolidable: "Dos ediciones del mismo titulo no son sustituibles.",
        }
      : {}),
    precio,
    subtotal_linea: precio === null ? null : precio * unidadesACcomprar,
  };
}

// ------------------------------------------------------------ Consolidacion

function consolidar(lineas: readonly LineaKit[], resueltos: readonly ItemResuelto[]): Consolidacion[] {
  const porConcepto = new Map<string, { hijos: Set<string>; lineas: LineaKit[] }>();
  const conceptoDe = new Map(resueltos.map((r) => [r.itemId, r.concepto]));

  for (const linea of lineas) {
    const concepto = conceptoDe.get(linea.item_id);
    if (!concepto || linea.no_consolidable || !linea.producto_elegido) continue;
    const clave = concepto.codigo;
    const actual = porConcepto.get(clave) ?? { hijos: new Set<string>(), lineas: [] };
    if (linea.hijo) actual.hijos.add(linea.hijo);
    actual.lineas.push(linea);
    porConcepto.set(clave, actual);
  }

  const consolidaciones: Consolidacion[] = [];
  for (const [codigo, grupo] of porConcepto) {
    if (grupo.hijos.size < 2) continue;
    const primera = grupo.lineas[0];
    if (!primera?.producto_elegido) continue;

    // Consolidar solo tiene sentido si el empaque trae mas de una unidad.
    // Con empaques de una unidad, juntar dos borradores sueltos compra
    // exactamente los mismos dos borradores: el ahorro seria cero y
    // anunciarlo igual convierte una funcion real en una promesa vacia.
    const empaque = primera.unidades_por_empaque ?? 1;
    if (empaque <= 1) continue;

    const demanda = grupo.lineas.reduce((t, l) => t + (l.cantidad_pedida ?? 1), 0);
    const empaquesJuntos = Math.ceil(demanda / empaque);
    const empaquesAparte = grupo.lineas.reduce(
      (t, l) => t + Math.ceil((l.cantidad_pedida ?? 1) / empaque),
      0,
    );
    if (empaquesJuntos >= empaquesAparte) continue;

    const unitario = primera.precio ?? 0;
    consolidaciones.push({
      concepto: `${codigo} ${primera.descripcion}`,
      hijos: [...grupo.hijos],
      demanda_base: demanda,
      producto: primera.producto_elegido.sku,
      unidades_a_comprar: empaquesJuntos,
      ahorro: (empaquesAparte - empaquesJuntos) * unitario,
      explicacion: `Un empaque de ${empaque} alcanza para los dos, y sale mas barato que comprar uno por hijo.`,
    });
  }
  return consolidaciones;
}

// ------------------------------------------------------------------- Kits

export interface AjustesAdmin {
  validadas: string[];
  sinCoincidencia: Record<string, string>;
  skusNoDisponibles: string[];
}

export const SIN_AJUSTES: AjustesAdmin = {
  validadas: [],
  sinCoincidencia: {},
  skusNoDisponibles: [],
};

function personajesDe(preferencias: Preferencias | undefined): string[] {
  return Object.values(preferencias?.personaje_por_hijo ?? {})
    .flat()
    .map((p) => p.toLowerCase());
}

export function armarKits(
  solicitud: SolicitudTrabajo,
  resueltos: readonly ItemResuelto[],
  ajustes: AjustesAdmin = SIN_AJUSTES,
): Kit[] {
  const personajes = personajesDe(solicitud.preferencias);
  const perfiles: PerfilKit[] = ["Ahorrador", "Fan", "Premium"];

  return perfiles.map((perfil) => {
    const lineas = resueltos.map((r) => armarLinea(r, perfil, personajes, ajustes));

    // El total incluye SOLO lineas con `informativa: false` y precio conocido.
    const total = lineas.reduce(
      (t, l) => t + (l.informativa === true ? 0 : (l.subtotal_linea ?? 0)),
      0,
    );

    const comprables = lineas.filter((l) => l.producto_elegido);
    const conPrecio = comprables.filter((l) => l.subtotal_linea !== null);
    const fidelidad =
      comprables.length === 0
        ? 0
        : comprables.reduce((t, l) => t + (l.producto_elegido?.confianza ?? 0), 0) /
          comprables.length;

    return {
      perfil,
      total,
      objetivos: {
        costo: total,
        fidelidad: Number(fidelidad.toFixed(2)),
        disponibilidad:
          comprables.length === 0
            ? 0
            : Number((conPrecio.length / comprables.length).toFixed(2)),
      },
      lineas,
      consolidaciones: consolidar(lineas, resueltos),
    };
  });
}

// --------------------------------------------------------- Recomendacion §6

export function recomendar(
  kits: readonly Kit[],
  preferencias: Preferencias | undefined,
  // `presupuesto_por_hijo` es por hijo y el total del kit es del hogar. Sin
  // este numero, un tope de 700.000 con dos hijos declara fuera de
  // presupuesto un kit de 900.000 que si cabe, y la recomendacion se cae al
  // punto equivocado del frente.
  numeroDeHijos = 1,
): Recomendacion {
  const pesos = preferencias?.pesos ?? PESOS_POR_DEFECTO;
  const topePorHijo = preferencias?.presupuesto_por_hijo ?? null;
  const presupuesto = topePorHijo === null ? null : topePorHijo * Math.max(1, numeroDeHijos);
  const sobreprecio = preferencias?.disposicion_sobreprecio ?? 0;
  const personajes = personajesDe(preferencias);

  const porPerfil = new Map(kits.map((k) => [k.perfil, k]));
  const maximo = Math.max(pesos.precio, pesos.marca_exigida, pesos.calidad, pesos.personaje);

  // Por defecto Ahorrador: 42 de 60 encuestados pagan como maximo 5 % mas.
  let perfil: PerfilKit = "Ahorrador";
  let razon = "";

  if (personajes.length > 0) {
    perfil = "Fan";
    razon = `Pediste ${personajes.join(", ")} para tu hijo, y este es el kit que lo trae.`;
  } else if (pesos.calidad === maximo && sobreprecio >= 0.1) {
    perfil = "Premium";
    razon = "Pusiste la calidad primero y dijiste que pagas hasta un 10 % mas por ella.";
  } else {
    perfil = "Ahorrador";
    razon = "Elegiste el precio como lo mas importante, y este es el kit mas barato de los tres.";
  }

  let kit = porPerfil.get(perfil);
  let dentro = presupuesto === null || (kit?.total ?? 0) <= presupuesto;

  // Si el recomendado excede el presupuesto se cae al siguiente punto del
  // frente, y la razon lo dice en vez de callarlo.
  if (!dentro) {
    const alternativa = [...kits].sort((a, b) => a.total - b.total)[0];
    if (alternativa && presupuesto !== null && alternativa.total <= presupuesto) {
      razon =
        `El kit ${perfil} se pasa de tu presupuesto, asi que te recomendamos el ` +
        `${alternativa.perfil}, que si cabe.`;
      perfil = alternativa.perfil;
      kit = alternativa;
      dentro = true;
    } else {
      razon += " Ojo: ninguno de los tres cabe en el presupuesto que pusiste.";
    }
  } else if (presupuesto !== null) {
    razon += ` Queda en ${formatearPesos(kit?.total ?? 0)}, dentro de tu presupuesto.`;
  }

  return { perfil, razon, dentro_de_presupuesto: dentro, pesos_usados: pesos };
}

export function degradacionesDe(kits: readonly Kit[]): Degradacion[] {
  const referencia = kits[0];
  if (!referencia) return [];

  const degradaciones: Degradacion[] = [];

  // §8: precio vencido o desconocido -> la linea no entra al total.
  const sinPrecio = referencia.lineas.filter(
    (l) => l.producto_elegido && l.subtotal_linea === null,
  ).length;
  if (sinPrecio > 0) {
    degradaciones.push({
      dependencia: "precio",
      efecto: "sin precio vigente: la linea no entra al total y se marca para revision",
      lineas_afectadas: sinPrecio,
    });
  }

  const huecos = referencia.lineas.filter(
    (l) => l.estado_resolucion === "HUECO_CATALOGO",
  ).length;
  if (huecos > 0) {
    degradaciones.push({
      dependencia: "catalogo",
      efecto: "entendimos que pide la lista y no hay producto que ofrecer",
      lineas_afectadas: huecos,
    });
  }

  return degradaciones;
}
