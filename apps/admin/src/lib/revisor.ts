// La carga del revisor de una lista (`/onboarding/{version_id}`), separada de
// la página para poder probar con `node --test` qué errores la tumban y cuáles
// no.
//
// La regla: solo `version_no_existe` es "esta página no existe" (`notFound`).
// Una lista sembrada o editada a mano no tiene documento original, y la
// percepción responde 404 `sin_evidencia`; eso no impide revisarla —las
// regiones 3 y 4 trabajan sobre la versión, no sobre el PDF—, así que se
// degrada a `percepcion: null` y la página lo explica en las regiones 1 y 2.
//
// Los errores se reconocen por su FORMA (`estado` + `codigo`) y no con
// `instanceof ErrorTukit`: así este módulo solo importa tipos del contrato y
// corre igual en Next que en `node --test`.

import type {
  Catalogo,
  OrigenDatos,
  PercepcionCruda,
  RevisionLista,
  VistaPreviaLista,
} from "@tukit/contrato";

export type OrigenRevisor = Pick<
  OrigenDatos,
  "revisionLista" | "percepcion" | "catalogo" | "vistaPreviaDeVersion"
>;

export interface DatosRevisor {
  revision: RevisionLista;
  // null = la versión no tiene documento original (`sin_evidencia`).
  percepcion: PercepcionCruda | null;
  catalogo: Catalogo;
  // null = no hay vista previa en espera (o no se pudo leer: es un aviso, no
  // debe impedir revisar la lista).
  vistaPrevia: VistaPreviaLista | null;
}

function esError(causa: unknown, estado: number, codigo: string): boolean {
  if (typeof causa !== "object" || causa === null) return false;
  const error = causa as { estado?: unknown; codigo?: unknown };
  return error.estado === estado && error.codigo === codigo;
}

/** Los datos del revisor, o null si la versión no existe (→ `notFound()`). */
export async function cargarRevisor(
  origen: OrigenRevisor,
  versionId: string,
): Promise<DatosRevisor | null> {
  const [revision, percepcion, catalogo, vistaPrevia] = await Promise.allSettled([
    origen.revisionLista(versionId),
    origen.percepcion(versionId),
    origen.catalogo(),
    origen.vistaPreviaDeVersion(versionId),
  ]);

  for (const resultado of [revision, percepcion]) {
    if (resultado.status === "rejected" && esError(resultado.reason, 404, "version_no_existe")) {
      return null;
    }
  }
  if (revision.status === "rejected") throw revision.reason;
  if (catalogo.status === "rejected") throw catalogo.reason;

  let percepcionLeida: PercepcionCruda | null = null;
  if (percepcion.status === "fulfilled") {
    percepcionLeida = percepcion.value;
  } else if (!esError(percepcion.reason, 404, "sin_evidencia")) {
    throw percepcion.reason;
  }

  return {
    revision: revision.value,
    percepcion: percepcionLeida,
    catalogo: catalogo.value,
    vistaPrevia: vistaPrevia.status === "fulfilled" ? vistaPrevia.value : null,
  };
}
