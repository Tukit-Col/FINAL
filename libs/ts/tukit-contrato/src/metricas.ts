// Superficie de lectura de métricas para el panel del operador.
//
// Decisiones:
// - Dos orígenes, un solo tema: `MetricasColegio` es la medida en vivo que calcula Inteligencia sobre los
//   kits publicados de un colegio; `SerieMetricas` es la traza congelada por día que guarda Operación.
// - La cobertura viaja como fracción (0..1) en vivo y en puntos base (0..10000) en la serie, porque la
//   columna es entera; `fraccionDeBps` deshace la conversión en el borde.

export interface MetricasColegio {
  colegio_id: string;
  kits_armados: number;
  lineas_comprables: number;
  lineas_resueltas: number;
  cobertura: number;
  ahorro_total_cop: number;
}

export interface PadreConNinos {
  usuario_id: string;
  ninos: number;
}

export interface PedidosPorGrado {
  grado: string;
  padres: number;
  ninos: number;
  por_padre: PadreConNinos[];
}

export interface ResumenPedidosColegio {
  colegio_id: string;
  total_padres: number;
  total_ninos: number;
  por_padre: PadreConNinos[];
  por_grado: PedidosPorGrado[];
  estados_trabajos: {
    espera_revision: number;
    publicado: number;
    fallido: number;
  };
}

export interface PuntoMetrica {
  fecha: string;
  dimension: "catalogo" | "colegio" | "global";
  dimension_id: string | null;
  metrica: string;
  valor: number;
}

export interface SerieMetricas {
  puntos: PuntoMetrica[];
}

export function fraccionDeBps(bps: number): number {
  return Math.max(0, Math.min(1, bps / 10000));
}

export function seriePorMetrica(serie: SerieMetricas): Map<string, PuntoMetrica[]> {
  const por = new Map<string, PuntoMetrica[]>();
  for (const p of serie.puntos) {
    const lista = por.get(p.metrica);
    if (lista) lista.push(p);
    else por.set(p.metrica, [p]);
  }
  return por;
}
