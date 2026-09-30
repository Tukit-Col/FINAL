// Lógica pura del editor de atributos (Task D2). Separada del componente para
// poder probarla sin runner de React: es donde vivía el bug real.
//
// El editor plano solo mostraba las claves que el producto ya traía y las
// mandaba como texto. Aquí se hacen las dos cosas que faltaban:
//
//  1. Pre-poblar TODAS las claves que el CONCEPTO declara (discriminantes +
//     descriptivos), no solo las que el producto trae. El caso del screenshot:
//     un cuaderno con solo `materias` también ve `hojas` y `rayado` (que el
//     concepto declara) como filas vacías, listas para llenar. Fila vacía =
//     clave no afirmada (no se guarda), consistente con `serializarAtributos`.
//  2. Repartir en tres grupos: `discriminantes` ("filtra la búsqueda"),
//     `descriptivos` ("solo informativo") y `libres` (claves que el producto
//     trae pero el concepto no declara — no se pierden al editar).
//
// El tipado al guardar lo hace `serializarAtributos` del contrato (Task C5);
// aquí solo se arma la vista. La conversión de valor a texto para la caja de
// input es la misma regla que usaba el componente (`comoTexto`).

export interface ParAtributo {
  clave: string;
  valor: string;
}

export interface GruposAtributos {
  discriminantes: ParAtributo[];
  descriptivos: ParAtributo[];
  libres: ParAtributo[];
}

/** Convierte un valor tipado de la base al texto que muestra la caja de input. */
export function comoTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  if (typeof valor === "object") return JSON.stringify(valor);
  return String(valor);
}

/**
 * Arma las filas iniciales del editor a partir de los atributos del producto y
 * las dos listas de claves que el concepto declara.
 *
 * - `discriminantes`/`descriptivos`: una fila por cada clave declarada, en el
 *   orden del concepto; con su valor si el producto la trae, vacía si no.
 * - `libres`: las claves que el producto trae pero el concepto no declara (no
 *   se pierden), en el orden en que vienen.
 */
export function filasDeAtributos(
  atributos: Record<string, unknown>,
  discriminantes: readonly string[],
  descriptivos: readonly string[],
): GruposAtributos {
  const declaradas = new Set<string>([...discriminantes, ...descriptivos]);

  const fila = (clave: string): ParAtributo => ({
    clave,
    valor: clave in atributos ? comoTexto(atributos[clave]) : "",
  });

  const libres = Object.keys(atributos)
    .filter((k) => !declaradas.has(k))
    .map((k) => ({ clave: k, valor: comoTexto(atributos[k]) }));

  return {
    discriminantes: discriminantes.map(fila),
    descriptivos: descriptivos.map(fila),
    libres,
  };
}
