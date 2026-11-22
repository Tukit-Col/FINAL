import type { ConceptoCatalogo } from "@tukit/contrato";

export interface VocabularioConceptos {
  atributos: string[];
  categorias: string[];
}

export function vocabularioDeConceptos(
  conceptos: readonly Pick<
    ConceptoCatalogo,
    "categoria" | "atributos_discriminantes" | "atributos_descriptivos"
  >[],
): VocabularioConceptos {
  const atributos = new Set<string>();
  const categorias = new Set<string>();
  for (const c of conceptos) {
    for (const a of c.atributos_discriminantes ?? []) atributos.add(a);
    for (const a of c.atributos_descriptivos ?? []) atributos.add(a);
    if (c.categoria) categorias.add(c.categoria);
  }
  const orden = (a: string, b: string) => a.localeCompare(b, "es");
  return { atributos: [...atributos].sort(orden), categorias: [...categorias].sort(orden) };
}
