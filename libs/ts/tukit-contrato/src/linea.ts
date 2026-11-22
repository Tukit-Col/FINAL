import type { Dinero, LineaKit } from "./contrato";

export type ClaseLinea =
  | "comprable"
  | "hueco"
  | "sin_match"
  | "pendiente_revision"
  | "licencia_digital"
  | "no_comprar"
  | "diferido"
  | "fuera_de_alcance"
  | "por_su_cuenta"
  | "informativa";

export function clasificar(linea: LineaKit): ClaseLinea {
  if (linea.tipo === "licencia_digital") return "licencia_digital";
  if (linea.tipo === "no_comprar") return "no_comprar";
  if (linea.tipo === "diferido") return "diferido";
  if (linea.tipo === "uniforme") return "fuera_de_alcance";
  if (linea.tipo === "otro") return "por_su_cuenta";
  if (linea.informativa) return "informativa";
  if (linea.tipo === "texto" && !linea.producto_elegido) return "por_su_cuenta";
  if (
    linea.tipo === "libro_libre" &&
    !linea.producto_elegido &&
    linea.estado_resolucion === "HUECO_CATALOGO"
  ) {
    return "por_su_cuenta";
  }
  if (linea.estado_resolucion === "HUECO_CATALOGO") return "hueco";
  if (linea.estado_resolucion === "SIN_MATCH") return "sin_match";
  if (linea.estado_resolucion === "AMBIGUO") return "pendiente_revision";
  return "comprable";
}

export function entraAlTotal(linea: LineaKit): boolean {
  return clasificar(linea) === "comprable" && typeof linea.subtotal_linea === "number";
}

export function esInformativaOExterna(linea: LineaKit): boolean {
  const clase = clasificar(linea);
  return (
    clase === "informativa" ||
    clase === "licencia_digital" ||
    clase === "no_comprar" ||
    clase === "diferido" ||
    clase === "fuera_de_alcance" ||
    clase === "por_su_cuenta"
  );
}

export function esAbstencion(linea: LineaKit): boolean {
  const clase = clasificar(linea);
  return clase === "hueco" || clase === "sin_match";
}

export const TITULO_CLASE: Record<ClaseLinea, string> = {
  comprable: "En tu carrito",
  hueco: "No lo tenemos",
  sin_match: "No entendimos qué pide",
  pendiente_revision: "Lo está revisando una persona",
  licencia_digital: "Se paga por fuera",
  no_comprar: "No hay que comprarlo",
  diferido: "El colegio lo pedirá después",
  fuera_de_alcance: "Uniformes: fuera de Tukit por ahora",
  por_su_cuenta: "Lo consigues por tu cuenta",
  informativa: "Lo gestiona el colegio",
};

export function razonDeNoCobrar(linea: LineaKit): string | null {
  switch (clasificar(linea)) {
    case "comprable":
      return linea.unidades_a_comprar === 0 && linea.mensaje ? linea.mensaje : null;
    case "hueco":
      return (
        linea.mensaje ?? "Entendimos que pides esto y hoy no lo tenemos en el catálogo."
      );
    case "sin_match":
      return "No logramos entender este renglón de la lista. Lo va a mirar una persona.";
    case "pendiente_revision":
      return "Hay varias opciones parecidas y ninguna gana clara. Una persona lo decide antes de cobrarte.";
    case "licencia_digital":
      return (
        linea.nota ?? "Esta licencia se paga directamente con el proveedor y no va en el carrito."
      );
    case "no_comprar":
      return linea.nota ?? "El colegio indica usar el que ya tienes en casa.";
    case "diferido":
      return "El colegio lo va a pedir durante el año. Te avisamos cuando se pueda comprar.";
    case "fuera_de_alcance":
      return (
        linea.instruccion_colegio ??
        "Los uniformes todavía no los surtimos. Te lo dejamos visible para que no se te pase."
      );
    case "por_su_cuenta":
      return (
        linea.instruccion_colegio ??
        linea.mensaje ??
        "Tukit no lo vende: consíguelo por tu cuenta. Te lo dejamos visible para que no se te pase."
      );
    case "informativa":
      return (
        linea.instruccion_colegio ??
        "El colegio o la editorial lo venden directamente, así que no lo podemos cobrar."
      );
  }
}

