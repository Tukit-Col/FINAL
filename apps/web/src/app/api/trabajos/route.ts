// `POST /api/trabajos` — la mitad del navegador del §2 del contrato.
//
// El navegador no llama al backend directamente y nunca lo va a hacer: la URL
// del backend se queda en el servidor, el tiempo de espera del pipeline supera
// el corte de 30 s de un `rewrite`, y este es el unico punto donde se habla con
// el backend. El prototipo ya tenia esta forma y se conserva por las mismas
// razones.

import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ArchivoLista, SolicitudTrabajo } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function POST(peticion: Request): Promise<Response> {
  const tipo = peticion.headers.get("content-type") ?? "";

  let solicitud: SolicitudTrabajo;
  const archivos: ArchivoLista[] = [];

  try {
    if (tipo.includes("multipart/form-data")) {
      // Entrada (b) del §2: el JSON viaja en el campo `hijos` y los archivos
      // en `archivo`, uno por hijo.
      const forma = await peticion.formData();
      const crudo = forma.get("hijos");
      if (typeof crudo !== "string") {
        return respuestaDeError(
          new ErrorTukit(400, "hijos_requeridos", "Falta el campo `hijos` con los datos del hogar."),
        );
      }
      solicitud = JSON.parse(crudo) as SolicitudTrabajo;

      const adjuntos = forma.getAll("archivo").filter((v): v is File => v instanceof File);
      const referencias = forma.getAll("referencia").map(String);
      adjuntos.forEach((archivo, indice) => {
        archivos.push({
          referencia: referencias[indice] ?? solicitud.hijos[indice]?.referencia ?? `hijo-${indice + 1}`,
          nombre: archivo.name,
          tipo: archivo.type,
          tamano: archivo.size,
          contenido: archivo,
        });
      });
    } else {
      // Entrada (a): el colegio ya publico la lista.
      solicitud = (await peticion.json()) as SolicitudTrabajo;
    }
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del formulario."),
    );
  }

  try {
    const creado = await origenDeDatos().crearTrabajo(solicitud, archivos, await tokenDeSesion());
    return Response.json(creado, { status: 202 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
