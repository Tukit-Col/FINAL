export interface ParAtributo {
  clave: string;
  valor: string;
}

export interface GruposAtributos {
  discriminantes: ParAtributo[];
  descriptivos: ParAtributo[];
  libres: ParAtributo[];
}

export function comoTexto(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  if (typeof valor === "object") return JSON.stringify(valor);
  return String(valor);
}

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
