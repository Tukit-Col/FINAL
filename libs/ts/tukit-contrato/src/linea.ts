// Como leer una linea de kit.
//
// El contrato modela en una sola forma cosas que en pantalla se comportan muy
// distinto: un lapiz con precio, una licencia con link de pago, un diccionario
// que no hay que comprar, un texto que vende la editorial en el colegio y un
// hueco de catalogo. Estas reglas viven aqui y no en cada componente porque
// son reglas del contrato, no decisiones de diseno, y repetirlas en `web` y en
// `admin` es como se desincronizan.

import type { Dinero, LineaKit } from "./contrato";

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
  | "por_su_cuenta" // tipo `otro`: Tukit decidio no venderlo (audifonos, un titere)
  | "informativa"; // la vende el colegio o la editorial, no Tukit

export function clasificar(linea: LineaKit): ClaseLinea {
  if (linea.tipo === "licencia_digital") return "licencia_digital";
  if (linea.tipo === "no_comprar") return "no_comprar";
  if (linea.tipo === "diferido") return "diferido";
  if (linea.tipo === "uniforme") return "fuera_de_alcance";
  // Antes de `informativa`: un `otro` tambien es informativo, pero decirle al
  // acudiente que "lo gestiona el colegio" era falso; lo compra el por su cuenta.
  if (linea.tipo === "otro") return "por_su_cuenta";
  if (linea.informativa) return "informativa";
  // Un texto con titulo y editorial (no informativo: se compra en libreria) no
  // se busca en el catalogo y llega como SIN_MATCH, porque la edicion aun no se
  // resuelve. Mostrarlo como "No entendimos que pide" era falso: se entendio.
  if (linea.tipo === "texto" && !linea.producto_elegido) return "por_su_cuenta";
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
    clase === "fuera_de_alcance" ||
    clase === "por_su_cuenta"
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
  por_su_cuenta: "Lo consigues por tu cuenta",
  informativa: "Lo gestiona el colegio",
};

/**
 * Por que la linea no se cobra, en lenguaje llano y sin culpar al acudiente.
 * `null` para las que si se cobran.
 */
export function razonDeNoCobrar(linea: LineaKit): string | null {
  switch (clasificar(linea)) {
    case "comprable":
      // En cero unidades porque otra linea ya la cubre: la herramienta pedida
      // en varias materias o la que se compra junto con la del hermano. El
      // mensaje dice donde quedo; sin el, se veia el producto y nada mas.
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
  "por_su_cuenta",
  "comprable",
];

// ------------------------------------------------ Lo que el acudiente lee
//
// Reglas de presentacion que dependen del contrato y no de un componente: que
// se muestra donde habria un precio, que lineas son libros o uniformes, como se
// dice un empaque, que productos hacen "Fan" a un kit y las reglas de la
// contrasena. Viven aqui, junto a `clasificar`, para probarlas sin pintar nada.

// El concepto del plan lector y los textos con titulo. Una linea suya sin
// edicion verificada llega como `otro` con "Se compra en librería", pero sigue
// siendo un libro y va en la seccion de libros. Como esa linea no se busca en
// el catalogo no trae `concepto` (no tiene resolucion): la instruccion basta.
const CONCEPTO_LIBRO_CON_TITULO = "C134";
const SE_COMPRA_EN_LIBRERIA = /^\s*se compra en (?:una )?librer[ií]a/i;

/** Un libro de texto o de lectura: se compra donde la editorial o la libreria. */
export function esLibro(linea: LineaKit): boolean {
  if (linea.tipo === "texto" || linea.tipo === "libro_libre") return true;
  if (linea.tipo !== "otro") return false;
  return (
    linea.concepto === CONCEPTO_LIBRO_CON_TITULO ||
    SE_COMPRA_EN_LIBRERIA.test(linea.instruccion_colegio ?? "")
  );
}

/**
 * La instruccion del colegio en una frase corta, para ponerla donde iria el
 * precio: "Se compra en librería", "Pregunta en el colegio (601 427 2365)".
 * La curaduria la escribe como frase y luego la fuente y la fecha; aqui se
 * toma solo la frase. `null` si no hay instruccion o es demasiado larga para
 * un titulo (en ese caso se lee completa como razon de no cobrar).
 */
export function instruccionCorta(linea: LineaKit): string | null {
  const texto = linea.instruccion_colegio?.trim();
  if (!texto) return null;
  const pregunta = texto.match(/Pregunta en el colegio(?: \([^)]*\))?/i);
  if (pregunta) return pregunta[0];
  const compra = texto.match(/^Se (?:compra|adquiere|consigue) (?:en|con) [^:.;]+/i);
  if (compra) return compra[0].trim();
  // split siempre devuelve al menos un trozo, pero el tipo no lo garantiza.
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

/**
 * Donde se compra lo que Tukit no cobra, con el dato mas especifico que haya:
 * lo que diga el catalogo (`se_compra_en`), la editorial de la edicion exigida,
 * el sitio del proveedor o la tienda de la primera oferta. `null` si nada lo
 * dice: la pantalla usa entonces un texto generico en vez de inventar un nombre.
 */
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

/**
 * Lo que se pinta en lugar del precio de una linea. Nunca `$ 0`: o hay un valor
 * real que cobrar, o una frase que dice por que no se cobra y donde se
 * consigue.
 */
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
  // Lo que no se cobra y el colegio dice como conseguir: esa frase va en lugar
  // del precio, salvo que el catalogo ya nombre la tienda (`se_compra_en`).
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

/** Hay algo que cobrar: un total en cero no se muestra como `$ 0`, se explica. */
export function hayQueCobrar(total: Dinero | null | undefined): total is Dinero {
  return typeof total === "number" && total > 0;
}

/**
 * Como se dice el empaque de una opcion: "Empaque de 12" y no "12". Si se
 * compra mas de un empaque, lo dice.
 */
export function etiquetaEmpaque(unidadesPorEmpaque: number, unidadesAComprar: number): string {
  const empaque = unidadesPorEmpaque > 1 ? `Empaque de ${unidadesPorEmpaque}` : "Por unidad";
  return unidadesAComprar > 1 ? `${empaque} · compras ${unidadesAComprar}` : empaque;
}

/** Las lineas de un kit que SUMAN al total hoy: con precio y sin descartar. */
export function lineasQueSuman(lineas: readonly LineaKit[]): LineaKit[] {
  return lineas.filter((l) => !l.descartado && entraAlTotal(l));
}

/** "Spider-Man" == "spiderman": sin tildes, mayusculas, guiones ni espacios (igual que el backend). */
export function normalizarPersonaje(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[\s_\-]+/g, "");
}

