// Cómo se arma la cola de revisión, separado de las páginas para poder
// probarlo con `node --test` y para que `/cola` y el inicio cuenten lo mismo.
//
// Dos secciones:
//  - "Listas por verificar": UNA fila por versión pendiente. Su vista previa
//    (`preview_onboarding`) no es otra fila: es el estado de esa lista. El kit
//    del grado que nace al aprobar una lista sin vista previa al día
//    (`colegio_grado` en espera) también va aquí, en la fila de su lista o en
//    una propia si la versión ya se cerró.
//  - "Kits de acudientes por aprobar": los trabajos con un acudiente dueño en
//    `espera_revision`. Los `parent_apply` que esperan un kit del grado no
//    llegan aquí (el backend no los lista): van contados en ese kit.
//
// Una vista previa cuya versión ya no está pendiente es huérfana (la lista se
// aprobó, se reemplazó o se descartó) y no se muestra: no hay lista que
// aprobar con ella.

import type { EntradaCola, VersionListaAdmin } from "@tukit/contrato";

export const ORIGEN_VISTA_PREVIA = "preview_onboarding";
export const ORIGEN_KIT_DEL_GRADO = "colegio_grado";

export type EstadoFilaLista =
  | { tipo: "sin_vista_previa" }
  | { tipo: "vista_previa"; dudosas: number }
  | { tipo: "lista_para_aprobar" }
  | { tipo: "kit_del_grado"; dudosas: number };

export interface FilaLista {
  // La versión pendiente; null cuando la fila es solo el kit del grado de una
  // lista ya aprobada.
  version: VersionListaAdmin | null;
  vistaPrevia: EntradaCola | null;
  kitDelGrado: EntradaCola | null;
  estado: EstadoFilaLista;
  // Hay un acudiente esperando que esta fila se resuelva.
  conAcudiente: boolean;
}

export interface ConteosCola {
  listasPorVerificar: number;
  kitsDeAcudientes: number;
  // Las dudosas sin decidir de todo lo que se muestra, con la misma regla que
  // la consola (AMBIGUO o SIN_MATCH sin decisión; un hueco no cuenta).
  dudosasSinDecidir: number;
}

export interface Cola {
  porVerificar: FilaLista[];
  deAcudientes: EntradaCola[];
  conteos: ConteosCola;
}

/** La etiqueta del estado de una fila de lista, tal cual se pinta. */
export function textoEstadoLista(estado: EstadoFilaLista): string {
  switch (estado.tipo) {
    case "sin_vista_previa":
      return "Sin vista previa";
    case "vista_previa":
      return `Vista previa: ${estado.dudosas} ${estado.dudosas === 1 ? "dudosa" : "dudosas"}`;
    case "lista_para_aprobar":
      return "Lista para aprobar";
    case "kit_del_grado":
      return `Lista verificada · kit con ${estado.dudosas} ${estado.dudosas === 1 ? "dudosa" : "dudosas"}`;
  }
}

function masReciente(a: EntradaCola, b: EntradaCola): EntradaCola {
  return b.recibido_en > a.recibido_en ? b : a;
}

function renglones(fila: FilaLista): number {
  return fila.version?.items ?? fila.kitDelGrado?.lineas_totales ?? 0;
}

/** Las dos secciones de la cola y sus conteos. */
export function armarCola({
  versiones,
  entradas,
}: {
  versiones: readonly VersionListaAdmin[];
  entradas: readonly EntradaCola[];
}): Cola {
  const enEspera = entradas.filter((e) => e.estado === "espera_revision");

  // Si un admin previsualizó dos veces (no debería quedar más de una), la
  // vigente es la más reciente, la misma que lee el revisor.
  const previaPorVersion = new Map<string, EntradaCola>();
  const kitPorVersion = new Map<string, EntradaCola>();
  const kitsSinVersion: EntradaCola[] = [];
  const deAcudientes: EntradaCola[] = [];
  for (const e of enEspera) {
    if (e.origen === ORIGEN_VISTA_PREVIA) {
      if (!e.version_id) continue;
      const otra = previaPorVersion.get(e.version_id);
      previaPorVersion.set(e.version_id, otra ? masReciente(otra, e) : e);
    } else if (e.origen === ORIGEN_KIT_DEL_GRADO && e.usuario_id === null) {
      if (e.version_id && !kitPorVersion.has(e.version_id)) kitPorVersion.set(e.version_id, e);
      else kitsSinVersion.push(e);
    } else {
      deAcudientes.push(e);
    }
  }

  const pendientes = new Set(versiones.map((v) => v.version_id));
  const filas: FilaLista[] = versiones.map((version) => {
    const vistaPrevia = previaPorVersion.get(version.version_id) ?? null;
    const kitDelGrado = kitPorVersion.get(version.version_id) ?? null;
    return {
      version,
      vistaPrevia,
      kitDelGrado,
      estado: estadoDe(vistaPrevia, kitDelGrado),
      conAcudiente: version.tiene_contacto || (kitDelGrado?.acudientes_esperando ?? 0) > 0,
    };
  });
  // El kit del grado de una lista ya cerrada sigue siendo trabajo pendiente:
  // fila propia, sin versión.
  const kitsHuerfanos = [
    ...[...kitPorVersion.entries()].filter(([vid]) => !pendientes.has(vid)).map(([, k]) => k),
    ...kitsSinVersion,
  ];
  for (const kitDelGrado of kitsHuerfanos) {
    filas.push({
      version: null,
      vistaPrevia: null,
      kitDelGrado,
      estado: estadoDe(null, kitDelGrado),
      conAcudiente: kitDelGrado.acudientes_esperando > 0,
    });
  }

  // Primero lo que tiene un acudiente esperando (resolverlo dispara su kit);
  // después, como hasta ahora, lo que tiene más renglones.
  const porVerificar = filas
    .map((fila, i) => ({ fila, i }))
    .sort(
      (a, b) =>
        Number(b.fila.conAcudiente) - Number(a.fila.conAcudiente) ||
        renglones(b.fila) - renglones(a.fila) ||
        a.i - b.i,
    )
    .map(({ fila }) => fila);

  const dudosasSinDecidir =
    porVerificar.reduce(
      (t, f) => t + (f.vistaPrevia?.lineas_sin_decidir ?? 0) + (f.kitDelGrado?.lineas_sin_decidir ?? 0),
      0,
    ) + deAcudientes.reduce((t, e) => t + e.lineas_sin_decidir, 0);

  return {
    porVerificar,
    deAcudientes,
    conteos: {
      listasPorVerificar: porVerificar.length,
      kitsDeAcudientes: deAcudientes.length,
      dudosasSinDecidir,
    },
  };
}

function estadoDe(vistaPrevia: EntradaCola | null, kitDelGrado: EntradaCola | null): EstadoFilaLista {
  if (kitDelGrado) return { tipo: "kit_del_grado", dudosas: kitDelGrado.lineas_sin_decidir };
  if (!vistaPrevia) return { tipo: "sin_vista_previa" };
  if (vistaPrevia.lineas_sin_decidir > 0) {
    return { tipo: "vista_previa", dudosas: vistaPrevia.lineas_sin_decidir };
  }
  return { tipo: "lista_para_aprobar" };
}
