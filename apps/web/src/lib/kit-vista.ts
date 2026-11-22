import { clasificar, esInformativaOExterna, esLibro, esUniforme, type ClaseLinea } from "@tukit/contrato/linea";
import type { Consolidacion, LineaKit } from "@tukit/contrato";

export interface HijoDelTrabajo {
  referencia?: string;
  colegio_id?: string;
  grado?: string;
  apodo?: string;
}

export interface ApodoMatricula {
  colegio_id: string;
  grado: string;
  apodo: string | null;
}

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

export function pistaDeTienda(ofertas: readonly { tienda: string }[]): string | null {
  const tiendas = ofertas.map((o) => o.tienda.trim()).filter(Boolean);
  if (tiendas.length === 0) return null;
  return tiendas.length > 1 ? `en ${tiendas[0]} · ${tiendas.length} tiendas` : `en ${tiendas[0]}`;
}

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

const CONCEPTO_LEGIBLE: Record<string, string> = {
  C001: "cuaderno",
  C009: "cartuchera",
  C011: "carpeta",
  C086: "maleta",
};

export function personajeLegible(personaje: string): string {
  return personaje
    .split(/[\s_]+/)
    .filter(Boolean)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

export function notaSinEncaje(f: { concepto: string; personaje: string }): string {
  const util = CONCEPTO_LEGIBLE[f.concepto] ?? "producto";
  return `No encontramos ${util} de ${personajeLegible(f.personaje)} que cumpla lo que pide la lista; dejamos uno sin personaje.`;
}

export interface ResumenHijo {
  hijo: string;
  nombre: string;
  grado: string | null;
  personaje: string | null;
  total: number;
  productos: LineaKit[];
  veces: Record<string, number>;
  comparten: number;
  falta: string[];
  aparte: number;
  renglones: number;
}

const POR_RESOLVER = new Set(["hueco", "sin_match", "pendiente_revision"]);
const MOTIVO_FALTA: Record<string, string> = {
  hueco: "Aún no lo tenemos",
  sin_match: "No encontramos uno que cumpla",
  pendiente_revision: "Lo estamos revisando",
};

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
        renglones: 0,
      };
      porHijo.set(hijo, r);
      orden.push(hijo);
    }
    return r;
  };

  const reales = [...new Set(kit.lineas.map((l) => l.hijo).filter((h): h is string => Boolean(h)))];
  for (const linea of kit.lineas) {
    const hijo = linea.hijo || (reales.length === 1 ? reales[0] : null);
    if (!hijo) continue;
    const r = indice(hijo);
    if (!linea.informativa && !linea.descartado && typeof linea.subtotal_linea === "number") {
      r.total += linea.subtotal_linea;
    }
    const clase = clasificar(linea);
    if (POR_RESOLVER.has(clase)) {
      r.falta.push(`${MOTIVO_FALTA[clase] ?? "Por resolver"}: ${linea.descripcion}`);
    } else if (esInformativaOExterna(linea)) {
      r.aparte += 1;
    } else if (clase === "comprable" && !linea.descartado && linea.producto_elegido) {
      r.renglones += 1;
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

export function normalizarTexto(t: string): string {
  return t
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

const REGLAS: [CategoriaKit, RegExp][] = [
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

export function idAnclaCategoria(c: CategoriaKit): string {
  return `cat-${c}`;
}

export function idAnclaLinea(itemId: string): string {
  const seguro = itemId.replace(/[^A-Za-z0-9_-]/g, (ch) => `.${ch.codePointAt(0)!.toString(16)}.`);
  return `linea-${seguro}`;
}

export function fotoDeConsolidacion(
  lineas: readonly LineaKit[],
  c: { producto: string },
): { imagen_url: string | null; linea: LineaKit | null } {
  const linea =
    lineas.find((l) => l.producto_elegido?.nombre === c.producto && (l.unidades_a_comprar ?? 0) > 0) ??
    lineas.find((l) => l.producto_elegido?.nombre === c.producto) ??
    null;
  return { imagen_url: linea?.producto_elegido?.imagen_url ?? null, linea };
}

export const ABSTENCIONES: readonly ClaseLinea[] = ["hueco", "sin_match", "pendiente_revision"];

export interface GrupoFueraDelCarrito {
  clave: "libros" | "colegio" | "uniformes" | "cuenta" | "casa";
  titulo: string;
  lineas: LineaKit[];
}

export function gruposFueraDelCarrito(lineas: readonly LineaKit[]): GrupoFueraDelCarrito[] {
  const libros: LineaKit[] = [];
  const uniformes: LineaKit[] = [];
  const colegio: LineaKit[] = [];
  const casa: LineaKit[] = [];
  const cuenta: LineaKit[] = [];
  for (const l of lineas) {
    const clase = clasificar(l);
    if (clase === "comprable" || ABSTENCIONES.includes(clase)) continue;
    if (esLibro(l)) libros.push(l);
    else if (esUniforme(l) || clase === "fuera_de_alcance") uniformes.push(l);
    else if (clase === "no_comprar") casa.push(l);
    else if (clase === "por_su_cuenta") cuenta.push(l);
    else colegio.push(l);
  }
  const grupos: GrupoFueraDelCarrito[] = [
    { clave: "libros", titulo: "Libros", lineas: libros },
    { clave: "colegio", titulo: "Los pide o los vende el colegio", lineas: colegio },
    { clave: "uniformes", titulo: "Uniformes", lineas: uniformes },
    { clave: "cuenta", titulo: "Consíguelos por tu cuenta", lineas: cuenta },
    { clave: "casa", titulo: "Usa el que ya tienes en casa", lineas: casa },
  ];
  return grupos.filter((g) => g.lineas.length > 0);
}
