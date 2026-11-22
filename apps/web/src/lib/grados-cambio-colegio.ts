export interface OpcionGrados {
  opciones: string[];
  seleccionado: string;
  gradoPerdido: boolean;
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
