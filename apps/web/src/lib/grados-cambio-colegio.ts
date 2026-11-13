// Grados que se ofrecen al cambiar de colegio un hijo desde el dashboard.
// Misma fuente que /empezar: `colegio.grados` son los grados con lista revisada
// (verificada). Aquí solo se ofrecen esos, en el orden canónico.

export interface OpcionGrados {
  /** Grados verificados del colegio, en orden canónico. */
  opciones: string[];
  /** Grado a preseleccionar: el actual solo si el colegio lo tiene verificado. */
  seleccionado: string;
  /** El hijo tenía un grado que el colegio nuevo no tiene verificado. */
  gradoPerdido: boolean;
  /** El colegio no tiene ningún grado verificado: ofrecer subir la lista. */
  sinVerificados: boolean;
}

export function gradosParaCambio(
  gradosColegio: readonly string[],
  canonicos: readonly string[],
  gradoActual: string,
): OpcionGrados {
  const verificados = new Set(gradosColegio);
  const opciones = canonicos.filter((g) => verificados.has(g));
  const conserva = opciones.includes(gradoActual);
  return {
    opciones,
    seleccionado: conserva ? gradoActual : "",
    gradoPerdido: !conserva && opciones.length > 0 && Boolean(gradoActual),
    sinVerificados: opciones.length === 0,
  };
}
