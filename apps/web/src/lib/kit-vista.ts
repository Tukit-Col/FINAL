// Las reglas puras de lo que el renglón del kit le muestra al acudiente,
// separadas del componente para probarlas sin navegador.

import { clasificar, esInformativaOExterna } from "@tukit/contrato/linea";
import type { Consolidacion, LineaKit } from "@tukit/contrato";

// Un hijo del trabajo tal como lo devuelve `GET /v1/trabajos/{id}`. La ruta
// rápida no trae `referencia` (sus renglones dicen "canonico").
export interface HijoDelTrabajo {
  referencia?: string;
  colegio_id?: string;
  grado?: string;
  // Lo que el acudiente escribió para este hijo en /empezar.
  apodo?: string;
}

// Lo justo de una matrícula del portador para ponerle nombre a su hijo.
export interface ApodoMatricula {
  colegio_id: string;
  grado: string;
  apodo: string | null;
}

// A qué hijo pertenece cada renglón. La `hijo` de la línea es una referencia
// interna ("canonico", "hijo-0"): nunca se pinta. Se cruza con el colegio y el
// grado del hijo del trabajo y, si una sola matrícula del acudiente casa con un
// solo apodo, ese es el nombre. Si no hay apodo y el kit es de un solo hijo no
// hay nada que distinguir y no se pinta pastilla; con varios hijos, el que no
// tiene apodo se llama "Hijo N" por su orden en el kit.
export function etiquetasDeHijos(
  referencias: readonly (string | null | undefined)[],
  hijosDelTrabajo: readonly HijoDelTrabajo[] = [],
  matriculas: readonly ApodoMatricula[] = [],
): Map<string, string> {
  const distintas = [...new Set(referencias.filter((r): r is string => Boolean(r)))];
  const etiquetas = new Map<string, string>();
  distintas.forEach((referencia, indice) => {
    const hijo =
      hijosDelTrabajo.find((h) => h.referencia === referencia) ??
      (hijosDelTrabajo.length === 1 ? hijosDelTrabajo[0] : undefined);
    const propio = hijo?.apodo?.trim();
    // Las matrículas solo identifican al hijo si ningún hermano comparte su
    // colegio y grado; si no, el mismo apodo caería en los dos.
    const hermanos = hijo
      ? hijosDelTrabajo.filter((h) => h.colegio_id === hijo.colegio_id && h.grado === hijo.grado).length
      : 0;
    const apodos = new Set(
      matriculas
        .filter(
          (m) => hijo && hermanos <= 1 && m.colegio_id === hijo.colegio_id && m.grado === hijo.grado,
        )
        .map((m) => m.apodo?.trim() ?? "")
        .filter(Boolean),
    );
    if (propio) etiquetas.set(referencia, propio);
    else if (apodos.size === 1) etiquetas.set(referencia, [...apodos][0]!);
    else if (distintas.length > 1) etiquetas.set(referencia, `Hijo ${indice + 1}`);
  });
  return etiquetas;
}

// El grado de cada hijo del kit, por la `hijo` de sus renglones: lo que se pone
// al lado de su nombre en "Lo que juntamos". La ruta rápida («canonico») no
// trae referencia: con un solo hijo en el trabajo, es ese.
export function gradosDeHijos(
  referencias: readonly (string | null | undefined)[],
  hijosDelTrabajo: readonly HijoDelTrabajo[] = [],
): Map<string, string> {
  const grados = new Map<string, string>();
  for (const referencia of new Set(referencias.filter((r): r is string => Boolean(r)))) {
    const hijo =
      hijosDelTrabajo.find((h) => h.referencia === referencia) ??
      (hijosDelTrabajo.length === 1 ? hijosDelTrabajo[0] : undefined);
    const grado = hijo?.grado?.trim();
    if (grado) grados.set(referencia, grado);
  }
  return grados;
}

// La pista de tienda bajo el precio. La normalización del contrato sintetiza
// una oferta con la tienda vacía cuando el backend solo manda el precio: sin
// un nombre de verdad no hay pista, en vez de un "en" que no dice dónde.
export function pistaDeTienda(ofertas: readonly { tienda: string }[]): string | null {
  const tiendas = ofertas.map((o) => o.tienda.trim()).filter(Boolean);
  if (tiendas.length === 0) return null;
  return tiendas.length > 1 ? `en ${tiendas[0]} · ${tiendas.length} tiendas` : `en ${tiendas[0]}`;
}