/** Los personajes que pidio cada hijo, por la `hijo` de sus lineas (solo franquicias). */
export type PersonajesPedidos = Readonly<Record<string, readonly string[]>>;

function pedidoPorSuHijo(linea: LineaKit, pedidos: PersonajesPedidos): boolean {
  const personaje = linea.producto_elegido?.personaje;
  if (!personaje) return false;
  const delHijo = pedidos[linea.hijo ?? ""] ?? [];
  const clave = normalizarPersonaje(personaje);
  return delHijo.some((p) => normalizarPersonaje(p) === clave);
}

/**
 * Los productos con personaje de un kit, sin repetir y sin los descartados: lo
 * que hace "Fan" a un kit Fan. Se muestra primero, antes de la lista completa.
 * Con `pedidos` solo cuenta las lineas cuyo personaje pidio SU hijo: un Bluey
 * que llego por "mas variedad" o la Minnie del hermano no hacen Fan a nadie.
 */
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
    // Se deduplica por (hijo, sku), no por sku a secas: dos hermanos pueden
    // compartir el MISMO producto de personaje (uno consolidado sobre el otro) y
    // ambos deben verlo en SU franja. Deduplicar global borraba al segundo hijo.
    const clave = `${linea.hijo ?? ""}\u0000${producto.sku}`;
    if (vistos.has(clave)) continue;
    vistos.add(clave);
    salida.push(linea);
  }
  return salida;
}

/** Los personajes distintos de un kit, para el titular de la franja Fan. */
export function personajesDelKit(lineas: readonly LineaKit[], pedidos?: PersonajesPedidos): string[] {
  return [...new Set(productosDelPersonaje(lineas, pedidos).map((l) => l.producto_elegido!.personaje!))];
}

/**
 * La franja Fan por hijo: un grupo por (hijo, personaje) en el orden del kit,
 * con sus productos. Un hijo neutral (sin personaje pedido) no aparece.
 */
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

// ------------------------------------------------- Contrasena y consentimiento

/** Una regla de la contrasena, dicha en palabras sencillas. */
export interface ReglaDeClave {
  id: string;
  texto: string;
  cumple: boolean;
}

/** Largo minimo que exige Identidad (`CLAVE_MINIMA`). */
export const CLAVE_MINIMA = 8;

/**
 * Las reglas de la contrasena y cuales ya cumple lo escrito. Hoy el unico
 * requisito real es el largo (Identidad no exige mayusculas ni simbolos); la
 * lista se arma aqui para que la pantalla muestre las reglas ANTES de escribir.
 */
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
