// El lado del navegador del ciclo asincrono.
//
// Habla solo con los Route Handlers de esta misma app, nunca con el backend:
// asi la bandera `TUKIT_ORIGEN_DATOS` vive en un solo sitio y el cliente no
// tiene que saber que existe.

import type {
  CasoCreado,
  ErrorApi,
  SolicitudCaso,
  SolicitudTrabajo,
  Trabajo,
  TrabajoCreado,
} from "@tukit/contrato";

export class FalloApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
  }
}

async function leer<T>(respuesta: Response): Promise<T> {
  const texto = await respuesta.text();
  const cuerpo: unknown = texto ? JSON.parse(texto) : null;
  if (!respuesta.ok) {
    const error = (cuerpo ?? {}) as ErrorApi & Record<string, unknown>;
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salió mal.",
      error,
    );
  }
  return cuerpo as T;
}

export async function crearTrabajo(
  solicitud: SolicitudTrabajo,
  archivos: { referencia: string; archivo: File }[] = [],
): Promise<TrabajoCreado> {
  if (archivos.length === 0) {
    return leer<TrabajoCreado>(
      await fetch("/api/trabajos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(solicitud),
      }),
    );
  }

  const forma = new FormData();
  forma.append("hijos", JSON.stringify(solicitud));
  for (const { referencia, archivo } of archivos) {
    forma.append("archivo", archivo, archivo.name);
    forma.append("referencia", referencia);
  }
  return leer<TrabajoCreado>(await fetch("/api/trabajos", { method: "POST", body: forma }));
}

export async function crearCaso(solicitud: SolicitudCaso): Promise<CasoCreado> {
  return leer<CasoCreado>(
    await fetch("/api/casos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(solicitud),
    }),
  );
}

export async function consultarTrabajo(trabajoId: string): Promise<Trabajo> {
  return leer<Trabajo>(
    await fetch(`/api/trabajos/${encodeURIComponent(trabajoId)}`, { cache: "no-store" }),
  );
}

/**
 * Sondea hasta que el trabajo termine.
 *
 * Con intervalo creciente y no fijo: el pipeline tarda minutos, y preguntar
 * cada segundo durante tres minutos son ciento ochenta peticiones para saber
 * lo mismo. Empieza rapido porque los primeros segundos es cuando el
 * acudiente esta mirando la pantalla.
 */
export function sondear(
  trabajoId: string,
  alCambiar: (trabajo: Trabajo) => void,
  alFallar: (fallo: FalloApi) => void,
): () => void {
  let vivo = true;
  let intervalo = 1000;

  async function ciclo(): Promise<void> {
    if (!vivo) return;
    try {
      const trabajo = await consultarTrabajo(trabajoId);
      if (!vivo) return;
      alCambiar(trabajo);
      if (trabajo.estado === "publicado" || trabajo.estado === "fallido") return;
    } catch (causa) {
      if (!vivo) return;
      if (causa instanceof FalloApi) {
        alFallar(causa);
        // Un 404 no se arregla esperando; una caida momentanea si.
        if (causa.estado === 404) return;
      }
    }
    intervalo = Math.min(intervalo * 1.4, 8000);
    setTimeout(() => void ciclo(), intervalo);
  }

  void ciclo();
  return () => {
    vivo = false;
  };
}
