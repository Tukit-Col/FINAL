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
    const error = conEspera(
      respuesta.status,
      (leido ?? {}) as ErrorApi & Record<string, unknown>,
      respuesta.headers.get("Retry-After"),
    );
    throw new FalloApi(
      respuesta.status,
      error.error ?? "error_desconocido",
      error.mensaje ?? "Algo salió mal al guardar el cambio.",
      error,
    );
  }
  return leido as T;
}

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