export function agruparPorClase(lineas: readonly LineaKit[]): Map<ClaseLinea, LineaKit[]> {
  const grupos = new Map<ClaseLinea, LineaKit[]>();
  for (const linea of lineas) {
    const clase = clasificar(linea);
    const actual = grupos.get(clase);
    if (actual) actual.push(linea);
    else grupos.set(clase, [linea]);
  }
  return grupos;
}

export const ORDEN_SECCIONES: readonly ClaseLinea[] = [
  "hueco",
  "sin_match",
  "pendiente_revision",
  "licencia_digital",
  "informativa",
  "diferido",
  "no_comprar",
  "fuera_de_alcance",
  "por_su_cuenta",
  "comprable",
];

const CONCEPTO_LIBRO_CON_TITULO = "C134";
const SE_COMPRA_EN_LIBRERIA = /^\s*se compra en (?:una )?librer[ií]a/i;

export function esLibro(linea: LineaKit): boolean {
  if (linea.tipo === "texto" || linea.tipo === "libro_libre") return true;
  if (linea.tipo !== "otro") return false;
  return (
    linea.concepto === CONCEPTO_LIBRO_CON_TITULO ||
    SE_COMPRA_EN_LIBRERIA.test(linea.instruccion_colegio ?? "")
  );
}

export function instruccionCorta(linea: LineaKit): string | null {
  const texto = linea.instruccion_colegio?.trim();
  if (!texto) return null;
  const pregunta = texto.match(/Pregunta en el colegio(?: \([^)]*\))?/i);
  if (pregunta) return pregunta[0];
  const compra = texto.match(/^Se (?:compra|adquiere|consigue) (?:en|con) [^:.;]+/i);
  if (compra) return compra[0].trim();
  const frase = (texto.split(/[:.;]/, 1)[0] ?? "").trim();
  return frase && frase.length <= 60 ? frase : null;
}

function conMinuscula(frase: string): string {
  return frase.charAt(0).toLowerCase() + frase.slice(1);
}

export function esUniforme(linea: LineaKit): boolean {
  return linea.tipo === "uniforme";
}

function nombreDeSitio(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}

export function dondeComprar(linea: LineaKit): string | null {
  const dicho = linea.se_compra_en?.trim();
  if (dicho) return dicho;
  const editorial = linea.edicion?.editorial?.trim();
  if (editorial && esLibro(linea)) return editorial;
  const sitio = nombreDeSitio(linea.url_externa);
  if (sitio) return sitio;
  const tienda = linea.producto_elegido?.ofertas?.[0]?.tienda?.trim();
  return tienda || null;
}

export type EstadoPrecio =
  | { tipo: "precio"; valor: Dinero }
  | { tipo: "descartado"; ahorro: Dinero | null }
  | { tipo: "sin_cobro"; titulo: string };

export function estadoDePrecio(linea: LineaKit): EstadoPrecio {
  if (linea.descartado) {
    return { tipo: "descartado", ahorro: linea.subtotal_descartado ?? null };
  }
  const clase = clasificar(linea);
  const donde = dondeComprar(linea);
  const libro = esLibro(linea);
  const instruccion = instruccionCorta(linea);
  if (
    instruccion &&
    !linea.se_compra_en?.trim() &&
    (clase === "por_su_cuenta" || clase === "fuera_de_alcance" || clase === "informativa")
  ) {
    const prefijo = libro ? "Libro: " : clase === "fuera_de_alcance" ? "Uniforme: " : "";
    return { tipo: "sin_cobro", titulo: prefijo ? prefijo + conMinuscula(instruccion) : instruccion };
  }
  switch (clase) {
    case "comprable":
      if (typeof linea.subtotal_linea === "number" && linea.subtotal_linea > 0) {
        return { tipo: "precio", valor: linea.subtotal_linea };
      }
      if (linea.unidades_a_comprar === 0) {
        return { tipo: "sin_cobro", titulo: "Ya va en otro renglón" };
      }
      return {
        tipo: "sin_cobro",
        titulo: donde ? `Sin precio aún — se compra en ${donde}` : "Sin precio aún",
      };
    case "hueco":
      return { tipo: "sin_cobro", titulo: "Todavía no lo tenemos" };
    case "sin_match":
    case "pendiente_revision":
      return { tipo: "sin_cobro", titulo: "Una persona lo está revisando" };
    case "licencia_digital":
      return {
        tipo: "sin_cobro",
        titulo: `Licencia digital: se compra en ${donde ?? "la plataforma del proveedor"}`,
      };
    case "informativa":
      return {
        tipo: "sin_cobro",
        titulo: libro
          ? `Libro: se compra en ${donde ?? "la editorial o la librería"}`
          : donde
            ? `Lo vende ${donde}`
            : "Lo entrega el colegio",
      };
    case "diferido":
      return { tipo: "sin_cobro", titulo: "El colegio lo pedirá después" };
    case "no_comprar":
      return { tipo: "sin_cobro", titulo: "Ya lo tienes en casa" };
    case "fuera_de_alcance":
      return {
        tipo: "sin_cobro",
        titulo: `Uniforme: se compra en ${donde ?? "la tienda que indique el colegio"}`,
      };
    case "por_su_cuenta":
      return {
        tipo: "sin_cobro",
        titulo: libro
          ? `Libro: se compra en ${donde ?? "la editorial o la librería"}`
          : donde
            ? `Se compra por tu cuenta en ${donde}`
            : "Se compra por tu cuenta",
      };
  }
}

