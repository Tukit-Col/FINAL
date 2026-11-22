import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import type { ArchivoLista, Contacto, HijoSubida, Preferencias } from "@tukit/contrato";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";
import { cuerpoDemasiadoGrande, motivoDeRechazo } from "@/lib/subida";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function POST(peticion: Request): Promise<Response> {
  let hijos: HijoSubida[];
  let contacto: Contacto | undefined;
  let preferencias: Preferencias | undefined;
  const archivos: ArchivoLista[] = [];

  try {
    if (cuerpoDemasiadoGrande(peticion)) {
      return respuestaDeError(
        new ErrorTukit(413, "archivo_muy_grande", "El archivo pesa más de 10 MB. Prueba con una foto más liviana o con el PDF del colegio."),
      );
    }
    const forma = await peticion.formData();

    const crudoHijos = forma.get("hijos");
    if (typeof crudoHijos !== "string") {
      return respuestaDeError(
        new ErrorTukit(400, "hijos_requeridos", "Falta el campo `hijos` con los datos del hogar."),
      );
    }
    hijos = JSON.parse(crudoHijos) as HijoSubida[];

    const crudoContacto = forma.get("contacto");
    if (typeof crudoContacto === "string") {
      contacto = JSON.parse(crudoContacto) as Contacto;
    }

    const crudoPreferencias = forma.get("preferencias");
    if (typeof crudoPreferencias === "string") {
      preferencias = JSON.parse(crudoPreferencias) as Preferencias;
    }

    const adjuntos = forma.getAll("archivo").filter((v): v is File => v instanceof File);
    const rechazado = adjuntos.map(motivoDeRechazo).find((m) => m !== null);
    if (rechazado) {
      return respuestaDeError(new ErrorTukit(415, "archivo_no_admitido", rechazado));
    }
    const referencias = forma.getAll("referencia").map(String);
    adjuntos.forEach((archivo, indice) => {
      archivos.push({
        referencia: referencias[indice] ?? hijos[indice]?.referencia ?? `hijo-${indice + 1}`,
        nombre: archivo.name,
        tipo: archivo.type,
        tamano: archivo.size,
        contenido: archivo,
      });
    });
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer los datos del formulario."),
    );
  }

  try {
    const resultado = await origenDeDatos().subirListas(
      hijos,
      archivos,
      contacto,
      preferencias,
      await tokenDeSesion(),
    );
    return Response.json(resultado, { status: 202 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
