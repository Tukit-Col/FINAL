// Las reglas puras de lo que el renglón del kit le muestra al acudiente,
// separadas del componente para probarlas sin navegador.

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
export function textoDeConsolidacion(
  c: {
    hijos: readonly string[];
    demanda_base?: number | null;
    unidades_a_comprar?: number | null;
  },
  nombres: ReadonlyMap<string, string>,
  ahorroEnPesos: string | null,
): { paraQuienes: string | null; cantidad: string | null; ahorro: string | null } {
  const quienes = nombresEnLista(c.hijos, nombres);
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
  };
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
