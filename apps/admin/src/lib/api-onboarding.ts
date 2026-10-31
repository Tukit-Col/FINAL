// El lado del navegador de las acciones del onboarding y las listas (P4).
//
// Habla solo con los Route Handlers de esta misma app, nunca con el backend:
// la URL del backend se queda del lado del servidor. Es un modulo propio de
// esta rebanada —no se toca `api-navegador.ts`—
// que reproduce la forma de `enviar()` de ese fichero, ampliada a los verbos
// que estas pantallas necesitan (multipart para el PDF, PATCH/POST para los
// items) sin acoplarse al resto de las acciones del §7.

import type { ColegioDesignado, ErrorApi } from "@tukit/contrato";
import { conEspera } from "@tukit/contrato";

export class FalloApi extends Error {
  constructor(
    readonly estado: number,
    readonly codigo: string,
    mensaje: string,
    readonly detalle: Record<string, unknown> = {},
  ) {
    super(mensaje);
    this.name = "FalloApi";
  }
}

async function leer<T>(respuesta: Response): Promise<T> {
  const texto = await respuesta.text();
  const leido: unknown = texto ? JSON.parse(texto) : null;
  if (!respuesta.ok) {
    // Un 429 llega con la espera en el mensaje aunque el cuerpo no la traiga.
    const error = conEspera(
      respuesta.status,
      (leido ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
    // El mensaje que se muestra es el del backend, no uno inventado aqui: es el
    // unico que sabe por que rechazo la accion.
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salió mal al guardar el cambio.",
      error,
    );
  }
  return leido as T;
}

/** El PDF de un grado hacia inteligencia, que lo percibe y crea la version.
 *  Va como `multipart/form-data`: el archivo mas su destino en campos aparte,
 *  igual que `crearTrabajo` con archivos. El colegio va con los campos de su
 *  designacion (`colegio_id`, o `colegio_dane` + `colegio_nombre`, o solo
 *  `colegio_nombre`). Devuelve la version recien creada. */
export async function subirOnboarding(datos: {
  colegio: ColegioDesignado;
  grado: string;
  anioLectivo: number;
  archivo: File;
}): Promise<{ version_id: string; grado: string; items: number }> {
  const forma = new FormData();
  for (const [campo, valor] of Object.entries(datos.colegio)) forma.append(campo, valor);
  forma.append("grado", datos.grado);
  forma.append("anio_lectivo", String(datos.anioLectivo));
  forma.append("archivo", datos.archivo, datos.archivo.name);
  return leer(await fetch("/api/onboarding", { method: "POST", body: forma }));
}
