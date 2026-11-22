function comoTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  return typeof valor === "object" ? JSON.stringify(valor) : String(valor);
}

export const NO_EXIGIR = "*";

export interface FilaExigencia {
  clave: string;
  leido: string | null;
  curado: string | null;
  ajena: boolean;
  deducido: boolean;
}

interface Exigencia {
  atributos: Record<string, unknown>;
  atributos_leidos: Record<string, unknown>;
  atributos_discriminantes: readonly string[];
  atributos_deducidos?: readonly string[];
}

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

export function porAgregar(filas: readonly FilaExigencia[], discriminantes: readonly string[]): string[] {
  const usadas = new Set(filas.map((f) => f.clave));
  return discriminantes.filter((k) => !usadas.has(k));
}

export function exigidoDe(fila: FilaExigencia): string | null {
  if (fila.ajena) return null;
  if (fila.curado === NO_EXIGIR) return null;
  if (fila.curado !== null && fila.curado.trim() !== "") return fila.curado;
  return fila.leido;
}

export function paresCurados(filas: readonly FilaExigencia[]): { clave: string; valor: string }[] {
  return filas
    .filter((f) => f.curado !== null)
    .map((f) => ({ clave: f.clave, valor: (f.curado ?? "").trim() }));
}

export function mismosAtributos(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  const claves = Object.keys(a);
  if (claves.length !== Object.keys(b).length) return false;
  return claves.every((k) => k in b && a[k] === b[k]);
}

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
