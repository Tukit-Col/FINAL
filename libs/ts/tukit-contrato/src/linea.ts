// Como leer una linea de kit.
//
// El contrato modela en una sola forma cosas que en pantalla se comportan muy
// distinto: un lapiz con precio, una licencia con link de pago, un diccionario
// que no hay que comprar, un texto que vende la editorial en el colegio y un
// hueco de catalogo. Estas reglas viven aqui y no en cada componente porque
// son reglas del contrato, no decisiones de diseno, y repetirlas en `web` y en
// `admin` es como se desincronizan.

import type { LineaKit } from "./contrato";

/**
 * Para que sirve cada linea en pantalla. El orden en que se prueba importa:
 * `informativa` gana sobre el tipo, porque un `texto` informativo y un `texto`
 * resuelto se pintan distinto aunque compartan `tipo`.
 */
export type ClaseLinea =
  | "comprable" // producto elegido, con precio, entra al total
  | "hueco" // se entendio que pide y el catalogo no lo tiene
  | "sin_match" // no se entendio que pide
  | "pendiente_revision" // ambiguo: hay candidatos y ninguno domina
  | "licencia_digital" // pago externo, con link
  | "no_comprar" // "el disponible en casa"
  | "diferido" // se solicitara mas adelante
  | "fuera_de_alcance" // uniformes: declarado fuera de v1
  | "informativa"; // la vende el colegio o la editorial, no Tukit

export function clasificar(linea: LineaKit): ClaseLinea {
  if (linea.tipo === "licencia_digital") return "licencia_digital";
  if (linea.tipo === "no_comprar") return "no_comprar";
  if (linea.tipo === "diferido") return "diferido";
  if (linea.tipo === "uniforme") return "fuera_de_alcance";
  if (linea.informativa) return "informativa";
  if (linea.estado_resolucion === "HUECO_CATALOGO") return "hueco";
  if (linea.estado_resolucion === "SIN_MATCH") return "sin_match";
  if (linea.estado_resolucion === "AMBIGUO") return "pendiente_revision";
  return "comprable";
}

/** Solo estas entran al total del kit y al carrito (§5.1.1). */
export function entraAlTotal(linea: LineaKit): boolean {
  return clasificar(linea) === "comprable" && typeof linea.subtotal_linea === "number";
}

/** Se muestra pero no se cobra: el acudiente necesita saber que existe. */
export function esInformativaOExterna(linea: LineaKit): boolean {
  const clase = clasificar(linea);
  return (
    clase === "informativa" ||
    clase === "licencia_digital" ||
    clase === "no_comprar" ||
    clase === "diferido" ||
    clase === "fuera_de_alcance"
  );
}

/** Lo que Tukit no pudo responder y por lo tanto se abstiene de ofrecer. */
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
  informativa: "Lo gestiona el colegio",
};

/**
 * Por que la linea no se cobra, en lenguaje llano y sin culpar al acudiente.
 * `null` para las que si se cobran.
 */
export function razonDeNoCobrar(linea: LineaKit): string | null {
  switch (clasificar(linea)) {
    case "comprable":
      return null;
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
      return "Los uniformes todavía no los surtimos. Te lo dejamos visible para que no se te pase.";
    case "informativa":
      return (
        linea.instruccion_colegio ??
        "El colegio o la editorial lo venden directamente, así que no lo podemos cobrar."
      );
  }
}

/** Agrupa las lineas de un kit por como se van a pintar, conservando el orden. */
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

/** El orden en que las secciones aparecen: primero lo que duele, luego lo que se compra. */
export const ORDEN_SECCIONES: readonly ClaseLinea[] = [
  "hueco",
  "sin_match",
  "pendiente_revision",
  "licencia_digital",
  "informativa",
  "diferido",
  "no_comprar",
  "fuera_de_alcance",
  "comprable",
];
