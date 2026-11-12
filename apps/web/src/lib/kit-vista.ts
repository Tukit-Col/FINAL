// Las reglas puras de lo que el renglón del kit le muestra al acudiente,
// separadas del componente para probarlas sin navegador.

// Un hijo del trabajo tal como lo devuelve `GET /v1/trabajos/{id}`. La ruta
// rápida no trae `referencia` (sus renglones dicen "canonico").
export interface HijoDelTrabajo {
  referencia?: string;
  colegio_id?: string;
  grado?: string;
  // Lo que el acudiente escribió para este hijo en /empezar.
  apodo?: string;
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
    const propio = hijo?.apodo?.trim();
    // Las matrículas solo identifican al hijo si ningún hermano comparte su
    // colegio y grado; si no, el mismo apodo caería en los dos.
    const hermanos = hijo
      ? hijosDelTrabajo.filter((h) => h.colegio_id === hijo.colegio_id && h.grado === hijo.grado).length
      : 0;
    const apodos = new Set(
      matriculas
        .filter(
          (m) => hijo && hermanos <= 1 && m.colegio_id === hijo.colegio_id && m.grado === hijo.grado,
        )
        .map((m) => m.apodo?.trim() ?? "")
        .filter(Boolean),
    );
    if (propio) etiquetas.set(referencia, propio);
    else if (apodos.size === 1) etiquetas.set(referencia, [...apodos][0]!);
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

// "Ana", "Ana y Luis", "Ana, Luis y Sofi". Los nombres salen del mismo mapa
// que las pastillas de los renglones (`etiquetasDeHijos`), así que coinciden.
// Un hijo que el mapa no conoce se llama "Hijo N" por su lugar en el grupo; un
// hijo repetido se nombra una sola vez.
export function nombresEnLista(
  hijos: readonly string[],
  nombres: ReadonlyMap<string, string>,
): string {
  const vistos = new Set<string>();
  const lista: string[] = [];
  hijos.forEach((h, i) => {
    const nombre = nombres.get(h)?.trim() || `Hijo ${i + 1}`;
    if (!vistos.has(nombre)) {
      vistos.add(nombre);
      lista.push(nombre);
    }
  });
  if (lista.length <= 1) return lista[0] ?? "";
  return `${lista.slice(0, -1).join(", ")} y ${lista[lista.length - 1]}`;
}

// Lo que el acudiente lee de un grupo que se junta entre hermanos: para quién
// es, cuánto se necesita y se compra en total y, solo si el contrato lo trae,
// cuánto se ahorra frente a comprar por separado (el ahorro viene exacto del
// backend: precio × paquetes de menos; no se recalcula aquí). La consolidación
// no trae la unidad ni el tamaño del paquete: el nombre del producto, que casi
// siempre lo lleva ("x12 Und"), se muestra aparte y la frase no lo repite.
export function textoDeConsolidacion(
  c: {
    hijos: readonly string[];
    demanda_base?: number | null;
    unidades_a_comprar?: number | null;
  },
  nombres: ReadonlyMap<string, string>,
  ahorroEnPesos: string | null,
): { paraQuienes: string | null; cantidad: string | null; ahorro: string | null } {
  const quienes = nombresEnLista(c.hijos, nombres);
  const paquetes = c.unidades_a_comprar ?? 0;
  const necesitan = c.demanda_base ?? 0;
  const compras =
    paquetes > 0 ? `compras ${paquetes === 1 ? "1 paquete" : `${paquetes} paquetes`}` : null;
  let cantidad: string | null = null;
  if (necesitan > 0) {
    cantidad = `Necesitan ${necesitan} ${necesitan === 1 ? "unidad" : "unidades"} en total` + (compras ? ` y ${compras}` : "");
  } else if (compras) {
    cantidad = `En total ${compras}`;
  }
  return {
    paraQuienes: quienes ? `Para ${quienes}` : null,
    cantidad,
    ahorro: ahorroEnPesos ? `Ahorras ${ahorroEnPesos} frente a comprarlos por separado` : null,
  };
}