// "Ana", "Ana y Luis", "Ana, Luis y Sofi". Los nombres salen del mismo mapa
// que las pastillas de los renglones (`etiquetasDeHijos`), así que coinciden.
// Un hijo que el mapa no conoce se llama "Hijo N" por su lugar en el grupo; un
// hijo repetido se nombra una sola vez.
export function nombresEnLista(
  hijos: readonly string[],
  nombres: ReadonlyMap<string, string>,
): string {
  const vistos = new Set<string>();
  const lista: string[] = [];
  hijos.forEach((h, i) => {
    const nombre = nombres.get(h)?.trim() || `Hijo ${i + 1}`;
    if (!vistos.has(nombre)) {
      vistos.add(nombre);
      lista.push(nombre);
    }
  });
  if (lista.length <= 1) return lista[0] ?? "";
  return `${lista.slice(0, -1).join(", ")} y ${lista[lista.length - 1]}`;
}

// Lo que el acudiente lee de un grupo que se junta entre hermanos: para quién
// es, cuánto se necesita y se compra en total y, solo si el contrato lo trae,
// cuánto se ahorra frente a comprar por separado (el ahorro viene exacto del
// backend: precio × paquetes de menos; no se recalcula aquí). La consolidación
// no trae la unidad ni el tamaño del paquete: el nombre del producto, que casi
// siempre lo lleva ("x12 Und"), se muestra aparte y la frase no lo repite.
//
// `porque` es la `explicacion` del backend tal cual ("Un empaque de 50 sale más
// barato que 2 por separado"). Con `grados`, cada hijo lleva el suyo al lado:
// "Hijo 1 (Séptimo) y Hijo 2 (Jardín)".
export function textoDeConsolidacion(
  c: {
    hijos: readonly string[];
    demanda_base?: number | null;
    unidades_a_comprar?: number | null;
    explicacion?: string | null;
  },
  nombres: ReadonlyMap<string, string>,
  ahorroEnPesos: string | null,
  grados?: ReadonlyMap<string, string>,
): { paraQuienes: string | null; cantidad: string | null; ahorro: string | null; porque: string | null } {
  const conGrado = new Map<string, string>();
  c.hijos.forEach((h, i) => {
    const nombre = nombres.get(h)?.trim() || `Hijo ${i + 1}`;
    const grado = grados?.get(h)?.trim();
    conGrado.set(h, grado ? `${nombre} (${grado})` : nombre);
  });
  const quienes = nombresEnLista(c.hijos, conGrado);
  const paquetes = c.unidades_a_comprar ?? 0;
  const necesitan = c.demanda_base ?? 0;
  const compras =
    paquetes > 0 ? `compras ${paquetes === 1 ? "1 paquete" : `${paquetes} paquetes`}` : null;
  let cantidad: string | null = null;
  if (necesitan > 0) {
    cantidad = `Necesitan ${necesitan} ${necesitan === 1 ? "unidad" : "unidades"} en total` + (compras ? ` y ${compras}` : "");
  } else if (compras) {
    cantidad = `En total ${compras}`;
  }
  return {
    paraQuienes: quienes ? `Para ${quienes}` : null,
    cantidad,
    ahorro: ahorroEnPesos ? `Ahorras ${ahorroEnPesos} frente a comprarlos por separado` : null,
    porque: c.explicacion?.trim() || null,
  };
}

// El útil de cada concepto ancla del Fan, como lo dice el acudiente.
const CONCEPTO_LEGIBLE: Record<string, string> = {
  C001: "cuaderno",
  C009: "cartuchera",
  C011: "carpeta",
  C086: "maleta",
};

