// Las sugerencias del chat: una fila que nunca queda vacia. Solo ofrece pedidos que el
// asistente resuelve hoy (mas barato / mejor calidad por categoria, variar el kit, explicar,
// ayuda). Los pedidos en lote entran en la Fase 5, no se sugieren antes.

import type { PedidoAnterior } from "./espec";

export type UltimaRespuesta = "ninguna" | "ayuda" | "texto" | "propuesta";

export const AYUDA = "¿Qué puedes hacer?";
export const MAXIMO = 4;

const CATEGORIA_POR_DEFECTO = "cuadernos";

const nombre = (categoria: string) => categoria.trim().toLowerCase();

/**
 * Tres o cuatro sugerencias segun el contexto, sin repetir las ya tocadas en la ultima
 * ronda mientras alcancen otras, y siempre al menos tres.
 */
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
  // Relleno estable: lo que siempre se puede pedir.
  orden.push(`Más barato en ${cat}`, `Mejor calidad en ${cat}`, "Más variedad en mi kit", "¿Por qué este kit cuesta eso?");

  const unicas = [...new Set(orden)].filter((s) => s !== AYUDA);
  const frescas = unicas.filter((s) => !recientes.includes(s));
  // La ayuda va siempre al final como salida segura.
  const elegidas = [...frescas, ...unicas.filter((s) => recientes.includes(s))].slice(0, MAXIMO - 1);
  return [...elegidas, AYUDA];
}
