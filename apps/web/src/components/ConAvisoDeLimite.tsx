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
