// `POST /api/onboarding`: entrada del revisor de listas.
//
// Decisiones:
// - Es una ruta de staff: el token de la cookie httpOnly se reenvía como Bearer y la URL del backend se
//   queda del lado del servidor. La percepción de un PDF tarda más que el corte de 30 s de una `rewrite`.
// - El colegio llega como `colegio_id`, como `colegio_dane` y `colegio_nombre` (del directorio) o solo
//   como `colegio_nombre`. Un DANE que ya es de un colegio de Tukit se reconduce a su `colegio_id` en el
//   servidor (`designarColegio`).

import type { ColegioDesignado } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { designarColegio } from "@/lib/designar-colegio";
import { respuestaDeError } from "@/lib/respuesta";
import { tokenDeSesion } from "@/lib/sesion";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function POST(peticion: Request): Promise<Response> {
  const token = await tokenDeSesion();
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Tu sesión terminó. Vuelve a ingresar."),
    );
  }

  const tipo = peticion.headers.get("content-type") ?? "";
  if (!tipo.includes("multipart/form-data")) {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "El onboarding va como multipart con el PDF."),
    );
  }

  let campos: { colegio_id: unknown; colegio_dane: unknown; colegio_nombre: unknown };
  let grado: string;
  let anioLectivo: number;
  let archivo: File;
  try {
    const forma = await peticion.formData();
    campos = {
      colegio_id: forma.get("colegio_id"),
      colegio_dane: forma.get("colegio_dane"),
      colegio_nombre: forma.get("colegio_nombre"),
    };
    const gr = forma.get("grado");
    const anio = forma.get("anio_lectivo");
    const adjunto = forma.get("archivo");
    if (typeof gr !== "string" || !(adjunto instanceof File)) {
      return respuestaDeError(
        new ErrorTukit(
          400,
          "peticion_invalida",
          "Faltan el grado o el archivo de la lista.",
        ),
      );
    }
    grado = gr;
    anioLectivo = Number(anio);
    if (!Number.isInteger(anioLectivo) || anioLectivo < 2000 || anioLectivo > 2100) {
      return respuestaDeError(
        new ErrorTukit(400, "anio_invalido", "El año lectivo va como un entero de cuatro cifras.", {
          campo: "anio_lectivo",
        }),
      );
    }
    archivo = adjunto;
  } catch {
    return respuestaDeError(
      new ErrorTukit(400, "peticion_invalida", "No pudimos leer el formulario del onboarding."),
    );
  }

  let colegio: ColegioDesignado | null;
  try {
    colegio = designarColegio(
      campos,
      campos.colegio_dane ? await origenDeDatos().colegios() : [],
    );
  } catch (causa) {
    return respuestaDeError(causa);
  }
  if (!colegio) {
    return respuestaDeError(
      new ErrorTukit(400, "colegio_requerido", "Elige el colegio de la lista o escribe su nombre.", {
        campo: "colegio",
      }),
    );
  }

  try {
    const version = await origenDeDatos().onboarding(token, colegio, grado, anioLectivo, {
      contenido: archivo,
      nombre: archivo.name,
    });
    return Response.json(version, { status: 201 });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
