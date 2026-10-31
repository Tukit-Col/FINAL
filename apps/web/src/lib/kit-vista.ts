// Las reglas puras de lo que el renglón del kit le muestra al acudiente,
// separadas del componente para probarlas sin navegador.

// Un hijo del trabajo tal como lo devuelve `GET /v1/trabajos/{id}`. La ruta
// rápida no trae `referencia` (sus renglones dicen "canonico").
export interface HijoDelTrabajo {
  referencia?: string;
  colegio_id?: string;
  grado?: string;
}

// Lo justo de una matrícula del portador para ponerle nombre a su hijo.
export interface ApodoMatricula {
  colegio_id: string;
  grado: string;
  apodo: string | null;
}

// A qué hijo pertenece cada renglón. La `hijo` de la línea es una referencia
// interna ("canonico", "hijo-0"): nunca se pinta. Se cruza con el colegio y el
// grado del hijo del trabajo y, si una sola matrícula del acudiente casa con un
// solo apodo, ese es el nombre. Si no hay apodo y el kit es de un solo hijo no
// hay nada que distinguir y no se pinta pastilla; con varios hijos, el que no
// tiene apodo se llama "Hijo N" por su orden en el kit.
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
    const apodos = new Set(
      matriculas
        .filter((m) => hijo && m.colegio_id === hijo.colegio_id && m.grado === hijo.grado)
        .map((m) => m.apodo?.trim() ?? "")
        .filter(Boolean),
    );
    if (apodos.size === 1) etiquetas.set(referencia, [...apodos][0]!);
    else if (distintas.length > 1) etiquetas.set(referencia, `Hijo ${indice + 1}`);
  });
  return etiquetas;
}

// La pista de tienda bajo el precio. La normalización del contrato sintetiza
// una oferta con la tienda vacía cuando el backend solo manda el precio: sin
// un nombre de verdad no hay pista, en vez de un "en" que no dice dónde.
export function pistaDeTienda(ofertas: readonly { tienda: string }[]): string | null {
  const tiendas = ofertas.map((o) => o.tienda.trim()).filter(Boolean);
  if (tiendas.length === 0) return null;
  return tiendas.length > 1 ? `en ${tiendas[0]} · ${tiendas.length} tiendas` : `en ${tiendas[0]}`;
}