/** "Spiderman", "Toy Story": el personaje con mayúscula inicial en cada palabra. */
export function personajeLegible(personaje: string): string {
  return personaje
    .split(/[\s_]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

// La nota bajo la fila de un hijo cuando un ancla de su personaje no cupo en
// ningún renglón de su lista (`kit.personaje_sin_encaje`).
export function notaSinEncaje(f: { concepto: string; personaje: string }): string {
  const util = CONCEPTO_LEGIBLE[f.concepto] ?? "producto";
  return `No encontramos ${util} de ${personajeLegible(f.personaje)} que cumpla lo que pide la lista; dejamos uno sin personaje.`;
}

// ---- Panel por hijo (hogar con 2+ hijos) -----------------------------------
// Un resumen por hijo para separar de un vistazo cada kit, lo que comparten y
// lo que falta. Lógica pura; el componente `ResumenPorHijo` solo la pinta.

export interface ResumenHijo {
  hijo: string; // referencia interna (clave de agrupación), NUNCA se pinta
  nombre: string; // de `nombres`; "Hijo N" si no hay
  grado: string | null;
  personaje: string | null; // primer personaje pedido por ese hijo, o null
  total: number; // suma de subtotal_linea de sus comprables
  productos: LineaKit[]; // comprables NO consolidadas-en-cero, una por sku
  veces: Record<string, number>; // sku -> en cuantos renglones de este hijo va
  comparten: number; // nº de consolidaciones en que participa
  falta: string[]; // avisos: personaje_sin_encaje + huecos, sin leer y en revision
  aparte: number; // renglones que se consiguen por fuera (libros, uniformes, licencias...)
}

// Lo que Tukit no pudo resolver: lo mismo que la vista pinta arriba con color de aviso.
const POR_RESOLVER = new Set(["hueco", "sin_match", "pendiente_revision"]);

export function resumenPorHijo(
  kit: {
    lineas: readonly LineaKit[];
    consolidaciones: readonly Consolidacion[];
    personaje_sin_encaje?: readonly { hijo: string; concepto: string; personaje: string }[];
  },
  nombres: ReadonlyMap<string, string>,
  grados: ReadonlyMap<string, string>,
  personajesPorHijo?: Record<string, string[]>,
): ResumenHijo[] {
  const orden: string[] = [];
  const porHijo = new Map<string, ResumenHijo>();
  const indice = (hijo: string): ResumenHijo => {
    let r = porHijo.get(hijo);
    if (!r) {
      r = {
        hijo,
        nombre: nombres.get(hijo)?.trim() || `Hijo ${orden.length + 1}`,
        grado: grados.get(hijo)?.trim() || null,
        personaje: (personajesPorHijo?.[hijo] ?? []).find((p) => p.trim()) ?? null,
        total: 0,
        productos: [],
        veces: {},
        comparten: 0,
        falta: [],
        aparte: 0,
      };
      porHijo.set(hijo, r);
      orden.push(hijo);
    }
    return r;
  };

  // Una linea sin `hijo` (trabajos viejos) no es un hijo mas: si el kit tiene un
  // solo hijo real es suya; con varios no se adivina de quien es y se omite.
  const reales = [...new Set(kit.lineas.map((l) => l.hijo).filter((h): h is string => Boolean(h)))];
  for (const linea of kit.lineas) {
    const hijo = linea.hijo || (reales.length === 1 ? reales[0] : null);
    if (!hijo) continue;
    const r = indice(hijo);
    // El total sigue la regla del backend: todo lo no informativo con precio,
    // asi los totales de los hijos suman exacto el del kit (un renglon en
    // revision con precio tambien cuenta). Lo descartado ya llega sin subtotal.
    if (!linea.informativa && !linea.descartado && typeof linea.subtotal_linea === "number") {
      r.total += linea.subtotal_linea;
    }
    const clase = clasificar(linea);
    if (POR_RESOLVER.has(clase)) {
      r.falta.push(linea.descripcion);
    } else if (esInformativaOExterna(linea)) {
      r.aparte += 1;
    } else if (clase === "comprable" && !linea.descartado && linea.producto_elegido) {
      // La linea del hermano consolidado va en 0 unidades: su compra vive en la
      // banda de compartido, no se repite en su tarjeta. Un mismo producto en
      // varios renglones (un cuaderno por materia) sale una vez con su cantidad.
      if ((linea.unidades_a_comprar ?? 0) <= 0) continue;
      const sku = linea.producto_elegido.sku;
      if (!(sku in r.veces)) r.productos.push(linea);
      r.veces[sku] = (r.veces[sku] ?? 0) + 1;
    }
  }

  for (const c of kit.consolidaciones) {
    for (const hijo of c.hijos) {
      const r = porHijo.get(hijo);
      if (r) r.comparten += 1;
    }
  }

  for (const f of kit.personaje_sin_encaje ?? []) {
    const r = porHijo.get(f.hijo);
    if (r) r.falta.unshift(notaSinEncaje(f));
  }

  return orden.map((h) => porHijo.get(h)!);
}

// ---- Categoría de una línea (Fase 3) ---------------------------------------
// `LineaKit` no trae categoría: se deriva en el cliente del texto del renglón.
// `concepto` suele ser un código del catálogo ("C001"), así que el nombre del
// útil sale de `descripcion`; si `concepto` trae un nombre se mira primero.

export type CategoriaKit = "cuadernos" | "escritura" | "arte" | "papeleria" | "geometria" | "otros";

export const TITULO_CATEGORIA: Record<CategoriaKit, string> = {
  cuadernos: "Cuadernos y libretas",
  escritura: "Lápices y escritura",
  arte: "Arte y colores",
  papeleria: "Papelería y pegantes",
  geometria: "Geometría",
  otros: "Otros",
};

const ORDEN_CATEGORIAS: CategoriaKit[] = ["cuadernos", "escritura", "arte", "papeleria", "geometria", "otros"];

/** Minúsculas y sin tildes: la comparación de textos y marcas del cliente. */
export function normalizarTexto(t: string): string {
  return t
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

// Geometría va antes que escritura/papelería ("regla", "compas" no chocan, pero
// "estuche de geometria" sí con "estuche"). Cada regex se contrastó con los
// nombres canónicos de datos/catalogo/conceptos.csv.
const REGLAS: [CategoriaKit, RegExp][] = [
  // Aseo: "papel higiénico" no es papelería.
  ["otros", /\b(higienico|jabon|antibacterial|toallas|bolsa de basura|esponja)/],
  ["geometria", /\b(regla|escuadra|transportador|compas|geometri|curvigrafo|cinta metrica|calculadora)/],
  ["cuadernos", /\b(cuaderno|libreta|bitacora|agenda|planeador|block de notas)/],
  [
    "escritura",
    /\b(lapiz|lapices|lapicero|portaminas|esfero|boligrafo|pluma|marcador|plumon|resaltador|borrador|tajalapiz|sacapuntas|corrector|limpiatipos|tiza)/,
  ],
  [
    "arte",
    /\b(color|colores|crayola|crayon|crayones|tempera|vinilo|pintura|acuarela|pincel|lienzo|plastilina|foamy|carboncillo|escarcha|lentejuela|lana|pompon|limpiapipas|ojos moviles|masa para moldear|kit de artes|tinta china|algodon|aserrin|arena decorativa|tablero de dibujo|espatula)/,
  ],
  [
    "papeleria",
    /\b(papel|cartulina|carton|block|resma|hojas|carpeta|folder|legajador|sobre|separador|cinta|pegante|colbon|pegastic|silicona|tijera|clip|gancho|grapa|chincheta|notas adhesivas|post-it|acetato|funda|fichas|cartuchera)/,
  ],
];

export function categoriaDeLinea(l: { concepto?: string | null; descripcion: string }): CategoriaKit {
  const nombre = l.concepto && !/^[A-Z]\d{2,}$/.test(l.concepto.trim()) ? `${l.concepto} ` : "";
  const texto = normalizarTexto(`${nombre}${l.descripcion}`);
  for (const [categoria, regla] of REGLAS) if (regla.test(texto)) return categoria;
  return "otros";
}

export function agruparPorCategoria<T extends { concepto?: string | null; descripcion: string }>(
  lineas: readonly T[],
): { categoria: CategoriaKit; titulo: string; lineas: T[] }[] {
  const grupos = new Map<CategoriaKit, T[]>();
  for (const l of lineas) {
    const c = categoriaDeLinea(l);
    grupos.set(c, [...(grupos.get(c) ?? []), l]);
  }
  return ORDEN_CATEGORIAS.filter((c) => grupos.has(c)).map((c) => ({
    categoria: c,
    titulo: TITULO_CATEGORIA[c],
    lineas: grupos.get(c)!,
  }));
}

// ---- Anclas estables (contrato con el asistente de la Fase 5) --------------

export function idAnclaCategoria(c: CategoriaKit): string {
  return `cat-${c}`;
}

/** Id HTML válido y sin colisiones: todo carácter raro se codifica en hex. */
export function idAnclaLinea(itemId: string): string {
  const seguro = itemId.replace(/[^A-Za-z0-9_-]/g, (ch) => `.${ch.codePointAt(0)!.toString(16)}.`);
  return `linea-${seguro}`;
}
