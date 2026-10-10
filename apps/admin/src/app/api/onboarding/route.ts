// `POST /api/onboarding` — P4, region de entrada del revisor de listas.
//
// Inteligencia recibe el PDF de un grado, lo percibe y lo vuelca en catalogo
// como una version importada. El navegador nunca llama a inteligencia
// directamente: la URL del backend y la bandera del origen se quedan aqui, del
// lado del servidor, igual que en `/api/trabajos`. La percepcion de un PDF
// tarda mas que el corte de 30 s de un `rewrite`, otra razon para el salto.
//
// El colegio llega como `colegio_id`, o `colegio_dane` + `colegio_nombre` (del
// directorio de Bogota), o solo `colegio_nombre` (escrito a mano). Un DANE que
// ya es de un colegio de Tukit se reconduce a su `colegio_id` aqui, del lado
// del servidor (`designarColegio`).

import type { ColegioDesignado } from "@tukit/contrato";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { designarColegio } from "@/lib/designar-colegio";
import { respuestaDeError } from "@/lib/respuesta";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function POST(peticion: Request): Promise<Response> {
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
    // Año lectivo entero; el borde vuelve a validar lo que la pantalla ya pide.
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
    // Solo hace falta la lista de colegios para reconducir un DANE.
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
    const version = await origenDeDatos().onboarding(colegio, grado, anioLectivo, {
      contenido: archivo,
      nombre: archivo.name,
    });
    return Response.json(version, { status: 201 });
  } catch (causa) {
    // Un 422 `lista_de_varios_grados` sube tal cual: la pantalla tiene que
    // decir por que se rechazo el PDF.
    return respuestaDeError(causa);
  }
}
