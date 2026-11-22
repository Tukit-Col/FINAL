import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ArchivoLista, SolicitudTrabajo } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { cuerpoDemasiadoGrande, motivoDeRechazo } from "@/lib/subida";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function POST(peticion: Request): Promise<Response> {
  const tipo = peticion.headers.get("content-type") ?? "";

  let solicitud: SolicitudTrabajo;
  const archivos: ArchivoLista[] = [];

  try {
    if (tipo.includes("multipart/form-data")) {
      if (cuerpoDemasiadoGrande(peticion)) {
        return respuestaDeError(
          new ErrorTukit(413, "archivo_muy_grande", "El archivo pesa más de 10 MB. Prueba con una foto más liviana o con el PDF del colegio."),
        );
      }
      const forma = await peticion.formData();
      const crudo = forma.get("hijos");
      if (typeof crudo !== "string") {
        return respuestaDeError(
          new ErrorTukit(400, "hijos_requeridos", "Falta el campo `hijos` con los datos del hogar."),
        );
      }
      solicitud = JSON.parse(crudo) as SolicitudTrabajo;

      const adjuntos = forma.getAll("archivo").filter((v): v is File => v instanceof File);
      const rechazado = adjuntos.map(motivoDeRechazo).find((m) => m !== null);
      if (rechazado) {
        return respuestaDeError(new ErrorTukit(415, "archivo_no_admitido", rechazado));
      }
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
