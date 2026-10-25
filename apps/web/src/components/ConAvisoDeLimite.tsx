// Envuelve el render de una pagina de servidor: si alguna lectura dio 429 (el
// limite de tasa, ADR 0047), pinta `AvisoLimite` en vez de la pagina. Cualquier
// otro fallo —y las senales de Next como `redirect`— sigue su camino.

import type { ReactNode } from "react";
import { avisoDeLimite } from "@/lib/limite";
import { tokenDeSesion } from "@/lib/sesion";
import AvisoLimite from "./AvisoLimite";

export async function conAvisoDeLimite(pagina: () => Promise<ReactNode>): Promise<ReactNode> {
  try {
    return await pagina();
  } catch (causa) {
    const aviso = avisoDeLimite(causa);
    if (!aviso) throw causa;
    return <AvisoLimite mensaje={aviso.mensaje} conSesion={Boolean(await tokenDeSesion())} />;
  }
}
