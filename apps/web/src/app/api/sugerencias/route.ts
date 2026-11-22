import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { cuerpoDemasiadoGrande, motivoDeRechazo } from "@/lib/subida";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function POST(peticion: Request): Promise<Response> {
  const tipo = peticion.headers.get("content-type") ?? "";

  let colegioId = "";
  let grado = "";
  let anio = 0;
  let referencia: string | undefined;
  let archivo: { contenido: Blob; nombre: string } | undefined;

  try {
    if (tipo.includes("multipart/form-data")) {
      if (cuerpoDemasiadoGrande(peticion)) {
        return respuestaDeError(
          new ErrorTukit(413, "archivo_muy_grande", "El archivo pesa más de 10 MB. Prueba con una foto más liviana o con el PDF del colegio."),
        );
      }
      const forma = await peticion.formData();
      colegioId = String(forma.get("colegio_id") ?? "");
      grado = String(forma.get("grado") ?? "");
      anio = Number(forma.get("anio_lectivo") ?? 0);
      const ref = forma.get("contacto_referencia");
      referencia = typeof ref === "string" && ref ? ref : undefined;
      const adjunto = forma.get("archivo");
      if (adjunto instanceof File) {
        const rechazado = motivoDeRechazo(adjunto);
        if (rechazado) {
          return respuestaDeError(new ErrorTukit(415, "archivo_no_admitido", rechazado));
        }
        archivo = { contenido: adjunto, nombre: adjunto.name };
      }
    } else {
      const cuerpo = (await peticion.json()) as {
        colegio_id?: string;
        grado?: string;
        anio_lectivo?: number;
        contacto_referencia?: string;
      };
      colegioId = cuerpo.colegio_id ?? "";
      grado = cuerpo.grado ?? "";
      anio = cuerpo.anio_lectivo ?? 0;
      referencia = cuerpo.contacto_referencia || undefined;
    }
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer tu sugerencia."),
    );
  }

  if (!colegioId || !grado || !anio) {
    return respuestaDeError(
      new ErrorTukit(400, "datos_incompletos", "Faltan el colegio, el grado o el año lectivo."),
    );
  }

  try {
    const creado = await origenDeDatos().sugerirColegio(
      colegioId,
      grado,
      anio,
      archivo,
      referencia,
    );
    return Response.json(creado, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
