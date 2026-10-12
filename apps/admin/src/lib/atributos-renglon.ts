// Lógica pura de «Atributos que se exigen» en el editor de un renglón de la
// lista. Aparte del componente por lo mismo que `atributos-editor.ts`: el admin
// no tiene runner de componentes y esto se prueba con `node --test`.
//
// La regla es la de la ruta rápida (`_renglon_resuelto` del catálogo): se exige
// lo que el texto dice de los atributos discriminantes del concepto; lo curado
// manda sobre lo leído, y el valor `*` (NO_EXIGIR) quita un atributo leído.
// Aquí no se vuelve a LEER el texto —eso lo hace el backend y llega en
// `atributos_leidos`—: solo se arma la vista y lo que se guarda.

// La misma conversión que `comoTexto` de `atributos-editor.ts`. No se importa:
// `node --test` exige la extensión `.ts` en el import y el build de Next la
// rechaza, y son dos líneas.
function comoTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  return typeof valor === "object" ? JSON.stringify(valor) : String(valor);
}

/** El valor curado que hace que un atributo leído del texto no se exija. */
export const NO_EXIGIR = "*";

export interface FilaExigencia {
  clave: string;
  /** Lo que se leyó del texto, como texto; `null` si el texto no lo dice. */
  leido: string | null;
  /** Lo curado: `null` sin curaduría, `NO_EXIGIR` para no exigirlo, o el valor. */
  curado: string | null;
  /** Curado con una clave que el concepto no filtra: no cambia nada (p. ej.
   *  quedó de un concepto anterior). Se muestra para poder quitarlo. */
  ajena: boolean;
  /** Lo leído no lo dice el texto: el backend lo dedujo (`atributos_deducidos`,
   *  hoy el «más de uno» de `caja de…`), y la ruta rápida lo suelta si ningún
   *  juego cumple. */
  deducido: boolean;
}

interface Exigencia {
  atributos: Record<string, unknown>;
  atributos_leidos: Record<string, unknown>;
  atributos_discriminantes: readonly string[];
  atributos_deducidos?: readonly string[];
}

/**
 * Una fila por cada atributo que hoy se lee o se cura: primero los
 * discriminantes, en el orden del concepto; después lo curado con claves que el
 * concepto no filtra. Los discriminantes que ni se leen ni se curan no salen:
 * son los que se pueden «agregar» (`porAgregar`).
 */
export function filasDeExigencia(item: Exigencia): FilaExigencia[] {
  const discriminantes = new Set(item.atributos_discriminantes);
  const deducidos = new Set(item.atributos_deducidos ?? []);
  const fila = (clave: string): FilaExigencia => ({
    clave,
    leido: clave in item.atributos_leidos ? comoTexto(item.atributos_leidos[clave]) : null,
    curado: clave in item.atributos ? comoTexto(item.atributos[clave]) : null,
    ajena: !discriminantes.has(clave),
    deducido: deducidos.has(clave) && clave in item.atributos_leidos,
  });
  const propias = item.atributos_discriminantes
    .filter((k) => k in item.atributos_leidos || k in item.atributos)
    .map(fila);
  const ajenas = Object.keys(item.atributos)
    .filter((k) => !discriminantes.has(k))
    .map(fila);
  return [...propias, ...ajenas];
}

/** Los discriminantes del concepto que todavía no tienen fila. */
export function porAgregar(filas: readonly FilaExigencia[], discriminantes: readonly string[]): string[] {
  const usadas = new Set(filas.map((f) => f.clave));
  return discriminantes.filter((k) => !usadas.has(k));
}

/**
 * Lo que la ruta rápida exigiría con esta fila: el valor, o `null` si no se
 * exige. Lo curado manda; `*` lo quita; una curaduría vacía no afirma nada y
 * vale lo leído; una clave ajena no filtra.
 */
export function exigidoDe(fila: FilaExigencia): string | null {
  if (fila.ajena) return null;
  if (fila.curado === NO_EXIGIR) return null;
  if (fila.curado !== null && fila.curado.trim() !== "") return fila.curado;
  return fila.leido;
}

/**
 * Los pares clave/valor de la curaduría, listos para `serializarAtributos` (que
 * tipa `100` → número y descarta el valor vacío). `*` viaja tal cual.
 */
export function paresCurados(filas: readonly FilaExigencia[]): { clave: string; valor: string }[] {
  return filas
    .filter((f) => f.curado !== null)
    .map((f) => ({ clave: f.clave, valor: (f.curado ?? "").trim() }));
}

/** Igualdad de dos mapas de atributos sin importar el orden de las claves. */
export function mismosAtributos(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const claves = Object.keys(a);
  if (claves.length !== Object.keys(b).length) return false;
  return claves.every((k) => k in b && a[k] === b[k]);
}

/**
 * Por concepto y atributo, los valores que declaran sus productos: lo que
 * conviene sugerir al curar, porque es lo que de verdad puede cumplirse. Solo
 * los atributos que el concepto filtra y valores simples, ordenados.
 */
export function valoresDeProductos(
  conceptos: readonly {
    codigo: string;
    atributos_discriminantes: readonly string[];
    productos: readonly { atributos: Record<string, unknown> }[];
  }[],
): Record<string, Record<string, string[]>> {
  const salida: Record<string, Record<string, string[]>> = {};
  for (const c of conceptos) {
    const porClave: Record<string, string[]> = {};
    for (const clave of c.atributos_discriminantes) {
      const vistos = new Set<string>();
      for (const p of c.productos) {
        const v = p.atributos?.[clave];
        if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") vistos.add(String(v));
      }
      if (vistos.size > 0) porClave[clave] = [...vistos].sort((x, y) => x.localeCompare(y, "es", { numeric: true }));
    }
    if (Object.keys(porClave).length > 0) salida[c.codigo] = porClave;
  }
  return salida;
}