export function hayQueCobrar(total: Dinero | null | undefined): total is Dinero {
  return typeof total === "number" && total > 0;
}

export function etiquetaEmpaque(unidadesPorEmpaque: number, unidadesAComprar: number): string {
  const empaque = unidadesPorEmpaque > 1 ? `Empaque de ${unidadesPorEmpaque}` : "Por unidad";
  return unidadesAComprar > 1 ? `${empaque} · compras ${unidadesAComprar}` : empaque;
}

export function lineasQueSuman(lineas: readonly LineaKit[]): LineaKit[] {
  return lineas.filter((l) => !l.descartado && entraAlTotal(l));
}

export function normalizarPersonaje(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[\s_\-]+/g, "");
}

export type PersonajesPedidos = Readonly<Record<string, readonly string[]>>;

function pedidoPorSuHijo(linea: LineaKit, pedidos: PersonajesPedidos): boolean {
  const personaje = linea.producto_elegido?.personaje;
  if (!personaje) return false;
  const delHijo = pedidos[linea.hijo ?? ""] ?? [];
  const clave = normalizarPersonaje(personaje);
  return delHijo.some((p) => normalizarPersonaje(p) === clave);
}

export function productosDelPersonaje(
  lineas: readonly LineaKit[],
  pedidos?: PersonajesPedidos,
): LineaKit[] {
  const vistos = new Set<string>();
  const salida: LineaKit[] = [];
  for (const linea of lineas) {
    const producto = linea.producto_elegido;
    if (!producto?.personaje || linea.descartado || linea.informativa) continue;
    if (pedidos && !pedidoPorSuHijo(linea, pedidos)) continue;
    const clave = `${linea.hijo ?? ""}\u0000${producto.sku}`;
    if (vistos.has(clave)) continue;
    vistos.add(clave);
    salida.push(linea);
  }
  return salida;
}

export function personajesDelKit(lineas: readonly LineaKit[], pedidos?: PersonajesPedidos): string[] {
  return [...new Set(productosDelPersonaje(lineas, pedidos).map((l) => l.producto_elegido!.personaje!))];
}

export function personajesPorHijo(
  lineas: readonly LineaKit[],
  pedidos?: PersonajesPedidos,
): { hijo: string; personaje: string; lineas: LineaKit[] }[] {
  const grupos: { hijo: string; personaje: string; lineas: LineaKit[] }[] = [];
  for (const linea of productosDelPersonaje(lineas, pedidos)) {
    const hijo = linea.hijo ?? "";
    const personaje = linea.producto_elegido!.personaje!;
    const clave = normalizarPersonaje(personaje);
    const grupo = grupos.find((g) => g.hijo === hijo && normalizarPersonaje(g.personaje) === clave);
    if (grupo) grupo.lineas.push(linea);
    else grupos.push({ hijo, personaje, lineas: [linea] });
  }
  return grupos;
}

export interface ReglaDeClave {
  id: string;
  texto: string;
  cumple: boolean;
}

export const CLAVE_MINIMA = 8;

export function reglasDeClave(clave: string): ReglaDeClave[] {
  return [
    {
      id: "largo",
      texto: `Al menos ${CLAVE_MINIMA} caracteres`,
      cumple: clave.length >= CLAVE_MINIMA,
    },
  ];
}

export function claveValida(clave: string): boolean {
  return reglasDeClave(clave).every((r) => r.cumple);
}
