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
