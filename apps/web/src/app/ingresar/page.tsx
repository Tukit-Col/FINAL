// Pantalla de ingreso.
//
// Se autentica contra identidad a traves del gateway. Si ya hay sesion, no
// tiene sentido volver a pedir credenciales: se redirige al destino que
// corresponde por rol.

import { redirect } from "next/navigation";
import { destinoDe, urlAdmin } from "@tukit/contrato/servidor";
import { sesionActual } from "@/lib/sesion";
import FormularioIngreso from "./FormularioIngreso";

export const dynamic = "force-dynamic";
export const metadata = { title: "Ingresar — Tukit" };

export default async function Ingresar() {
  const sesion = await sesionActual();
  if (sesion) {
    const destino = destinoDe(sesion);
    redirect(destino.app === "admin" ? `${urlAdmin()}${destino.ruta}` : destino.ruta);
  }

  return <FormularioIngreso />;
}
