import type { PedidoAnterior } from "./espec";

export type UltimaRespuesta = "ninguna" | "ayuda" | "texto" | "propuesta";

export const AYUDA = "¿Qué puedes hacer?";
export const MAXIMO = 4;

const CATEGORIA_POR_DEFECTO = "cuadernos";

const nombre = (categoria: string) => categoria.trim().toLowerCase();

export function sugerenciasDe(
  ultima: UltimaRespuesta,
  anterior: PedidoAnterior | null,
  recientes: readonly string[] = [],
): string[] {
  const cat = anterior ? nombre(anterior.categoria) : CATEGORIA_POR_DEFECTO;
  const orden: string[] = [];

  if (ultima === "propuesta" && anterior) {
    if (anterior.accion === "mas_barato") orden.push(`Mejor calidad en ${cat}`);
    else if (anterior.accion === "mejor_calidad") orden.push(`Más barato en ${cat}`);
    else orden.push("Más barato en cuadernos");
    orden.push("¿Por qué este kit cuesta eso?", "Más variedad en mi kit");
  } else if (ultima === "ayuda") {
    orden.push(`Más barato en ${cat}`, "Más variedad en mi kit", "¿Por qué este kit cuesta eso?");
  } else {
    orden.push(`Más barato en ${cat}`, `Mejor calidad en ${cat}`, "Más variedad en mi kit");
  }
  orden.push(`Más barato en ${cat}`, `Mejor calidad en ${cat}`, "Más variedad en mi kit", "¿Por qué este kit cuesta eso?");

  const unicas = [...new Set(orden)].filter((s) => s !== AYUDA);
  const frescas = unicas.filter((s) => !recientes.includes(s));
  const elegidas = [...frescas, ...unicas.filter((s) => recientes.includes(s))].slice(0, MAXIMO - 1);
  return [...elegidas, AYUDA];
}
