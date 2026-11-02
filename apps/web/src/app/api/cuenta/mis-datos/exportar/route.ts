// `GET /api/cuenta/mis-datos/exportar`: la copia completa de los datos del
// titular (Ley 1581, art. 8), como archivo. El token sale de la cookie httpOnly
// aqui, en el servidor; el navegador solo recibe el adjunto.
import { cookies } from "next/headers";
import { ErrorTukit, origenDeDatos } from "@tukit/contrato/servidor";
import { respuestaDeError } from "@/lib/respuesta";
import { COOKIE_SESION } from "@/lib/sesion";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  const token = (await cookies()).get(COOKIE_SESION)?.value;
  if (!token) {
    return respuestaDeError(
      new ErrorTukit(401, "sesion_invalida", "Necesitas una sesión para descargar tus datos."),
    );
  }
  try {
    const { contenido, nombreArchivo } = await origenDeDatos().exportarMisDatos(token);
    return new Response(contenido, {
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Disposition": `attachment; filename="${nombreArchivo}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (causa) {
    return respuestaDeError(causa);
  }
}
