// Superficie de LECTURA de metricas para el panel del operador.
//
// Dos origenes distintos, un solo tema. `MetricasColegio` es la medida EN VIVO
// que Inteligencia calcula sobre los kits publicados de un colegio
// (`GET /v1/metricas/colegios/{id}`): cobertura y ahorro de hoy, recalculados
// cada vez. `SerieMetricas` es la traza CONGELADA que Operacion guarda por dia
// (`GET /v1/operacion/metricas`): la misma cobertura, pero fotografiada cada
// jornada para poder ver "como mejora el algoritmo mientras crece el catalogo".
//
// La cobertura viaja como fraccion (0..1) en vivo, pero en la serie congelada
// se guarda en puntos base (0..10000) porque la columna es entera. `fraccionDeBps`
// deshace esa conversion en el borde para que la pantalla no repita la aritmetica.

/** Las metricas en vivo de un colegio (Inteligencia). Cero en todo si el
 *  colegio no tiene kits publicados: respuesta valida, no un 404. */
export interface MetricasColegio {
  colegio_id: string;
  kits_armados: number;
  lineas_comprables: number;
  lineas_resueltas: number;
  /** Fraccion 0..1 de lineas comprables resueltas con producto real (FU-06). */
  cobertura: number;
  ahorro_total_cop: number;
}

/** Un padre (por `usuario_id`, sin PII) y cuantos de sus hijos entran en el
 *  conteo. El correo NO viaja aqui: lo resuelve el servidor del admin con el
 *  endpoint protegido de acudientes, pasando estos `usuario_id`. */
export interface PadreConNinos {
  usuario_id: string;
  ninos: number;
}

/** El desglose por grado de los pedidos pagados de un colegio. */
export interface PedidosPorGrado {
  grado: string;
  padres: number;
  ninos: number;
  por_padre: PadreConNinos[];
}

/** El cruce `pedido pagado -> trabajo -> hijos -> padre` de un colegio, que
 *  calcula Inteligencia (`GET /v1/metricas/colegios/{id}/pedidos`) llamando a
 *  Comercio por HTTP. Solo agregados e ids: cero PII. "Pedido" = pedido en un
 *  estado confirmado (la definicion vive en Comercio). Todo en cero y listas
 *  vacias si el colegio no tiene pedidos pagados: respuesta valida, no 404. */
export interface ResumenPedidosColegio {
  colegio_id: string;
  /** `usuario_id` distintos con >=1 hijo de este colegio en pedidos pagados. */
  total_padres: number;
  /** Hijos de este colegio contados en esos pedidos (un trabajo cuenta una vez). */
  total_ninos: number;
  por_padre: PadreConNinos[];
  por_grado: PedidosPorGrado[];
  /** Estado de las solicitudes de kit del colegio (todas, no solo pagadas). */
  estados_trabajos: {
    espera_revision: number;
    publicado: number;
    fallido: number;
  };
}

/** Un punto de la serie congelada: una metrica, un dia, una dimension. */
export interface PuntoMetrica {
  fecha: string; // ISO YYYY-MM-DD
  dimension: "catalogo" | "colegio" | "global";
  dimension_id: string | null;
  metrica: string;
  valor: number;
}

/** La respuesta cruda de `GET /v1/operacion/metricas`. Vacia si aun no se ha
 *  congelado ningun snapshot (`make instantanea-metricas` no se ha corrido). */
export interface SerieMetricas {
  puntos: PuntoMetrica[];
}

/** Puntos base (0..10000) a fraccion (0..1). Inverso del `_a_bps` del backend;
 *  las metricas cuyo nombre acaba en `_bps` guardan porcentajes asi. */
export function fraccionDeBps(bps: number): number {
  return Math.max(0, Math.min(1, bps / 10000));
}

/** Agrupa los puntos de una serie por nombre de metrica, cada uno ya ordenado
 *  por fecha, para que la pantalla pinte una linea por metrica sin re-agrupar.
 *  Los puntos ya vienen ordenados por fecha del backend; se conserva ese orden. */
export function seriePorMetrica(serie: SerieMetricas): Map<string, PuntoMetrica[]> {
  const por = new Map<string, PuntoMetrica[]>();
  for (const p of serie.puntos) {
    const lista = por.get(p.metrica);
    if (lista) lista.push(p);
    else por.set(p.metrica, [p]);
  }
  return por;
}
