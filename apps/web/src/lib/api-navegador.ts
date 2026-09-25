// El lado del navegador del ciclo asincrono.
//
// Habla solo con los Route Handlers de esta misma app, nunca con el backend:
// asi la bandera `TUKIT_ORIGEN_DATOS` vive en un solo sitio y el cliente no
// tiene que saber que existe.

import type {
  AplicarCanonico,
  CasoCreado,
  Checkout,
  Contacto,
  ErrorApi,
  HijoSubida,
  Preferencias,
  SolicitudCaso,
  SolicitudCheckout,
  SolicitudTrabajo,
  SubidaListas,
  Trabajo,
  TrabajoAplicado,
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

/**
 * Ruta rápida: aplica el nivel + personaje del acudiente a la cache bendita de
 * un (colegio, grado) ya publicado, sin subir PDF ni entrar a la cola. Devuelve
 * el trabajo creado y el total del pedido congelado.
 */
export async function aplicarCanonico(cuerpo: AplicarCanonico): Promise<TrabajoAplicado> {
  return leer<TrabajoAplicado>(
    await fetch("/api/trabajos/aplicar-canonico", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    }),
  );
}

/**
 * Checkout: el acudiente paga el kit de un trabajo publicado. Manda solo perfil
 * + correo + dirección; el backend arma la orden en Comercio y devuelve la url
 * de la pasarela a la que redirigir. No viaja ningún id de producto.
 */
export async function iniciarCheckout(
  trabajoId: string,
  cuerpo: SolicitudCheckout,
): Promise<Checkout> {
  return leer<Checkout>(
    await fetch(`/api/trabajos/${encodeURIComponent(trabajoId)}/ordenar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    }),
  );
}

/**
 * Sugiere un (colegio, grado) al backlog del administrador cuando aún no es
 * aliado. El PDF que el acudiente subió viaja como semilla de onboarding; la
 * única traza al acudiente es `contacto_referencia` —correo y celular nunca
 * salen del navegador por aquí—.
 */
export async function sugerirColegio(datos: {
  colegioId: string;
  grado: string;
  anioLectivo: number;
  archivo?: File | null;
  contactoReferencia?: string;
}): Promise<{ tarea_id: string; estado: string }> {
  const forma = new FormData();
  forma.append("colegio_id", datos.colegioId);
  forma.append("grado", datos.grado);
  forma.append("anio_lectivo", String(datos.anioLectivo));
  if (datos.contactoReferencia) forma.append("contacto_referencia", datos.contactoReferencia);
  if (datos.archivo) forma.append("archivo", datos.archivo, datos.archivo.name);
  return leer<{ tarea_id: string; estado: string }>(
    await fetch("/api/sugerencias", { method: "POST", body: forma }),
  );
}

/**
 * Sube el PDF de cada hijo para que se importe como una versión PENDIENTE de su
 * (colegio, grado). NO crea un trabajo: el acudiente espera la verificación de
 * un administrador. El contacto viaja para que Identidad lo registre una vez;
 * su correo y celular nunca se guardan en catálogo —solo baja el
 * `contacto_referencia` (un id) para poder avisarle cuando aprueben la lista—.
 */
export async function subirListas(
  hijos: HijoSubida[],
  archivos: { referencia: string; archivo: File }[],
  contacto?: Contacto,
  preferencias?: Preferencias,
): Promise<SubidaListas> {
  const forma = new FormData();
  forma.append("hijos", JSON.stringify(hijos));
  if (contacto) forma.append("contacto", JSON.stringify(contacto));
  // El paso 3 es del hogar: las preferencias viajan una vez y quedan con cada
  // versión, para que el kit que se arme al aprobar use lo que el padre pidió.
  if (preferencias) forma.append("preferencias", JSON.stringify(preferencias));
  for (const { referencia, archivo } of archivos) {
    forma.append("archivo", archivo, archivo.name);
    forma.append("referencia", referencia);
  }
  return leer<SubidaListas>(await fetch("/api/listas/subir", { method: "POST", body: forma }));
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
